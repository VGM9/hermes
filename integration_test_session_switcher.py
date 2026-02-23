#!/usr/bin/env python3
"""
integration_test_session_switcher.py

Round-trip integration test for hermes#35 session_switcher.

Protocol:
  1. Find the current VS Code window for this workspace
  2. Record the current agent mode (BEFORE)
  3. Find a SECOND session with a different customTitle
  4. Switch to it via Quick Pick
  5. DETECT: read "Set Agent" button after switch (AFTER)
  6. Assert AFTER != BEFORE (switch happened)
  7. Switch BACK to original session (round-trip)
  8. DETECT: read "Set Agent" button (RESTORED)
  9. Assert RESTORED == BEFORE

This test is fully automated. No human required. The "Set Agent" button
is the telemetry: detect_before → affect_switch → detect_after.

Usage: python3 integration_test_session_switcher.py
Author: AION0 (Binah, patch 45) — TDD fix for hermes#35
"""
import sys
import os
import time
import json
from pathlib import Path

HERMES_DEV = r"C:\www\VGM9\_\AS\0.0.Q\_\repos\hermes-dev"
sys.path.insert(0, HERMES_DEV)

WORKSPACE_HASH = "27d15dd3fe03c43d42ef4aafc54a2c26"
SESSIONS_DIR = Path(
    r"C:\Users\victorb\AppData\Roaming\Code - Insiders\User\workspaceStorage"
) / WORKSPACE_HASH / "chatSessions"

if len(sys.argv) < 2:
    print("Usage: python3 integration_test_session_switcher.py <path/to/current_session.jsonl>", file=sys.stderr)
    sys.exit(1)
CURRENT_SESSION = Path(sys.argv[1]).stem  # derive UUID from JSONL filename


def get_all_sessions_with_titles() -> list[tuple[str, str | None]]:
    """Return list of (jsonl_path, customTitle) for all sessions in workspace."""
    from core.ui_automation.session_switcher import get_session_custom_title
    result = []
    for jsonl in SESSIONS_DIR.glob("*.jsonl"):
        title = get_session_custom_title(str(jsonl))
        result.append((str(jsonl), title))
    return result


def find_alternate_session(current_jsonl: str) -> tuple[str, str] | None:
    """Find a session with a known title that is NOT the current session."""
    from core.ui_automation.session_switcher import get_session_custom_title
    for jsonl in SESSIONS_DIR.glob("*.jsonl"):
        if str(jsonl).endswith(Path(current_jsonl).name):
            continue
        title = get_session_custom_title(str(jsonl))
        if title and title.strip():
            return str(jsonl), title
    return None


def find_workspace_window():
    """Find a VS Code window for the VGM9 workspace."""
    from pywinauto import Desktop
    from vscode_ground_truth import VSCODE_WINDOW_CLASS_NAME
    desktop = Desktop(backend="uia")
    for win in desktop.windows():
        try:
            if win.class_name() != VSCODE_WINDOW_CLASS_NAME:
                continue
            title = win.window_text()
            if "visual studio code" not in title.lower():
                continue
            if "vgm9" in title.lower() or "agent-hub" in title.lower():
                return win
        except Exception:
            continue
    return None


def read_agent_mode(win) -> str | None:
    """Read current 'Set Agent' button label from window."""
    from core.ui_automation.window_detection import find_agent_mode_in_window
    return find_agent_mode_in_window(win)


