#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes Daemon
=============
Idempotent always-on background process. Monitors VS Code windows and acts
on configured triggers without human intervention.

Triggers (all toggled via hermes_config.json, hot-reloaded each poll cycle):

  update_button   — Detect and click VS Code "Update is ready" status bar button
  reload_dialog   — Detect and click "A chat request is in progress" cancel dialog
  wake_on_reload  — Detect window reload/restart, wait for chat, send wake message

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
    """Load config JSON, return dict. Returns defaults on any error."""
    defaults = {
        "triggers": {"update_button": True, "reload_dialog": True, "wake_on_reload": True},
        "wake_msg": "Window reloaded. #qhoami",
        "poll_interval": 0.8,
        "window_pattern": "VGM9",
        "wake_debounce_seconds": 10,
    }
    try:
        raw = Path(path).read_text(encoding="utf-8")
        # Strip // line comments for .jsonc compatibility
        stripped = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("/"))
        data = json.loads(stripped)
        # Merge with defaults so missing keys don't crash
        merged = {**defaults, **data}
        merged["triggers"] = {**defaults["triggers"], **data.get("triggers", {})}
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

            # Fall back: accessible name scan for retry/regenerate icon
            for btn in win.descendants(control_type="Button"):
                name = (btn.element_info.name or "").lower()
                if any(k in name for k in ("retry", "regenerate", "try again", "resend")):
                    btn.click_input()
                    safe_print(f"[hermes] Clicked chat retry icon: '{btn.element_info.name}'")
                    return True
        except Exception:
            pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Trigger: wake on reload
# ─────────────────────────────────────────────────────────────────────────────

def wait_for_chat_ready(window, timeout=45):
    """Wait until chat Edit control is visible and enabled.

    Sends as soon as the input is interactable. If Copilot extension isn't
    connected yet, the send will fail with a timeout error — the
    trigger_chat_timeout_restart trigger handles recovery automatically.
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            for edit in window.descendants(control_type="Edit"):
                name = (edit.element_info.name or "").lower()
                cls = edit.element_info.class_name or ""
                if "chat input" in name or cls == "native-edit-context":
                    if edit.is_visible() and edit.is_enabled():
                        try:
                            edit.click_input()
                            return edit
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(0.5)
    return None


def send_wake_message(window, message):
    """Type and send wake message into the focused chat input."""
    try:
        escaped = (message
                   .replace("{", "{{").replace("}", "}}")
                   .replace("+", "{+}").replace("^", "{^}")
                   .replace("%", "{%}").replace("~", "{~}"))
        window.type_keys(escaped, with_spaces=True, pause=0.02)
        time.sleep(0.3)
        window.type_keys("{ENTER}")
        safe_print(f"[hermes] Wake message sent: '{message}'")
        return True
    except Exception as e:
        safe_print(f"[hermes] Wake message failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Poll loop state and main loop
# ─────────────────────────────────────────────────────────────────────────────

class DaemonState:
    def __init__(self):
        self.known_handles = set()
        self.reload_pending = False       # a reload was detected (handles disappeared)
        self.wake_sent = False            # wake message was sent; retry handler is active until chat responds
        self.woken_handles = set()        # handles already woken — never re-wake the same handle
        self.last_update_click_time = 0.0  # debounce: don't click update button repeatedly


def has_existing_session() -> bool:
    """Return True if AppData contains at least one session with requests > 0.

    Prevents wake from firing into an empty/new chat panel when the real
    session is in a different window (e.g., popped out). Ground-truth check
    via filesystem — no UI guesswork. See VSQode/hermes#5.
    """
    try:
        from hermes_config import get_appdata_path
        workspace_storage = get_appdata_path()
        for hash_dir in workspace_storage.iterdir():
            if not hash_dir.is_dir():
                continue
            sessions_dir = hash_dir / 'chatSessions'
            if not sessions_dir.exists():
                continue
            for session_file in sessions_dir.glob('*.jsonl'):
                try:
                    last_line = None
                    with open(session_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            last_line = line
                    if last_line:
                        data = json.loads(last_line)
                        requests = data.get('v', {}).get('requests', [])
                        if len(requests) > 0:
                            return True
                except Exception:
                    continue
    except Exception as e:
        safe_print(f"[hermes] Session guard check failed: {e} — proceeding anyway")
        return True  # fail open: if we can't check, don't block the wake
    return False


def poll_once(state, config, config_path):
    """One poll cycle. Mutates state. Hot-reloads config."""
    config = load_config(config_path)
    triggers = config["triggers"]
    pattern = config.get("window_pattern")

    windows = find_vscode_windows(pattern)
    current_handles = {w["handle"] for w in windows}

    # ── Wake-on-reload detection ────────────────────────────────────────────────
    # Event-driven: fires ONCE per new handle, only after a reload_pending event.
    # woken_handles guarantees no re-fire on the same handle.
    if triggers.get("wake_on_reload"):
        lost_handles = state.known_handles - current_handles

        if lost_handles:
            safe_print(f"[hermes] Detected window exit — reload pending")
            state.reload_pending = True
            state.woken_handles -= lost_handles  # gone handles no longer woken

        if state.reload_pending and current_handles:
            # Guard: only fire if AppData shows a session with conversation history.
            # Prevents waking into an empty panel when the real session is in another window.
            if not has_existing_session():
                safe_print("[hermes] No existing session found in AppData — skipping wake (empty window guard)")
            else:
                unwoken = [w for w in windows if w["handle"] not in state.woken_handles]
                for entry in unwoken:
                    win = entry["window"]
                    if win is None:
                        continue
                    safe_print(f"[hermes] New window up — waiting for chat ready...")
                    chat = wait_for_chat_ready(win, timeout=30)
                    if chat:
                        send_wake_message(win, config["wake_msg"])
                        state.woken_handles.add(entry["handle"])
                        state.reload_pending = False
                        state.wake_sent = True  # retry handler now active
                    else:
                        safe_print("[hermes] Chat never ready — skipping wake")
                    break  # one window per poll cycle

    # ── Update button ──────────────────────────────────────────────────────
    if triggers.get("update_button") and windows:
        update_debounce = config.get("update_click_debounce_seconds", 30)
        if time.time() - state.last_update_click_time > update_debounce:
            clicked = trigger_update_button(windows)
            if clicked:
                state.reload_pending = True  # update restart coming
                state.last_update_click_time = time.time()

    # ── Reload dialog ────────────────────────────────────────────────────────
    if triggers.get("reload_dialog") and windows:
        trigger_reload_dialog(windows)

    # ── Chat timeout Restart ─────────────────────────────────────────────────
    # Active only after wake_sent — prevents clicking Regenerate on normal responses.
    # Clears wake_sent on success, so retries stop once the error is resolved.
    if triggers.get("chat_timeout_restart", True) and windows and state.wake_sent:
        if trigger_chat_timeout_restart(windows):
            state.wake_sent = False

    state.known_handles = current_handles
    return config  # return hot-reloaded config for next interval


def run_daemon(config_path):
    """Main daemon loop. Runs until SIGTERM/SIGINT."""
    safe_print(f"[hermes] Daemon started (PID {os.getpid()})")
    safe_print(f"[hermes] Config: {config_path}")

    config = load_config(config_path)
    state = DaemonState()
    # Warm up known handles without triggering wake
    state.known_handles = {w["handle"] for w in find_vscode_windows(config.get("window_pattern"))}

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
