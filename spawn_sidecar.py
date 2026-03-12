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
import ctypes
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from pywinauto import Desktop
from core.ui_automation.window_detection import find_agent_mode_in_window, find_target_window, VSCODE_WINDOW_CLASS_NAME, is_foreground
from chat.input import read_content
from chat.send import send_message

# Minimum system idle required before spawn_sidecar may steal focus.
# Higher than send_message's 10s because agent-mode switching is more disruptive.
_MIN_SPAWN_IDLE_SECONDS = 60.0

_HERMES_PREFIX = "[hermes]"


def _get_system_idle_seconds() -> float:
    """Return seconds since last keyboard or mouse input (system-wide)."""
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        elapsed_ms = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, elapsed_ms / 1000.0)
    except Exception:
        return float('inf')  # fail-open: assume idle


def _restore_foreground(handle: int) -> None:
    """Attempt to return focus to the previously-foreground window."""
    try:
        if handle:
            ctypes.windll.user32.SetForegroundWindow(handle)
    except Exception:
        pass


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

    # Never target the window the user is actively using.
    try:
        fg_handle = int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        fg_handle = 0

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
            # CRITICAL: never touch the window the user is actively working in.
            if fg_handle and int(win.handle) == fg_handle:
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

    Requires win to already be the foreground window. Never calls set_focus();
    focus must be acquired by the caller before this is called.

    Returns True if the button was found and clicked, False otherwise.
    """
    if not is_foreground(win):
        return False
    try:
        for btn in win.descendants(control_type="Button"):
            name = (btn.element_info.name or "").strip()
            if name.startswith("Set Agent"):
                btn.click_input()
                return True
    except Exception:
        pass
    return False


def _switch_agent_mode(win, target_mode: str,
                       saved_fg_handle: int = 0,
                       timeout: float = 5.0) -> bool:
    """Bring win to foreground, click Set Agent button, select target mode, verify.

    SAFETY MODEL:
      1. System idle gate must be checked by caller before invoking this function.
      2. We bring win to foreground explicitly (not waiting for user to do so).
      3. After set_focus(), if focus was lost (user typed), abort immediately.
      4. Capture the mode BEFORE switching so we can detect and report wrong selection.
      5. After ENTER, verify the result; if the wrong agent was selected, ESC + restore.
      6. On any abort, restore focus to saved_fg_handle.

    Returns True iff the switch was confirmed successful.
    """
    # Capture current mode before we touch anything (rollback reference)
    mode_before = find_agent_mode_in_window(win)

    # Bring window to foreground
    try:
        win.set_focus()
    except Exception:
        return False
    time.sleep(0.15)

    # Gate: did we actually get focus?
    if not is_foreground(win):
        _restore_foreground(saved_fg_handle)
        return False

    # Click the Set Agent button (opens the picker dropdown)
    if not _click_set_agent_button(win):
        _restore_foreground(saved_fg_handle)
        return False

    # Wait for picker to open
    time.sleep(0.4)

    # Gate: still foreground? User may have clicked away.
    if not is_foreground(win):
        # Picker is open in an orphaned state — close it
        try:
            win.type_keys("{ESCAPE}")
        except Exception:
            pass
        _restore_foreground(saved_fg_handle)
        return False

    # Type the agent name to filter the picker list
    try:
        win.type_keys(target_mode, with_spaces=True)
    except Exception:
        try:
            win.type_keys("{ESCAPE}")
        except Exception:
            pass
        _restore_foreground(saved_fg_handle)
        return False

    time.sleep(0.3)

    # Gate: still foreground before the irrevocable ENTER?
    if not is_foreground(win):
        try:
            win.type_keys("{ESCAPE}")
        except Exception:
            pass
        _restore_foreground(saved_fg_handle)
        return False

    # Press Enter to confirm selection
    try:
        win.type_keys("{ENTER}")
    except Exception:
        _restore_foreground(saved_fg_handle)
        return False

    # Poll until mode switch is confirmed, with rollback on wrong selection
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.5)
        current = find_agent_mode_in_window(win)
        if current is None:
            continue  # still transitioning
        if current.lower() == target_mode.lower():
            # Success — restore focus to whoever had it before
            _restore_foreground(saved_fg_handle)
            return True
        # Wrong agent selected (default fell through, or wrong picker item).
        # Do NOT leave the window in an unexpected state. Restore mode_before
        # by clicking Set Agent again and selecting it, or just ESC.
        # Best-effort: open picker again, type original mode, confirm.
        if mode_before and current.lower() != mode_before.lower():
            print(
                f"[spawn_sidecar] ROLLBACK: selected '{current}' but wanted '{target_mode}' "
                f"— restoring to '{mode_before}'",
                file=sys.stderr
            )
            try:
                win.set_focus()
                time.sleep(0.1)
                if is_foreground(win):
                    _click_set_agent_button(win)
                    time.sleep(0.4)
                    if is_foreground(win):
                        win.type_keys(mode_before, with_spaces=True)
                        time.sleep(0.3)
                        if is_foreground(win):
                            win.type_keys("{ENTER}")
            except Exception:
                pass
        _restore_foreground(saved_fg_handle)
        return False

    _restore_foreground(saved_fg_handle)
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
    parser.add_argument("--workspace", required=False, default="",
                        help="Window title substring to constrain window search (legacy fallback). "
                             "Use --session-jsonl instead for session-anchored targeting.")
    parser.add_argument("--session-jsonl", dest="session_jsonl", default="",
                        help="Path to the target agent's session JSONL file. Enables session-anchored "
                             "window targeting via find_target_window() (hermes#47). Preferred over "
                             "--workspace because it uniquely identifies the correct VS Code window "
                             "regardless of title substring collisions.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Find window but do not switch mode or deliver mandate")
    args = parser.parse_args()

    if not args.session_jsonl and not args.workspace:
        print("[spawn_sidecar] ERROR: one of --session-jsonl or --workspace must be provided", file=sys.stderr)
        sys.exit(1)

    target_mode = args.agent.strip()
    mandate = args.mandate.strip()

    # Step 1: Find a suitable window
    # Prefer session-anchored targeting (hermes#47) over workspace-hint fallback.
    if args.session_jsonl:
        win = find_target_window(args.session_jsonl.strip(), target_mode)
        if win is None:
            print(f"[spawn_sidecar] ERROR: find_target_window found no window for session-jsonl='{args.session_jsonl}' agent='{target_mode}'", file=sys.stderr)
            print("[spawn_sidecar] Verify the session JSONL path is correct and the agent mode is active.", file=sys.stderr)
            sys.exit(1)
    else:
        # Legacy fallback: workspace-hint title search (pre-#47 behaviour).
        # WARNING: this may target the wrong window if multiple workspaces share
        # a title substring. Use --session-jsonl for reliable targeting.
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

    # SYSTEM IDLE GATE: do not steal focus if user is active.
    # spawn_sidecar requires 60s idle (more disruptive than a pulse).
    idle = _get_system_idle_seconds()
    if idle < _MIN_SPAWN_IDLE_SECONDS:
        print(
            f"[spawn_sidecar] ABORTED: system idle {idle:.1f}s < {_MIN_SPAWN_IDLE_SECONDS}s required.",
            file=sys.stderr
        )
        print("[spawn_sidecar] User is present. Spawn deferred.", file=sys.stderr)
        sys.exit(1)

    # Capture the current foreground handle so we can restore it afterward.
    try:
        saved_fg_handle = int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        saved_fg_handle = 0

    # Step 2–5: Switch to target agent mode
    print(f"[spawn_sidecar] Clicking Set Agent button and selecting '{target_mode}'...")
    if not _switch_agent_mode(win, target_mode, saved_fg_handle=saved_fg_handle):
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
