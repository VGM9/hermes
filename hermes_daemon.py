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
    """Adapter: wraps core discovery, adds pattern filter, normalises to dict."""
    windows = _core_find_windows()
    if pattern:
        windows = [w for w in windows if pattern.lower() in w.title.lower()]
    return [{"handle": w.handle, "title": w.title, "window": None} for w in windows]


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


# ─────────────────────────────────────────────────────────────────────────────
# Trigger: wake on reload
# ─────────────────────────────────────────────────────────────────────────────

def wait_for_chat_ready(window, timeout=30):
    """Wait until chat Edit control is visible, enabled, and clickable. Returns element or None."""
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
        self.reload_in_progress = False   # True once we see a handle disappear
        self.last_wake_time = 0.0


def poll_once(state, config, config_path):
    """One poll cycle. Mutates state. Hot-reloads config."""
    config = load_config(config_path)
    triggers = config["triggers"]
    pattern = config.get("window_pattern")

    windows = find_vscode_windows(pattern)
    current_handles = {w["handle"] for w in windows}

    # ── Wake-on-reload detection ────────────────────────────────────────────
    if triggers.get("wake_on_reload"):
        debounce = config.get("wake_debounce_seconds", 10)
        lost_handles = state.known_handles - current_handles

        if lost_handles and not state.reload_in_progress:
            safe_print(f"[hermes] Detected window exit — reload in progress")
            state.reload_in_progress = True

        if state.reload_in_progress and current_handles:
            # New window appeared after a reload
            if time.time() - state.last_wake_time > debounce:
                new_windows = [w for w in windows if w["handle"] not in state.known_handles]
                target = new_windows[0] if new_windows else windows[0]
                win = target["window"]
                safe_print(f"[hermes] New window up — waiting for chat ready...")
                chat = wait_for_chat_ready(win, timeout=30)
                if chat:
                    send_wake_message(win, config["wake_msg"])
                    state.last_wake_time = time.time()
                else:
                    safe_print("[hermes] Chat never ready — skipping wake")
            state.reload_in_progress = False

    # ── Update button ────────────────────────────────────────────────────────
    if triggers.get("update_button") and windows:
        clicked = trigger_update_button(windows)
        if clicked:
            state.reload_in_progress = True  # update restart coming

    # ── Reload dialog ────────────────────────────────────────────────────────
    if triggers.get("reload_dialog") and windows:
        trigger_reload_dialog(windows)

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

    write_pid()
    try:
        run_daemon(args.config)
    finally:
        clear_pid()


if __name__ == "__main__":
    main()
