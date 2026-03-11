#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat.send — Message sending utilities

Provides functions for sending messages via the chat interface.
"""

import ctypes
import time
from .input import read_content, clear_input, clipboard_paste, find_send_button, _is_foreground


def _get_system_idle_seconds() -> float:
    """Return seconds since last keyboard or mouse input (system-wide).

    Returns float('inf') on failure so callers fail-open (treat as idle).
    """
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        elapsed_ms = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, elapsed_ms / 1000.0)
    except Exception:
        return float('inf')


# Minimum system idle time required before hermes may inject into ANY window.
# If the user touched keyboard or mouse within this many seconds, we must not
# steal focus or paste anything.
_MIN_SYSTEM_IDLE_SECONDS = 10.0


def send_message(win, message, hermes_prefix="[hermes]"):
    """Acquire focus on win and submit a message into the chat input.

    Safety contract:
      1. Check system-wide idle time first. If the user has touched input
         in the last _MIN_SYSTEM_IDLE_SECONDS, abort — they are present.
      2. Acquire focus with set_focus(). This is an intentional focus steal;
         it must only happen when the user is verifiably idle.
      3. Re-check system idle after set_focus (covers race where user starts
         typing while set_focus is in flight).
      4. Re-check foreground after clipboard paste — before the irrevocable
         Send action.

    Returns:
        True  — delivered
        None  — suppressed: user content in input box (not a failure)
        False — delivery failure, idle check failed, or foreground lost
    """
    # INNER IDLE GATE (hermes#41): user must not have touched keyboard/mouse
    # recently. This is the final safety check before focus acquisition.
    # The outer autopulse loop already checked system_idle_grace_seconds, but
    # that check happened at dispatch time — there is a TOCTOU window between
    # dispatch and execution. This inner gate closes it.
    if _get_system_idle_seconds() < _MIN_SYSTEM_IDLE_SECONDS:
        return False  # user is present — do not steal focus

    # Acquire focus explicitly. Never wait for the user to bring the window
    # to foreground — that would fire on the user at the worst moment.
    try:
        win.set_focus()
    except Exception:
        return False
    time.sleep(0.15)  # brief wait for focus to settle

    # Re-check: if user started typing during set_focus(), abort.
    if _get_system_idle_seconds() < _MIN_SYSTEM_IDLE_SECONDS:
        return False

    # Verify we actually own the foreground after set_focus.
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

    clipboard_paste(win, f"{hermes_prefix} {message}")
    time.sleep(0.2)

    # SAFETY GATE: re-check foreground before the irrevocable send action.
    # Between paste completion and now, focus may have changed. If the user
    # moved to another window, abort — do not fire the message.
    # The pasted text starts with hermes_prefix, so the cleanup branch at
    # the top of send_message will fire and clear it on the next invocation.
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