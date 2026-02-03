"""HERMES Core - Pure functions for window operations."""

import logging
from typing import Optional, Tuple
from pathlib import Path
from pywinauto import Application, findwindows

logger = logging.getLogger(__name__)


class WindowNotFoundError(Exception):
    """Raised when target VS Code window cannot be found."""
    pass


def find_vscode_windows() -> list[dict]:
    """Find all VS Code windows using Chrome_WidgetWin_1 class.
    
    Returns:
        List of dicts with 'window', 'title', 'handle' keys
        
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


def find_agent_window(agent_pattern: str) -> Tuple[object, str]:
    """Find VS Code window matching agent pattern in title.
    
    Args:
        agent_pattern: Pattern to match in window title (case-insensitive)
                      e.g., 'THEIA0', '0.6.Q', 'ARGUS0'
    
    Returns:
        Tuple of (window_object, matched_title)
        
    Raises:
        WindowNotFoundError: If no matching window found
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


def focus_window(window: object, delay_sec: float = 0.3) -> None:
    """Focus window and wait for focus to take effect.
    
    Args:
        window: pywinauto window object
        delay_sec: Delay after focus (default 0.3s)
        
    Raises:
        Exception: If window focus fails
    """
    import time
    
    try:
        window.set_focus()
        logger.debug(f"Focused window")
        time.sleep(delay_sec)
    except Exception as e:
        logger.error(f"Failed to focus window: {e}")
        raise
