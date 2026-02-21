#!/usr/bin/env python3
"""
spawn_sidecar.py — Deliberate sidecar session spawn

Implements the deliberate sidecar spawn protocol from ___/protocols/SEMVER.md:
  1. Find a VS Code window that does NOT already have the target agent mode
  2. Click the "Set Agent" button → opens the agent picker
  3. Type the target agent name → filter the picker
  4. Press Enter → mode switches
  5. Verify mode switch via find_agent_mode_in_window()
  6. Deliver the mandate message into the now-switched window

Usage:
    python3 spawn_sidecar.py --agent POLARIS1 --mandate "Your initial mandate here"

Options:
    --agent       Target agent mode name (must match .agent.md filename stem)
    --mandate     Initial mandate message delivered after mode switch
    --workspace   Workspace name substring to constrain window search
                  (default: all VS Code windows are candidates)
    --dry-run     Find the target window and print its title, but do not switch

Exit codes:
    0  — spawned and mandate delivered
    1  — no suitable window found
    2  — mode switch failed (window found but agent mode did not change)
    3  — mandate delivery failed
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pywinauto import Desktop
from core.ui_automation.window_detection import find_agent_mode_in_window, VSCODE_WINDOW_CLASS_NAME, is_foreground
from chat.send import send_message


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_spawn_target(target_mode: str, workspace_hint: str = "") -> object:
    """Return a VS Code window that does NOT have target_mode active.

    Preference order:
      1. Window with NO agent mode set (empty sidebar / fresh session)
      2. Window with a different agent mode set

    Excludes: windows already running target_mode.

    Args:
        target_mode:    Agent mode we want to switch TO (e.g. "POLARIS1")
        workspace_hint: Optional substring to filter window titles

    Returns:
        pywinauto Window object, or None if no suitable window found.
    """
    desktop = Desktop(backend="uia")
    no_mode_candidates = []
    other_mode_candidates = []

    for win in desktop.windows():
        try:
            if win.class_name() != VSCODE_WINDOW_CLASS_NAME:
                continue
            title = win.window_text()
            # Chrome_WidgetWin_1 matches ALL Electron apps (draw.io, Slack, etc.)
            # Require "Visual Studio Code" in title to ensure it's actually VS Code.
            if "visual studio code" not in title.lower():
                continue
            if workspace_hint and workspace_hint.lower() not in title.lower():
                continue
            current_mode = find_agent_mode_in_window(win)
            if current_mode and current_mode.lower() == target_mode.lower():
                continue  # already has target mode — not a spawn target
            if not current_mode:
                no_mode_candidates.append(win)
            else:
                other_mode_candidates.append(win)
        except Exception:
            continue

    # Prefer windows without an agent mode set (fresh / empty sidebar)
    if no_mode_candidates:
        return no_mode_candidates[0]
    if other_mode_candidates:
        return other_mode_candidates[0]
    return None


def _click_set_agent_button(win) -> bool:
    """Click the 'Set Agent (Ctrl+.) - ...' button to open the agent picker.

    Returns True if the button was found and clicked, False otherwise.
    """
    try:
        for btn in win.descendants(control_type="Button"):
            name = (btn.element_info.name or "").strip()
            if name.startswith("Set Agent"):
                btn.click_input()
                return True
    except Exception:
        pass
    return False


def _switch_agent_mode(win, target_mode: str, timeout: float = 5.0) -> bool:
    """Click the Set Agent button, type the mode name, press Enter, verify.

    SAFETY: Verifies win is the foreground window before any keystroke injection.
    Returns False immediately (no keys sent) if another window is in front.
    """
    # SAFETY GATE: verify we own the foreground before click_input steals focus
    # into an already-active window. If the user is typing in this window, bail.
    if not is_foreground(win):
        return False

    if not _click_set_agent_button(win):
        return False

    # Give the picker time to open
    time.sleep(0.4)

    # SAFETY GATE: check we still own foreground before typing
    if not is_foreground(win):
        # Picker may be open — close it without typing
        try:
            win.type_keys("{ESCAPE}")
        except Exception:
            pass
        return False

    # Type the agent name to filter the list
    try:
        win.type_keys(target_mode, with_spaces=True)
    except Exception:
        return False

    time.sleep(0.3)

    # SAFETY GATE: check foreground before sending Enter
    if not is_foreground(win):
        try:
            win.type_keys("{ESCAPE}")
        except Exception:
            pass
        return False

    # Press Enter to confirm selection
    try:
        win.type_keys("{ENTER}")
    except Exception:
        return False

    # Poll until mode switch is confirmed
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.5)
        current = find_agent_mode_in_window(win)
        if current and current.lower() == target_mode.lower():
            return True

    return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Spawn a deliberate sidecar agent session in an available VS Code window."
    )
    parser.add_argument("--agent", required=True,
                        help="Target agent mode name (e.g. POLARIS1)")
    parser.add_argument("--mandate", required=True,
                        help="Initial mandate message to deliver after mode switch")
    parser.add_argument("--workspace", default="",
                        help="Window title substring to constrain search (optional)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Find window but do not switch mode or deliver mandate")
    args = parser.parse_args()

    target_mode = args.agent.strip()
    mandate = args.mandate.strip()

    # Step 1: Find a suitable window
    win = _find_spawn_target(target_mode, workspace_hint=args.workspace)
    if win is None:
        print(f"[spawn_sidecar] ERROR: no suitable window found for agent '{target_mode}'", file=sys.stderr)
        print("[spawn_sidecar] All VS Code windows may already have this agent mode, or none exist.", file=sys.stderr)
        sys.exit(1)

    print(f"[spawn_sidecar] Found spawn target: '{win.window_text()}'")
    current_mode = find_agent_mode_in_window(win) or "(none)"
    print(f"[spawn_sidecar] Current mode: {current_mode} → switching to: {target_mode}")

    if args.dry_run:
        print("[spawn_sidecar] Dry run — no changes made.")
        sys.exit(0)

    # Step 2–5: Switch to target agent mode
    print(f"[spawn_sidecar] Clicking Set Agent button and selecting '{target_mode}'...")
    if not _switch_agent_mode(win, target_mode):
        print(f"[spawn_sidecar] ERROR: mode switch to '{target_mode}' failed or timed out.", file=sys.stderr)
        print("[spawn_sidecar] Window may not have this agent mode installed, or picker didn't open.", file=sys.stderr)
        sys.exit(2)

    print(f"[spawn_sidecar] Mode switched confirmed: {target_mode}")

    # Step 6: Deliver mandate
    time.sleep(0.5)  # brief pause for chat input to initialize
    print(f"[spawn_sidecar] Delivering mandate...")
    result = send_message(win, mandate)
    if result is False:
        print("[spawn_sidecar] ERROR: mandate delivery failed.", file=sys.stderr)
        sys.exit(3)
    if result is None:
        print("[spawn_sidecar] WARNING: mandate suppressed (user content in input box). Sidecar mode switched but mandate not delivered.")
        sys.exit(0)

    print(f"[spawn_sidecar] Sidecar spawned successfully.")
    print(f"[spawn_sidecar]   Agent:   {target_mode}")
    print(f"[spawn_sidecar]   Mandate: {mandate[:80]}{'...' if len(mandate) > 80 else ''}")
    sys.exit(0)


if __name__ == "__main__":
    main()
