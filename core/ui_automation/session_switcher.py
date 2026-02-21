"""
session_switcher.py — Session switching via VS Code Quick Pick

Implements hermes#35: switch to a specific chat session by its JSONL UUID,
using the workbench.action.chat.history Quick Pick command.

Source analysis (vscode-src agentSessionsPicker.ts):
  - Quick Pick item label = session.label = IChatSessionItem.label = customTitle
  - JSONL field: {"v": {"customTitle": "...", ...}} (first-line snapshot)
  - Command: workbench.action.chat.history (no default keybinding, f1 accessible)
  - Trigger: Ctrl+Shift+P → "workbench.action.chat.history" → Enter
  - Then: type session title prefix → Enter

Author: AION0 (Binah station, patch 45) — VGM9/hermes#35
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from .window_detection import is_foreground


# ── JSONL title extraction ────────────────────────────────────────────────────

def get_session_custom_title(jsonl_path: str) -> Optional[str]:
    """Extract customTitle from a VS Code session JSONL file.

    The JSONL mutation-log format (VS Code 1.109+) stores the full session
    state snapshot as the first JSONL line in {"v": {...}} format.

    Args:
        jsonl_path: Absolute path to the session .jsonl file.

    Returns:
        The session's customTitle string, or None if unreadable/not set.
    """
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                    title = obj.get("v", {}).get("customTitle")
                    if title:
                        return str(title)
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
    except OSError:
        pass
    return None


# ── Quick Pick session switcher ───────────────────────────────────────────────

def switch_to_session_via_quick_pick(win, session_title: str, timeout_ms: int = 1500) -> bool:
    """Switch the active chat session in a VS Code window using the history Quick Pick.

    SAFETY CONTRACT: This function MUST only be called when the caller has
    verified — by its own means — that win is already the foreground window, OR
    the caller has explicit user/agent permission to steal focus.

    DO NOT call this from a polling loop. The daemon's poll_once must NOT call
    find_target_window with session fallback enabled — that would type
    "workbench.action.chat.history" into whatever the user is actively using.

    Flow:
      1. Verify win IS already foreground — if not, abort with no side effects.
      2. Re-confirm foreground after Ctrl+Shift+P.
      3. Type 'workbench.action.chat.history' + Enter.
      4. Re-confirm foreground before filter text.
      5. Type session title prefix + Enter.

    Args:
        win: pywinauto Window object for the target VS Code window.
        session_title: The exact customTitle of the session to switch to.
        timeout_ms: Total wait budget in milliseconds.

    Returns:
        True if the Quick Pick sequence completed without exceptions.
        False if win is not already foreground — zero side effects in that case.
        Caller must verify the 'Set Agent' button state after returning True.
    """
    wait_unit = timeout_ms / 1000 / 5

    try:
        # SAFETY GATE: check foreground BEFORE set_focus.
        # set_focus() itself steals focus — checking after is too late.
        # If win is not already foreground, refuse to proceed entirely.
        # This function must only be called with explicit intent to switch
        # a session in the window the user is already looking at.
        if not is_foreground(win):
            return False

        # Re-assert focus (may be a no-op if already foreground)
        win.set_focus()
        time.sleep(wait_unit)

        # All type_keys calls go to `win` directly (window-scoped in pywinauto)
        # Ctrl+Shift+P — open command palette
        win.type_keys("^+p", pause=0.05)
        time.sleep(wait_unit)

        # Verify still foreground before typing command
        if not is_foreground(win):
            win.type_keys("{ESCAPE}")  # close palette if open
            return False

        # Type command ID and confirm
        win.type_keys("workbench.action.chat.history", pause=0.02, with_spaces=False)
        time.sleep(wait_unit)
        win.type_keys("{ENTER}", pause=0.05)
        time.sleep(wait_unit)  # wait for Quick Pick to open

        # Verify still foreground before typing filter
        if not is_foreground(win):
            win.type_keys("{ESCAPE}")
            return False

        # Filter by session title prefix
        filter_text = session_title[:30]
        win.type_keys(filter_text, pause=0.02, with_spaces=True)
        time.sleep(wait_unit)

        win.type_keys("{ENTER}", pause=0.05)
        time.sleep(wait_unit / 2)

        return True

    except Exception:
        return False


# ── Combined: extract title + switch ─────────────────────────────────────────

def switch_to_session_by_jsonl(win, jsonl_path: str, timeout_ms: int = 2000) -> bool:
    """Convenience wrapper: extract title from JSONL, then switch via Quick Pick.

    Args:
        win: pywinauto Window for the VS Code window.
        jsonl_path: Path to session JSONL file.
        timeout_ms: Total wait budget (default 2s).

    Returns:
        True if switch was attempted (title found + Quick Pick sequence ran).
        Caller must verify "Set Agent" state after returning.
    """
    title = get_session_custom_title(jsonl_path)
    if not title:
        return False
    return switch_to_session_via_quick_pick(win, title, timeout_ms=timeout_ms)
