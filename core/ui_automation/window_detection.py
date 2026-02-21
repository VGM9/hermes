"""
Window Detection Module

Pure functions for finding and identifying VSCode windows.
All identifiers imported from vscode_ground_truth.py.
"""

from typing import List, Optional
import ctypes
import json
import urllib.parse
import pywinauto
from pywinauto import Desktop

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from vscode_ground_truth import (
    VSCODE_WINDOW_CLASS_NAME,
    CONTROL_TYPE_GROUP,
    CONTROL_TYPE_EDIT,
)
from core.data_models.approval_request import WindowInfo


def is_foreground(win) -> bool:
    """Return True only if win IS the current foreground window.

    Use this gate before EVERY keystroke injection point. If any other window
    has keyboard focus, keys go there — not to win. This makes cross-window
    injection structurally impossible: if we are not foreground, we do not type.

    Args:
        win: pywinauto window object.

    Returns:
        True if win.handle == GetForegroundWindow(), False otherwise (including
        on any exception — fail safe, never assume foreground).
    """
    try:
        fg_handle = ctypes.windll.user32.GetForegroundWindow()
        return int(fg_handle) == int(win.handle)
    except Exception:
        return False


def find_agent_mode_in_window(win) -> Optional[str]:
    """Return the active agent mode name for a VS Code chat window, or None.

    VS Code renders a 'Set Agent (Ctrl+.) - AGENTNAME' button in the chat
    input row. This is the only stable, per-window identifier for which
    agent session is active in a given window.

    Confirmed via UIA probe 2026-02-20:
      Main window POLARIS1:  'Set Agent (Ctrl+.) - POLARIS1'
      Floating POLARIS3:     'Set Agent (Ctrl+.) - POLARIS3'

    Args:
        win: pywinauto window object (Application(backend='uia').window(...))

    Returns:
        Agent name string (e.g. 'POLARIS1') or None if not found.
    """
    try:
        for btn in win.descendants(control_type="Button"):
            name = (btn.element_info.name or "").strip()
            if name.startswith("Set Agent") and " - " in name:
                return name.split(" - ", 1)[1].strip()
    except Exception:
        pass
    return None


def find_target_window(session_jsonl: str, expected_agent_mode: str):
    """Return the unique VS Code window hosting a given session + agent mode.

    Implements the session-anchored targeting doctrine (HERMES_WINDOW_DETECTION):
      1. session_jsonl path → workspace hash (from path structure)
      2. workspaceStorage/{hash}/workspace.json → full workspace URI → name
      3. Filter VS Code windows by title containing workspace name
      4. Among those: verify agent_mode via 'Set Agent (Ctrl+.) - NAME' button

    Returns the pywinauto Window object, or None if no unique match found.
    Multiple matches logged but first returned (parent-path disambiguation TODO).
    Zero matches returns None — caller must suppress action.
    """
    from pathlib import Path

    try:
        # Step 1: workspace hash from JSONL path
        # .../workspaceStorage/{hash}/chatSessions/{id}.jsonl
        hash_dir = Path(session_jsonl).parent.parent  # .../workspaceStorage/{hash}/
        workspace_json_path = hash_dir / "workspace.json"
        if not workspace_json_path.exists():
            return None

        ws = json.loads(workspace_json_path.read_text(encoding="utf-8"))
        raw_uri = ws.get("folder") or ws.get("workspace", "")
        if not raw_uri:
            return None

        # Step 2: URI → full filesystem path → workspace name stem
        # "file:///C:/www/VGM9/..." → "C:/www/VGM9/..."
        full_path = urllib.parse.unquote(raw_uri.removeprefix("file:///"))
        workspace_name = Path(full_path).stem  # last segment, no extension

        # Step 3+4: find windows containing workspace name, verify agent_mode
        desktop = Desktop(backend="uia")
        candidates = []
        workspace_windows = []  # all workspace-matching windows (for session switch fallback)
        for win in desktop.windows():
            try:
                if win.class_name() != VSCODE_WINDOW_CLASS_NAME:
                    continue
                title = win.window_text()
                if "visual studio code" not in title.lower():
                    continue  # exclude other Electron apps (draw.io, etc.)
                if workspace_name.lower() not in title.lower():
                    continue
                workspace_windows.append(win)
                agent = find_agent_mode_in_window(win)
                if agent and agent.lower() == expected_agent_mode.lower():
                    candidates.append(win)
            except Exception:
                continue

        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # Multiple matches: parent-path disambiguation not yet implemented.
            # Return first — better than nothing.
            return candidates[0]

        # No window currently shows the expected agent mode.
        # DO NOT attempt to switch sessions here — this function is called from
        # the daemon's poll loop. Typing workbench.action.chat.history into
        # whatever the user is looking at is not recovery. It is corruption.
        # The session switcher path (session_switcher.py) must only be invoked
        # with explicit intent from a user-triggered or agent-triggered action,
        # never from a background poll.
        return None

    except Exception:
        return None


def find_vscode_windows() -> List[WindowInfo]:
    """
    Find all VSCode windows currently open.
    
    Pure function - queries system state but doesn't modify anything.
    
    Returns:
        List of WindowInfo objects representing VSCode windows.
        May be empty if no VSCode windows are open.
    
    Source:
        Uses VSCODE_WINDOW_CLASS_NAME from ground truth.
    """
    desktop = Desktop(backend='uia')
    windows = []
    
    try:
        # Find all windows with VSCode class name
        all_windows = desktop.windows()
        
        for window in all_windows:
            try:
                class_name = window.class_name()
                if class_name == VSCODE_WINDOW_CLASS_NAME:
                    window_info = WindowInfo(
                        handle=window.handle,
                        title=window.window_text(),
                        class_name=class_name,
                        process_id=window.process_id()
                    )
                    windows.append(window_info)
            except Exception:
                # Window may have closed during iteration
                continue
                
    except Exception as e:
        # Desktop enumeration failed - return empty list
        pass
    
    return windows


def has_chat_panel(window_info: WindowInfo) -> bool:
    """
    Check if a VSCode window has a chat panel visible.
    
    Pure function - reads window state, doesn't modify.
    
    Args:
        window_info: WindowInfo object to check
    
    Returns:
        True if window has chat panel, False otherwise.
    
    Implementation:
        For now, assume all VSCode windows might have chat panels.
        More sophisticated detection can be added later if needed.
        The real check happens in has_approval_request().
    """
    # Simplified: let the button detection be the authoritative check
    return True


def get_window_by_handle(handle: int) -> Optional[WindowInfo]:
    """
    Get WindowInfo for a specific window handle.
    
    Pure function - queries window properties, doesn't modify.
    
    Args:
        handle: Windows HWND handle
    
    Returns:
        WindowInfo if window exists and is VSCode, None otherwise.
    """
    try:
        desktop = Desktop(backend='uia')
        window = desktop.window(handle=handle)
        
        class_name = window.class_name()
        if class_name != VSCODE_WINDOW_CLASS_NAME:
            return None
        
        return WindowInfo(
            handle=handle,
            title=window.window_text(),
            class_name=class_name,
            process_id=window.process_id()
        )
        
    except Exception:
        return None
