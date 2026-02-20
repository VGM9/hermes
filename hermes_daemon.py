#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes Daemon
=============
Idempotent always-on background process. Monitors VS Code windows and acts
on configured triggers without human intervention.

Triggers (all toggled via hermes_config.json, hot-reloaded each poll cycle):

  update_button      — Detect and click VS Code "Update is ready" status bar button
  reload_dialog      — Detect and click "A chat request is in progress" cancel dialog
  chat_timeout_restart — Click retry when Copilot reports "Chat took too long to get ready"

Wake-on-reload is handled by hermes_wake.py, invoked by the VS Code
folderOpen task. This daemon no longer manages wake state.

Idempotency: writes a PID file on start. Subsequent launches check the PID file;
if the process is alive they exit 0 immediately. The folderOpen VS Code task calls
this script — safe to call every workspace open.

Usage:
    python3 hermes_daemon.py                    # start (or no-op if already running)
    python3 hermes_daemon.py --ensure-running   # alias, same behavior
    python3 hermes_daemon.py --stop             # kill running daemon
    python3 hermes_daemon.py --status           # print running/stopped + PID
    python3 hermes_daemon.py --config /path/to/hermes_config.json

Author: POLARIS1 (0.0.19), 2026-02-19
"""

import sys
import os
import time
import json
import signal
import argparse
import subprocess
from pathlib import Path

try:
    import pywinauto
    from pywinauto import Application, findwindows
    from pywinauto.keyboard import send_keys
except ImportError:
    print("ERROR: pywinauto not installed. Run: pip install pywinauto")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "hermes_config.jsonc"
PID_FILE = SCRIPT_DIR / "hermes_daemon.pid"
VSCODE_CLASS = "Chrome_WidgetWin_1"
DETACHED_PROCESS = 0x00000008  # Windows: detach child from parent console

_UPDATE_BUTTON_FRAGMENTS = [
    "update available",
    "restart to update",
    "click to restart",
    "update is ready",
    "restart required",
]


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def safe_print(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def load_config(path):
    """Load config JSON, return dict. Returns defaults on any error.
    If hermes_config.local.jsonc exists alongside path, its values overlay
    the base config — used for per-workspace overrides (e.g. window_pattern).
    """
    defaults = {
        "triggers": {"update_button": True, "reload_dialog": True, "wake_on_reload": True},
        "wake_msg": "Window reloaded. #qhoami",
        "poll_interval": 0.8,
        "window_pattern": "",
        "wake_debounce_seconds": 10,
    }
    def _parse(fpath):
        raw = Path(fpath).read_text(encoding="utf-8")
        stripped = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("/"))
        return json.loads(stripped)
    try:
        data = _parse(path)
        merged = {**defaults, **data}
        merged["triggers"] = {**defaults["triggers"], **data.get("triggers", {})}
        # Overlay with local config if present
        local_path = Path(path).parent / "hermes_config.local.jsonc"
        if local_path.exists():
            try:
                local = _parse(local_path)
                merged.update(local)
            except Exception as le:
                safe_print(f"[hermes] Local config error ({local_path}): {le} — ignored")
        return merged
    except Exception as e:
        safe_print(f"[hermes] Config load error ({path}): {e} — using defaults")
        return defaults


# ─────────────────────────────────────────────────────────────────────────────
# PID management
# ─────────────────────────────────────────────────────────────────────────────

def read_pid():
    """Return int PID from PID file, or None."""
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def is_process_alive(pid):
    """Return True if a process with the given PID is running."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except Exception:
        return False


def is_daemon_running():
    """Return (alive: bool, pid: int|None)."""
    pid = read_pid()
    if pid is None:
        return False, None
    return is_process_alive(pid), pid


def write_pid():
    PID_FILE.write_text(str(os.getpid()))


def clear_pid():
    try:
        PID_FILE.unlink()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# VS Code window utilities
# ─────────────────────────────────────────────────────────────────────────────

from core.ui_automation.window_detection import find_vscode_windows as _core_find_windows
from core.ui_automation.window_detection import find_agent_mode_in_window

def find_vscode_windows(pattern=None):
    """Adapter: wraps core discovery, adds pattern filter, normalises to dict.
    
    Connects each discovered handle to a pywinauto window object so trigger
    functions can call .descendants() and .click_input() on them.
    """
    windows = _core_find_windows()
    if pattern:
        windows = [w for w in windows if pattern.lower() in w.title.lower()]
    result = []
    for w in windows:
        try:
            app = Application(backend="uia").connect(handle=w.handle)
            win_obj = app.window(handle=w.handle)
            result.append({"handle": w.handle, "title": w.title, "window": win_obj})
        except Exception:
            result.append({"handle": w.handle, "title": w.title, "window": None})
    return result


