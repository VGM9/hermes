"""
Window Detection Module

Pure functions for finding and identifying VSCode windows.
All identifiers imported from vscode_ground_truth.py.
"""

from typing import List, Optional
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
