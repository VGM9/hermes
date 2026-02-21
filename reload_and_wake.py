#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HERMES Reload-and-Wake
======================
Orchestrates the full VS Code reload lifecycle for agentic contexts.

  Phase 0 — UPDATE:   Detect and click VS Code's "Update is ready" status bar button.
                      Use when a VS Code update is pending (Electron restart + update install).
  Phase 1 — TRIGGER:  F1 -> Developer: Reload Window (FALLBACK ONLY — hijacks focus).
                      Prefer qopilot/execute_command{workbench.action.reloadWindow} instead.
  Phase 2 — CONFIRM:  Watch for "A chat request is in progress" dialog, click Yes.
  Phase 3 — WAKE:     After old window DIES and new window LIVES and chat is READY,
                      send the wake message.

The critical timing contract:
  - Do NOT attempt Phase 3 until the old window handle is provably dead.
  - Do NOT type until the chat Edit control is visible, enabled, AND interactive.

Common usage:
    # VS Code update available: detect+click update button, handle dialog, folderOpen wakes
    python reload_and_wake.py --phases 0,2

    # Detect only (no click) — for polling:
    python reload_and_wake.py --phases 0 --detect-only

    # Extension-only reload (agent fires command, script handles dialog):
    python reload_and_wake.py --phases 2

    # Fallback (no workspace, agent tool unavailable):
    python reload_and_wake.py --phases 1,2,3 --window-pattern "VGM9"

    # Dry-run to verify window detection:
    python reload_and_wake.py --dry-run

