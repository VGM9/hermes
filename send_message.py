#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send_message.py — Active-session message delivery CLI

Slim CLI for delivering messages to active sessions.
"""

import sys
from chat import send_message
from core.ui_automation.window_detection import find_target_window

def main():
    if len(sys.argv) < 2:
        print("Usage: send_message.py <message>")
        sys.exit(1)

    message = sys.argv[1]
    win = find_target_window("session.jsonl", "agent_mode")
    if not win:
        print("No target window found.")
        sys.exit(1)

    if not send_message(win, message):
        print("Failed to send message.")
        sys.exit(1)

    print("Message sent successfully.")

if __name__ == "__main__":
    main()