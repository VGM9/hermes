"""HERMES Core - Pure functions for window operations."""

import logging
import time
from typing import Optional, Tuple, List, Dict, TYPE_CHECKING
from pathlib import Path
from pywinauto import Application, findwindows

if TYPE_CHECKING:
    from pywinauto.uia_element_info import UIAElementInfo

logger = logging.getLogger(__name__)


class WindowNotFoundError(Exception):
    """Raised when target VS Code window cannot be found."""
    pass


def find_vscode_windows() -> list[dict[str, object]]:
    """Find all VS Code windows using Chrome_WidgetWin_1 class.
    
    Returns:
        List of dicts with 'window' (UIAElementInfo), 'title' (str), 'handle' (int) keys
        
    Raises:
        WindowNotFoundError: If no VS Code windows found at all
    """
    try:
        handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    except Exception as e:
        logger.error(f"Failed to enumerate windows: {e}")
        raise WindowNotFoundError("Cannot enumerate VS Code windows") from e
    
    vscode_windows = []
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" in title:
                vscode_windows.append({
                    'window': win,
                    'title': title,
                    'handle': handle
                })
                logger.debug(f"Found VS Code window: {title[:60]}")
        except Exception as e:
            logger.debug(f"Failed to connect to window {handle}: {e}")
            continue
    
    if not vscode_windows:
        raise WindowNotFoundError("No VS Code windows found")
    
    return vscode_windows


def find_agent_window(agent_pattern: str) -> Tuple["UIAElementInfo", str]:
    """Find VS Code window matching agent pattern in title.
    
    Args:
        agent_pattern: Pattern to match in window title (case-insensitive)
                      e.g., 'THEIA0', '0.6.Q', 'ARGUS0'
    
    Returns:
        Tuple of (window_object: UIAElementInfo, matched_title: str)
        
    Raises:
        WindowNotFoundError: If no matching window found
        
    Warning:
        Returned window object is only valid for the current session.
        Do NOT cache or store between function calls; window may become invalid.
    """
    try:
        vscode_windows = find_vscode_windows()
    except WindowNotFoundError:
        raise
    
    # Try exact match first
    for w in vscode_windows:
        if agent_pattern.lower() in w['title'].lower():
            logger.info(f"Found window for agent '{agent_pattern}': {w['title'][:60]}")
            return w['window'], w['title']
    
    # No match found - provide helpful error
    available = "\n".join(f"  • {w['title'][:70]}" for w in vscode_windows[:5])
    error_msg = (
        f"No window matching '{agent_pattern}' found.\n"
        f"Available windows:\n{available}"
    )
    if len(vscode_windows) > 5:
        error_msg += f"\n  ... and {len(vscode_windows) - 5} more"
    
    logger.warning(error_msg)
    raise WindowNotFoundError(error_msg)


def focus_window(window: "UIAElementInfo", delay_sec: float = 0.3) -> None:
    """Focus window and wait for focus to take effect.
    
    Args:
        window: pywinauto window object (UIAElementInfo)
        delay_sec: Delay after focus (default 0.3s)
        
    Raises:
        Exception: If window focus fails
    """
    try:
        window.set_focus()
        logger.debug(f"Focused window")
        time.sleep(delay_sec)
    except Exception as e:
        logger.error(f"Failed to focus window: {e}")
        raise


def get_focused_vscode_window() -> Optional[dict]:
    """Get the currently focused VS Code window.
    
    Returns:
        Dict with 'window', 'title', 'handle' keys, or None if no VSCode window 
        has focus.
        
    Note:
        Returns None if focused window is not a VS Code window.
        Use find_vscode_windows() if you need all windows regardless of focus.
    """
    try:
        from pywinauto import GetFocusedControl
        try:
            focused = GetFocusedControl()
            focused_handle = focused.handle if hasattr(focused, 'handle') else None
            
            if not focused_handle:
                logger.debug("No window has focus")
                return None
            
            # Check if focused window is VS Code
            try:
                app = Application(backend="uia").connect(handle=focused_handle)
                win = app.window(handle=focused_handle)
                title = win.window_text()
                
                if "Visual Studio Code" in title:
                    logger.debug(f"Focused window is VS Code: {title[:60]}")
                    return {
                        'window': win,
                        'title': title,
                        'handle': focused_handle
                    }
                else:
                    logger.debug(f"Focused window is not VS Code: {title[:40]}")
                    return None
            except Exception as e:
                logger.debug(f"Cannot connect to focused window: {e}")
                return None
        
        except Exception as e:
            logger.debug(f"Cannot get focused control: {e}")
            return None
            
    except ImportError:
        logger.warning("GetFocusedControl not available, falling back to window list")
        # Fallback: return first window (not ideal, but something)
        try:
            windows = find_vscode_windows()
            if windows:
                logger.debug("Returning first window as fallback (focus detection unavailable)")
                return windows[0]
        except:
            pass
        return None


def get_window_workspace_path(window_title: str) -> Optional[Path]:
    """Extract workspace path from VS Code window title.
    
    VS Code window titles follow patterns like:
      "file.md - /path/to/workspace - Visual Studio Code"
      "Welcome - folder_name (Workspace) - Visual Studio Code"
      "file.py - WSL: Ubuntu - Workspace/folder - Visual Studio Code"
    
    Args:
        window_title: Full VS Code window title
        
    Returns:
        Workspace path as Path object, or None if cannot extract
        
    Note:
        This is a best-effort heuristic. Not all workspaces may be detectable
        from the window title alone.
    """
    try:
        # Try to extract path patterns from title
        parts = window_title.split(" - ")
        
        for part in parts:
            # Skip known keywords
            if any(skip in part for skip in ['Visual Studio Code', 'Insiders']):
                continue
            
            # Check if looks like a path
            if '/' in part or '\\' in part or 'Workspace' in part:
                # Try to clean it up
                clean = part.rstrip(')')
                if clean:
                    logger.debug(f"Extracted workspace from title: {clean}")
                    return Path(clean)
        
        logger.debug(f"Could not extract workspace path from: {window_title[:60]}")
        return None
    
    except Exception as e:
        logger.debug(f"Error extracting workspace: {e}")
        return None


def list_window_properties(window: "UIAElementInfo") -> Dict[str, str]:
    """Get detailed properties of a window for debugging.
    
    Args:
        window: pywinauto window object
        
    Returns:
        Dict with title, class, automation_id, etc.
    """
    try:
        return {
            'title': window.window_text(),
            'class': window.class_name(),
            'pid': str(window.process_id()) if hasattr(window, 'process_id') else 'unknown',
            'handle': str(window.handle) if hasattr(window, 'handle') else 'unknown'
        }
    except Exception as e:
        logger.debug(f"Error getting window properties: {e}")
        return {'error': str(e)}