Author: POLARIS1 (0.0.13), 2026-02-19
Revised: same session — fixed Phase 3 timing (was typing into dying window)
"""

import sys
import time
import argparse
import json
from pathlib import Path

from core.ui_automation.window_detection import find_target_window, is_foreground
from chat.input import wait_for_chat_ready
from chat.send import send_message as chat_send_message

# Check dependencies before importing
try:
    import pywinauto
    from pywinauto import Application, findwindows
except ImportError:
    print("ERROR: pywinauto not installed")
    print("  pip install pywinauto")
    sys.exit(1)

DEFAULT_WAKE_MSG = "Window reloaded. #qhoami"
VSCODE_CLASS = "Chrome_WidgetWin_1"


def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0: Detect and click VS Code update button
# ─────────────────────────────────────────────────────────────────────────────

# Fragments that identify the update status bar button across VS Code versions
_UPDATE_BUTTON_FRAGMENTS = [
    "update available",
    "restart to update",
    "click to restart",
    "update is ready",
    "restart required",
]


def scan_for_update_button(windows):
    """Search all VS Code windows for the update/restart status bar button.

    Returns the pywinauto element if found, or None.
    Searches all clickable elements (Button, MenuItem, Custom) whose name
    contains any of the known update-notification fragments.
    """
    for entry in windows:
        win = entry["window"]
        try:
            for ctrl_type in ("Button", "MenuItem", "Custom", "Text"):
                for elem in win.descendants(control_type=ctrl_type):
                    try:
                        name = (elem.element_info.name or "").lower()
                        if any(frag in name for frag in _UPDATE_BUTTON_FRAGMENTS):
                            safe_print(f"[Phase 0] Found update button: '{elem.element_info.name}'")
                            return elem
                    except Exception:
                        pass
        except Exception:
            pass
    return None


def click_update_button(session_jsonl, agent_mode, detect_only=False):
    """Find and click the VS Code update status bar button.

    Uses session-anchored targeting to locate the window.
    If detect_only=True, reports presence without clicking.
    Returns True if button was found (and clicked if not detect_only).
    """
    safe_print("[Phase 0] Scanning for VS Code update button...")
    win = find_target_window(session_jsonl, agent_mode)
    if win is None:
        safe_print("[Phase 0] No target window found")
        return False

    windows = [{"window": win}]
    btn = scan_for_update_button(windows)
    if btn:
        if detect_only:
            safe_print("[Phase 0] Update button detected (--detect-only, not clicking)")
            return True
        try:
            btn.click_input()
            safe_print("[Phase 0] Update button clicked — VS Code update restart triggered")
            return True
        except Exception as e:
            safe_print(f"[Phase 0] Click failed: {e}")
            return False

    safe_print("[Phase 0] No update button found")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Trigger reload
# ─────────────────────────────────────────────────────────────────────────────

def trigger_reload(window, title):
    """Open command palette in target window and run Developer: Reload Window.

    NOTE: This is a FALLBACK path (Phase 1). Prefer sending
    workbench.action.reloadWindow via qopilot/execute_command, which does not
    require focus acquisition and carries no wrong-window risk.
    """
    safe_print(f"[Phase 1] Triggering reload in: {title[:60]}...")
    window.set_focus()
    time.sleep(0.4)

    # SAFETY GATE: verify we own the foreground before typing anything.
    # If another window grabbed focus while set_focus() ran, abort.
    if not is_foreground(window):
        safe_print("[Phase 1] Foreground not acquired — aborting reload trigger")
        return

    # Open command palette. window.type_keys is window-scoped (not global).
    window.type_keys("{F1}")
    time.sleep(0.6)

    window.type_keys("Developer: Reload Window", with_spaces=True, pause=0.02)
    time.sleep(0.4)

    window.type_keys("{ENTER}")
    time.sleep(0.3)
    safe_print("[Phase 1] Reload command sent")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Confirm the "chat in progress" dialog
# ─────────────────────────────────────────────────────────────────────────────

def confirm_reload_dialog(timeout=12):
    """Watch for the 'A chat request is in progress' dialog and click Yes.

    VS Code shows this modal when you reload while a chat session is active.
    Dialog text fragment: "chat request is in progress".
    Button text: "Yes" (or similar).

    Returns True if dialog was found and confirmed, False if timeout.
    """
    safe_print(f"[Phase 2] Watching for reload dialog (up to {timeout}s)...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            desktop = pywinauto.Desktop(backend="uia")
            for win in desktop.windows():
                try:
                    if "Visual Studio Code" not in win.window_text():
                        continue
                    descendants = win.descendants()
                    texts = [d.window_text().lower() for d in descendants if d.window_text()]

                    # Check if dialog text is present
                    if any("chat request is in progress" in t or
                           "a chat session is in progress" in t or
                           "reload window" in t
                           for t in texts):
                        # Find Yes/Reload/OK button
                        for btn in win.descendants(control_type="Button"):
                            btn_text = btn.window_text()
                            if btn_text.lower() in ("yes", "reload", "ok", "restart"):
                                safe_print(f"[Phase 2] Found dialog, clicking '{btn_text}'")
                                btn.click_input()
                                safe_print("[Phase 2] Dialog confirmed")
                                return True
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.3)

    safe_print("[Phase 2] No dialog found within timeout (may not have appeared)")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Wait for reload and send wake message
# ─────────────────────────────────────────────────────────────────────────────

def wait_for_window_death(old_window, timeout=15):
    """Wait until the old window handle stops responding. Returns True if died."""
    safe_print(f"[Phase 3] Waiting for old window to close (up to {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        if not window_handle_alive(old_window):
            safe_print(f"[Phase 3] Old window closed after {time.time()-start:.1f}s")
            return True
        time.sleep(0.25)
    safe_print("[Phase 3] WARNING: old window never died within timeout")
    return False


def wait_for_new_window(session_jsonl, agent_mode, timeout=20):
    """Poll for reloaded VS Code window via session-anchored targeting."""
    safe_print(f"[Phase 3] Waiting for reloaded window (up to {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        win = find_target_window(session_jsonl, agent_mode)
        if win is not None:
            safe_print(f"[Phase 3] New window appeared: {win.window_text()[:60]}")
            return win, win.window_text()
        time.sleep(0.4)
    safe_print("[Phase 3] Timeout waiting for new window")
    return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ─────────────────────────────────────────────────────────────────────────────

def load_config(path):
    """Load JSONC config file, stripping comments."""
    with open(path, 'r') as f:
        content = f.read()
    content = '\n'.join(line for line in content.splitlines() if not line.strip().startswith('//'))
    return json.loads(content)


def run(phases, config_path, wake_msg, reload_timeout, dialog_timeout, dry_run, detect_only=False):
    config = load_config(config_path)
    session_jsonl = config.get("autopulse", {}).get("session_jsonl", "")
    agent_mode = config.get("agent_mode", "").strip()

    win = find_target_window(session_jsonl, agent_mode)
    if win is None:
        safe_print(f"ERROR: No window found for agent_mode='{agent_mode}'")
        return 1

    title = win.window_text()
    safe_print(f"Target window: {title[:70]}")

    if dry_run:
        safe_print(f"[DRY RUN] Would execute phases: {phases}")
        if 0 in phases:
            safe_print(f"  Phase 0: Scan VS Code windows for update/restart status bar button")
        if 1 in phases:
            safe_print(f"  Phase 1 (FALLBACK): F1 -> 'Developer: Reload Window' [prefer qopilot/execute_command instead]")
        if 2 in phases:
            safe_print(f"  Phase 2: Watch {dialog_timeout}s for reload dialog, click Yes")
        if 3 in phases:
            safe_print(f"  Phase 3: Wait for old window to DIE -> new window to LIVE -> "
                       f"chat to be READY -> send: '{wake_msg}'")
        return 0

    if 0 in phases:
        found = click_update_button(session_jsonl, agent_mode, detect_only=detect_only)
        if not found and not detect_only:
            safe_print("[Phase 0] No update button — nothing to click")
            return 1

    if 1 in phases:
        trigger_reload(win, title)

    if 2 in phases:
        confirm_reload_dialog(dialog_timeout)

    if 3 in phases:
        if 2 in phases:
            wait_for_window_death(win, timeout=15)
            new_win, new_title = wait_for_new_window(session_jsonl, agent_mode, timeout=reload_timeout)
        else:
            safe_print("[Phase 3] Running post-reload (folderOpen mode) — skipping window death wait")
            new_win, new_title = win, title

        if not new_win:
            safe_print("ERROR: Window did not reappear after reload")
            return 1

        chat_input = wait_for_chat_ready(new_win, timeout=30)
        if not chat_input:
            safe_print("ERROR: Chat input never became ready")
            return 1

        ok = chat_send_message(new_win, wake_msg)
        if ok:
            safe_print("\nDone. Extension loaded, wake message sent.")
            return 0
        else:
            safe_print("\nReload completed but wake message failed.")
            return 2

    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Confirm reload dialog + send wake message after VS Code window reload"
    )
    parser.add_argument(
        "--phases", default="2",
        help="Comma-separated phases to run: 1=trigger(fallback),2=confirm,3=wake "
             "(default: 2 — Phase 3 is handled by folderOpen task when in a workspace; "
             "use 2,3 only as fallback outside a workspace)"
    )
    parser.add_argument(
        "--config", default=str(Path(__file__).parent / "hermes_config.jsonc"),
        help="Path to hermes_config.jsonc (default: hermes_config.jsonc in script directory)"
    )
    parser.add_argument(
        "--wake-msg", default=DEFAULT_WAKE_MSG,
        help=f"Message to send after reload (default: '{DEFAULT_WAKE_MSG}')"
    )
    parser.add_argument(
        "--reload-timeout", type=int, default=25,
        help="Seconds to wait for new window after reload (default: 25)"
    )
    parser.add_argument(
        "--dialog-timeout", type=int, default=12,
        help="Seconds to watch for reload confirmation dialog (default: 12)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen, don't execute"
    )
    parser.add_argument(
        "--detect-only", action="store_true",
        help="Phase 0: report if update button exists without clicking it"
    )
    args = parser.parse_args()

    phases = [int(p.strip()) for p in args.phases.split(",") if p.strip().isdigit()]

    sys.exit(run(
        phases=phases,
        config_path=args.config,
        wake_msg=args.wake_msg,
        reload_timeout=args.reload_timeout,
        dialog_timeout=args.dialog_timeout,
        dry_run=args.dry_run,
        detect_only=args.detect_only,
    ))

if __name__ == "__main__":
    main()
