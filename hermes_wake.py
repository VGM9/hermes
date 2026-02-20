#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hermes_wake.py — One-shot post-reload wake.

Invoked by VS Code's folderOpen task on every workspace open/reload.
Waits (up to wake_timeout seconds) for the Copilot chat extension to
become ready, then sends the configured wake message.

The daemon passively handles retry if the extension reports
"Chat took too long to get ready" — that is its only remaining job
alongside the reload-dialog and update-button triggers.

This script just needs to deliver the message once chat is available.

Exit codes:
  0 — wake message sent
  1 — chat never became ready within timeout

Usage:
    python3 hermes_wake.py [--config path/to/hermes_config.jsonc]
"""

import sys
import time
import json
import argparse
from pathlib import Path

try:
    from pywinauto import Application, findwindows
except ImportError:
    print("[hermes:wake] ERROR: pywinauto not installed. Run: pip install pywinauto")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "hermes_config.jsonc"
VSCODE_CLASS = "Chrome_WidgetWin_1"


def load_config(path=DEFAULT_CONFIG):
    defaults = {
        "wake_msg": "Window reloaded. #qhoami",
        "window_pattern": "VGM9",
        "wake_timeout": 30,
    }
    try:
        raw = Path(path).read_text(encoding="utf-8")
        stripped = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("/"))
        data = json.loads(stripped)
        return {**defaults, **data}
    except Exception as e:
        print(f"[hermes:wake] Config error: {e} — using defaults")
        return defaults


def find_vscode_windows(pattern=None):
    handles = findwindows.find_windows(class_name=VSCODE_CLASS)
    result = []
    for h in handles:
        try:
            app = Application(backend="uia").connect(handle=h)
            win = app.window(handle=h)
            title = win.window_text()
            if pattern and pattern.lower() not in title.lower():
                continue
            result.append({"handle": h, "title": title, "window": win})
        except Exception:
            pass
    return result


def wait_for_chat_ready(win, timeout=30):
    """Block until chat Edit is visible+enabled, or timeout expires."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            for edit in win.descendants(control_type="Edit"):
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


_SEND_BUTTON_NAMES = {"send", "send message", "submit"}


def _find_send_button(win):
    """Return the Send button control, or None."""
    for btn in win.descendants(control_type="Button"):
        name = (btn.element_info.name or "").lower()
        if name in _SEND_BUTTON_NAMES:
            return btn
    return None


def send_wake_message(win, message):
    # Dismiss any open autocomplete/picker before typing.
    win.type_keys("{ESCAPE}")
    time.sleep(0.1)

    escaped = (message
               .replace("{", "{{").replace("}", "}}")
               .replace("+", "{+}").replace("^", "{^}")
               .replace("%", "{%}").replace("~", "{~}"))
    win.type_keys(escaped, with_spaces=True, pause=0.02)
    time.sleep(0.2)

    # Prefer clicking the Send button — avoids Enter being swallowed by
    # any picker that got re-triggered by the message text.
    btn = _find_send_button(win)
    if btn:
        btn.click_input()
    else:
        win.type_keys("{ENTER}")


def main():
    parser = argparse.ArgumentParser(description="Hermes one-shot post-reload wake")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help=f"Path to config JSONC (default: {DEFAULT_CONFIG})")
    args = parser.parse_args()

    config = load_config(args.config)
    pattern = config.get("window_pattern")
    timeout = int(config.get("wake_timeout", 30))
    message = config["wake_msg"]

    windows = find_vscode_windows(pattern)
    if not windows:
        print(f"[hermes:wake] No VS Code window matching '{pattern}' — giving up")
        sys.exit(1)

    win = windows[0]["window"]
    print(f"[hermes:wake] Waiting for chat ready (timeout={timeout}s)...")
    chat = wait_for_chat_ready(win, timeout=timeout)
    if not chat:
        print("[hermes:wake] Chat never ready — timeout exceeded")
        sys.exit(1)

    print(f"[hermes:wake] Sending: '{message}'")
    send_wake_message(win, message)
    print("[hermes:wake] Done")


if __name__ == "__main__":
    main()
