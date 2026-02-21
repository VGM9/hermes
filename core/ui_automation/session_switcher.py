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

    Flow:
      1. Set focus to the VS Code window.
      2. Open command palette: Ctrl+Shift+P.
      3. Type 'workbench.action.chat.history' + Enter to open the Quick Pick.
      4. Type the session title prefix to filter.
      5. Press Enter to select the first match.
      6. Wait for the session to load.

    Args:
        win: pywinauto Window object for the target VS Code window.
        session_title: The exact customTitle of the session to switch to.
        timeout_ms: Total wait budget in milliseconds (default 1500 = 1.5s).

    Returns:
        True if the Quick Pick sequence completed without exceptions.
        The caller should verify the "Set Agent" button after returning.
    """
    from pywinauto.keyboard import send_keys  # type: ignore[import]

    wait_unit = timeout_ms / 1000 / 5  # divide budget into 5 parts

    try:
        win.set_focus()
        time.sleep(wait_unit)  # wait for focus

        # Open command palette
        send_keys("^+p")
        time.sleep(wait_unit)  # wait for palette to render

        # Type command ID — direct ID is locale-independent
        for char in "workbench.action.chat.history":
            send_keys(char, pause=0.02)
        time.sleep(wait_unit)

        send_keys("{ENTER}")
        time.sleep(wait_unit)  # wait for Quick Pick to open

        # Filter by session title — type first 30 chars (enough to be unique)
        filter_text = session_title[:30]
        for char in filter_text:
            # Escape braces for send_keys
            if char in ("{", "}"):
                send_keys("{%s}" % char, pause=0.02)
            else:
                send_keys(char, pause=0.02)
        time.sleep(wait_unit)

        send_keys("{ENTER}")
        time.sleep(wait_unit / 2)  # wait for session load

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
