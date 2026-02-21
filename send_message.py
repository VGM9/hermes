#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send_message.py — Active-session message delivery CLI

Delivers a message to a specific VS Code agent session identified by
session JSONL path + agent mode name.

Usage:
    send_message.py <message> [--session-jsonl <path>] [--agent-mode <name>]

If --session-jsonl / --agent-mode are omitted, reads them from
hermes_config.local.jsonc (or hermes_config.jsonc as fallback).

Fixes hermes#17: previous version had hardcoded placeholder args
("session.jsonl", "agent_mode") that caused every autopulse to fail silently.
"""

import sys
import os
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def load_config():
    """Load merged hermes config (local overrides base)."""
    import json
    import re

    def _load_jsonc(path):
        """Load JSONC (JSON with // comments)."""
        text = Path(path).read_text(encoding="utf-8")
        # Strip single-line // comments
        text = re.sub(r"//[^\n]*", "", text)
        return json.loads(text)

    base = {}
    local = {}
    base_path = SCRIPT_DIR / "hermes_config.jsonc"
    local_path = SCRIPT_DIR / "hermes_config.local.jsonc"

    if base_path.exists():
        base = _load_jsonc(base_path)
    if local_path.exists():
        local = _load_jsonc(local_path)

    # Deep merge: local overrides base
    merged = {**base}
    for k, v in local.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


def main():
    parser = argparse.ArgumentParser(description="Send a message to a VS Code agent session.")
    parser.add_argument("message", help="Message text to deliver")
    parser.add_argument("--session-jsonl", default=None,
                        help="Path to the session JSONL file (for window targeting)")
    parser.add_argument("--agent-mode", default=None,
                        help="Agent mode name shown in the 'Set Agent' button")
    args = parser.parse_args()

    session_jsonl = args.session_jsonl
    agent_mode = args.agent_mode

    # Fall back to config if not provided on CLI
    if not session_jsonl or not agent_mode:
        config = load_config()
        if not session_jsonl:
            session_jsonl = config.get("autopulse", {}).get("session_jsonl", "")
        if not agent_mode:
            agent_mode = config.get("agent_mode", "")

    if not session_jsonl or not agent_mode:
        print("[send_message] ERROR: --session-jsonl and --agent-mode required "
              "(or set in hermes_config.local.jsonc)", file=sys.stderr)
        sys.exit(1)

    from chat import send_message
    from core.ui_automation.window_detection import find_target_window

    win = find_target_window(session_jsonl, agent_mode)
    if not win:
        print(f"[send_message] No target window found for agent_mode={agent_mode!r}", file=sys.stderr)
        sys.exit(1)

    if not send_message(win, args.message):
        print("[send_message] Failed to send message.", file=sys.stderr)
        sys.exit(1)

    print(f"[send_message] Message delivered to {agent_mode!r}.")


if __name__ == "__main__":
    main()