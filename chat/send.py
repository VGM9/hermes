#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat.send — Message sending utilities

Provides functions for sending messages via the chat interface.
"""

import time
from .input import read_content, clear_input, clipboard_paste, find_send_button, _is_foreground

def send_message(win, message, hermes_prefix="[hermes]"):
    """Type and submit a message into the chat input.

    Returns:
        True  — delivered
        None  — suppressed: user content in input box (not a failure)
        False — delivery failure or foreground check failed
    """
    # SAFETY GATE: only operate on the foreground window.
    # If we are not foreground, we must not touch the input box, paste
    # into it, or click Send — any of those would corrupt the user's
    # active work in another window.
    if not _is_foreground(win):
        return False

    try:
        win.type_keys("{ESC}")
    except Exception:
        pass
    time.sleep(0.1)

    existing = (read_content(win) or "").strip()
    if existing:
        if existing.startswith(hermes_prefix):
            clear_input(win)
            time.sleep(0.1)
        else:
            return None  # suppressed: user content present, not a failure

    clipboard_paste(win, message)
    time.sleep(0.2)

    # SAFETY GATE: re-check foreground before the irrevocable send action.
    # Between paste completion and now, focus may have changed. If the user
    # moved to another window, abort — do not fire the message.
    # Note: we leave the pasted text in the input box; the hermes_prefix check
    # at the top of send_message clears it on the next invocation.
    if not _is_foreground(win):
        return False

    btn = find_send_button(win)
    if btn:
        btn.click_input()
    else:
        win.type_keys("{ENTER}")

    deadline = time.time() + 2.0
    while time.time() < deadline:
        time.sleep(0.2)
        if not read_content(win):
            return True
    return True

def send_failure_to_chat(win, reason):
    """Send a failure notice into chat."""
    try:
        chat = wait_for_chat_ready(win, timeout=5)
        if chat:
            send_message(win, f"hermes:wake failed — {reason}")
    except Exception:
        pass