#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wake.py — Post-reload wake CLI

Slim CLI for post-reload wake. Handles lock acquisition, readiness wait,
and message sending.
"""

import json
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
    """Load JSONC config with local overlay. Same pattern as hermes_daemon.load_config."""
    defaults = {
        "wake_msg": "Window reloaded. qhoami",
        "wake_timeout": 30,
        "session_jsonl": "",
        "agent_mode": "",
    }
    def _parse(fpath):
        raw = Path(fpath).read_text(encoding="utf-8")
        stripped = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("/"))
        return json.loads(stripped)
    try:
        data = _parse(path)
        merged = {**defaults, **data}
        local_path = Path(path).parent / "hermes_config.local.jsonc"
        if local_path.exists():
            try:
                merged.update(_parse(local_path))
            except Exception as le:
                log(f"[hermes:wake] Local config error: {le} — ignored")
        # Resolve session_jsonl from autopulse.targets if not set at top level
        if not merged.get("session_jsonl"):
            agent_mode = merged.get("agent_mode", "")
            for t in merged.get("autopulse", {}).get("targets", []):
                if t.get("agent_mode") == agent_mode:
                    merged["session_jsonl"] = t.get("session_jsonl", "")
                    break
        return merged
    except Exception as e:
        log(f"[hermes:wake] Config load error: {e} — using defaults")
        return defaults

def main():
    config = load_config(SCRIPT_DIR / "hermes_config.jsonc")
    message = config["wake_msg"]
    timeout = config["wake_timeout"]
    session_jsonl = config["session_jsonl"]
    agent_mode = config["agent_mode"]

    with WakeLock():
        win = find_target_window(session_jsonl, agent_mode)
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