def handle_is_alive(handle):
    try:
        app = Application(backend="uia").connect(handle=handle)
        app.window(handle=handle).window_text()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Trigger: update button
# ─────────────────────────────────────────────────────────────────────────────

def scan_for_update_button(windows):
    """Return first matching update/restart status bar element, or None."""
    for entry in windows:
        win = entry["window"]
        if win is None:
            continue
        try:
            for ctrl_type in ("Button", "MenuItem", "Custom", "Text"):
                for elem in win.descendants(control_type=ctrl_type):
                    try:
                        name = (elem.element_info.name or "").lower()
                        if any(frag in name for frag in _UPDATE_BUTTON_FRAGMENTS):
                            return elem
                    except Exception:
                        pass
        except Exception:
            pass
    return None


def trigger_update_button(windows):
    """Click update button if found. Returns True if clicked."""
    btn = scan_for_update_button(windows)
    if btn:
        try:
            name = btn.element_info.name
            btn.click_input()
            safe_print(f"[hermes] Clicked update button: '{name}'")
            return True
        except Exception as e:
            safe_print(f"[hermes] Update button click failed: {e}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Trigger: reload dialog
# ─────────────────────────────────────────────────────────────────────────────

def trigger_reload_dialog(windows):
    """Find and click Yes/Reload on the 'chat request in progress' dialog. Returns True if clicked."""
    for entry in windows:
        win = entry["window"]
        if win is None:
            continue
        try:
            descendants = win.descendants()
            texts = [d.window_text().lower() for d in descendants if d.window_text()]
            if any(
                "chat request is in progress" in t or
                "a chat session is in progress" in t
                for t in texts
            ):
                for btn in win.descendants(control_type="Button"):
                    if btn.window_text().lower() in ("yes", "reload", "ok", "restart"):
                        btn.click_input()
                        safe_print(f"[hermes] Clicked reload dialog: '{btn.window_text()}'")
                        return True
        except Exception:
            pass
    return False


def trigger_chat_timeout_restart(windows):
    """Click retry after 'Chat took too long to get ready' error.

    VS Code renders two button layouts for this error:
    - A named 'Restart' button (first occurrence)
    - A row of icon buttons below the response; the retry icon (⟳) has
      accessible name 'Retry' or 'Regenerate response' with no visible text

    Try named button first, then fall back to accessible-name scan.
    See VSQode/hermes#5.
    """
    for entry in windows:
        win = entry["window"]
        if win is None:
            continue
        try:
            descendants = win.descendants()
            texts = [d.window_text().lower() for d in descendants if d.window_text()]
            if not any("chat took too long" in t or "took too long to get ready" in t for t in texts):
                continue

            # Try named button first
            for btn in win.descendants(control_type="Button"):
                label = btn.window_text().lower()
                if label == "restart":
                    btn.click_input()
                    safe_print("[hermes] Clicked chat timeout Restart button")
                    return True

            # Fall back: accessible name scan for retry/regenerate icon.
            # Use exact matching (not substring) to avoid false-positive clicks on
            # unrelated UI elements whose accessible name merely contains "retry"
            # (e.g. search results, pagination buttons). See VSQode/hermes#6.
            RETRY_EXACT_NAMES = {"retry", "regenerate", "regenerate response", "try again", "resend"}
            for btn in win.descendants(control_type="Button"):
                name = (btn.element_info.name or "").lower()
                if name in RETRY_EXACT_NAMES:
                    btn.click_input()
                    safe_print(f"[hermes] Clicked chat retry icon: '{btn.element_info.name}'")
                    return True
        except Exception:
            pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Poll loop state and main loop
# ─────────────────────────────────────────────────────────────────────────────

class DaemonState:
    def __init__(self):
        self.last_update_click_time = 0.0  # debounce: don't click update button repeatedly


def poll_once(state, config, config_path):
    """One poll cycle. Mutates state. Hot-reloads config."""
    config = load_config(config_path)
    triggers = config["triggers"]
    pattern = config.get("window_pattern")
    agent_mode = config.get("agent_mode", "").strip()

    windows = find_vscode_windows(pattern)

    # ── Agent mode filter (VGM9/hermes#5) ────────────────────────────────────
    # If agent_mode is configured, only act on windows containing that agent's
    # chat pane. This prevents polling / acting on the wrong window in
    # multi-window multi-agent deployments.
    # Without this filter, walking a non-target window's descendants fires
    # AutomationFocusChangedEvent and steals focus from the user.
    if agent_mode and windows:
        matched = []
        for entry in windows:
            win = entry["window"]
            if win is None:
                continue
            mode = find_agent_mode_in_window(win)
            if mode and mode.lower() == agent_mode.lower():
                matched.append(entry)
        if matched:
            windows = matched
        else:
            # No window matches yet — either loading or agent_mode wrong.
            # Skip this cycle entirely rather than acting on random windows.
            return config

    # ── Foreground window exclusion ──────────────────────────────────────────
    # Never walk descendants of the window the user is actively using.
    # Walking any non-foreground window fires AutomationFocusChangedEvent.
    # With agent_mode filtering above, this is belt-and-suspenders protection.
    try:
        import win32gui
        focused_handle = win32gui.GetForegroundWindow()
        windows = [w for w in windows if w["handle"] != focused_handle]
    except Exception:
        pass  # win32gui unavailable — skip guard, agent_mode filter is sufficient

    if not windows:
        return config  # all candidate windows are foreground — skip
    # ── Update button ──────────────────────────────────────────────────────
    if triggers.get("update_button") and windows:
        update_debounce = config.get("update_click_debounce_seconds", 30)
        if time.time() - state.last_update_click_time > update_debounce:
            if trigger_update_button(windows):
                state.last_update_click_time = time.time()

    # ── Reload dialog ────────────────────────────────────────────────────────
    if triggers.get("reload_dialog") and windows:
        trigger_reload_dialog(windows)

    # ── Chat timeout Restart ─────────────────────────────────────────────────
    # Text-gated: only fires when "Chat took too long to get ready" is visible.
    # hermes_wake.py (folderOpen task) sends the initial wake message;
    # this picks up the error if Copilot wasn't ready yet.
    if triggers.get("chat_timeout_restart", True) and windows:
        trigger_chat_timeout_restart(windows)

    return config  # return hot-reloaded config for next interval


def run_daemon(config_path):
    """Main daemon loop. Runs until SIGTERM/SIGINT."""
    safe_print(f"[hermes] Daemon started (PID {os.getpid()})")
    safe_print(f"[hermes] Config: {config_path}")

    config = load_config(config_path)
    state = DaemonState()

    def _shutdown(sig, frame):
        safe_print("[hermes] Shutting down")
        clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        try:
            config = poll_once(state, config, config_path)
        except Exception as e:
            safe_print(f"[hermes] Poll error: {e}")
        time.sleep(config.get("poll_interval", 0.8))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hermes idempotent daemon")
    parser.add_argument("--ensure-running", action="store_true",
                        help="Start if not running, exit 0 if already running (default behavior)")
    parser.add_argument("--detach", action="store_true",
                        help="Self-daemonize via DETACHED_PROCESS spawn (works in cmd.exe / any shell)")
    parser.add_argument("--stop", action="store_true", help="Stop the running daemon")
    parser.add_argument("--status", action="store_true", help="Print daemon status")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help=f"Path to config JSON (default: {DEFAULT_CONFIG})")
    args = parser.parse_args()

    alive, pid = is_daemon_running()

    if args.status:
        if alive:
            safe_print(f"running (PID {pid})")
        else:
            safe_print("stopped")
        return

    if args.stop:
        if alive:
            os.kill(pid, signal.SIGTERM)
            safe_print(f"[hermes] Sent SIGTERM to PID {pid}")
            clear_pid()
        else:
            safe_print("[hermes] Not running")
        return

    # Default / --ensure-running: if already alive, exit idempotently.
    # Backgrounding is the caller's job (VS Code task, run_in_terminal isBackground=true).
    if alive:
        safe_print(f"[hermes] Already running (PID {pid}) — exiting")
        return

    if getattr(args, "detach", False):
        # Spawn self without --detach as a detached background process.
        # Works from any shell (cmd.exe, powershell, bash) — no nohup/& needed.
        log_path = SCRIPT_DIR / "hermes_daemon.log"
        with open(log_path, "a", encoding="utf-8") as log_f:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--config", args.config],
                creationflags=DETACHED_PROCESS,
                close_fds=True,
                stdout=log_f,
                stderr=log_f,
                stdin=subprocess.DEVNULL,
            )
        safe_print(f"[hermes] Detached daemon PID {child.pid} (child will self-register)")
        return

    write_pid()
    try:
        run_daemon(args.config)
    finally:
        clear_pid()


if __name__ == "__main__":
    main()