def run_test():
    print("=== hermes#35 Round-Trip Integration Test ===\n")

    # ── Step 0: inventory sessions ────────────────────────────────────────
    print("Step 0: Inventory available sessions...")
    sessions = get_all_sessions_with_titles()
    print(f"  Found {len(sessions)} sessions")
    for path, title in sessions:
        marker = " ← CURRENT" if CURRENT_SESSION in path else ""
        print(f"  [{Path(path).name[:8]}] {repr(title)}{marker}")

    # ── Step 1: find window ───────────────────────────────────────────────
    print("\nStep 1: Find VS Code window...")
    win = find_workspace_window()
    if not win:
        print("  ❌ No VS Code window found for VGM9 workspace")
        sys.exit(1)
    print(f"  ✅ Window: '{win.window_text()[:60]}'")

    # ── Step 2: record BEFORE state ───────────────────────────────────────
    print("\nStep 2: Read current agent mode (BEFORE)...")
    mode_before = read_agent_mode(win)
    print(f"  BEFORE mode: {repr(mode_before)}")
    if mode_before is None:
        print("  ⚠ No agent mode detected — window may not have a chat panel visible")
        # Don't abort — the switch test can still verify the Quick Pick opens

    # ── Step 3: find alternate session ───────────────────────────────────
    print("\nStep 3: Find alternate session for switch target...")
    current_jsonl = str(SESSIONS_DIR / f"{CURRENT_SESSION}.jsonl")
    alternate = find_alternate_session(current_jsonl)
    if not alternate:
        print("  ❌ No alternate session with a title found")
        sys.exit(1)
    alt_path, alt_title = alternate
    print(f"  Target session: {repr(alt_title)}")
    print(f"  JSONL: {Path(alt_path).name}")

    # ── Step 4: switch to alternate ───────────────────────────────────────
    print("\nStep 4: Switch to alternate session via Quick Pick...")
    from core.ui_automation.session_switcher import switch_to_session_via_quick_pick
    switched = switch_to_session_via_quick_pick(win, alt_title, timeout_ms=2500)
    print(f"  switch_to_session_via_quick_pick returned: {switched}")

    # ── Step 5: detect AFTER state ────────────────────────────────────────
    print("\nStep 5: Read agent mode after switch (AFTER)...")
    time.sleep(0.5)  # allow VS Code to settle
    mode_after = read_agent_mode(win)
    print(f"  AFTER mode: {repr(mode_after)}")

    # ── Step 6: assert change ─────────────────────────────────────────────
    print("\nStep 6: Assert switch occurred...")
    if mode_before is None and mode_after is None:
        print("  ⚠ Both BEFORE and AFTER are None — cannot confirm switch via agent mode")
        print("    Proceeding to round-trip restore anyway")
    elif mode_after != mode_before:
        print(f"  ✅ Mode changed: {repr(mode_before)} → {repr(mode_after)}")
    else:
        print(f"  ❌ Mode did NOT change: still {repr(mode_after)}")
        # Don't abort — attempt restore and report
        pass

    # ── Step 7+8+9: round-trip back ───────────────────────────────────────
    print("\nStep 7-9: Switch BACK to original session (round-trip)...")
    from core.ui_automation.session_switcher import get_session_custom_title
    original_title = get_session_custom_title(current_jsonl)
    print(f"  Original title: {repr(original_title)}")

    if original_title:
        restored = switch_to_session_via_quick_pick(win, original_title, timeout_ms=2500)
        print(f"  switch back returned: {restored}")
        time.sleep(0.5)
        mode_restored = read_agent_mode(win)
        print(f"  RESTORED mode: {repr(mode_restored)}")

        if mode_restored == mode_before:
            print(f"  ✅ Round-trip complete: mode restored to {repr(mode_before)}")
        else:
            print(f"  ❌ Round-trip FAILED: expected {repr(mode_before)}, got {repr(mode_restored)}")
            sys.exit(1)
    else:
        print("  ❌ Cannot restore — original session has no customTitle")
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n=== TEST RESULT ===")
    if mode_after != mode_before:
        print(f"✅ PASS — session switch detected: {repr(mode_before)} → {repr(mode_after)} → {repr(mode_restored)}")
    else:
        print(f"❌ FAIL — session switch not detected (mode unchanged: {repr(mode_before)})")
        print("   Cause: check if Quick Pick opened correctly (timing? palette already open?)")
        sys.exit(1)


if __name__ == "__main__":
    run_test()
