#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wake.py — Post-reload wake CLI

Slim CLI for post-reload wake. Handles lock acquisition, readiness wait,
and message sending.
"""

import sys
from pathlib import Path
from chat import send_message, wait_for_chat_ready
from chat.lock import WakeLock
from core.ui_automation.window_detection import find_target_window

SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / "hermes_daemon.log"

def log(msg):
    line = msg if msg.startswith("[hermes") else f"[hermes:wake] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)

def load_config(path):
    defaults = {
        "wake_msg": "Window reloaded. qhoami",
        "wake_timeout": 30,
    }
    try:
        raw = Path(path).read_text(encoding="utf-8")
        return {**defaults, **json.loads(raw)}
    except Exception:
        return defaults

def main():
    config = load_config(SCRIPT_DIR / "hermes_config.jsonc")
    message = config["wake_msg"]
    timeout = config["wake_timeout"]

    with WakeLock():
        win = find_target_window("session.jsonl", "agent_mode")
        if not win:
            log("No target window found.")
            sys.exit(1)

        chat = wait_for_chat_ready(win, timeout=timeout)
        if not chat:
            log("Chat not ready.")
            sys.exit(1)

        if not send_message(win, message):
            log("Failed to send wake message.")
            sys.exit(1)

        log("Wake message sent successfully.")

if __name__ == "__main__":
    main()