"""
Optimized Element Detection Module

Uses global button search instead of per-window descendants.
Based on working approach from earlier tests.
"""

from typing import List, Optional, Dict
from pywinauto import Desktop

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from vscode_ground_truth import (
    MONACO_BUTTON_PRIMARY_CLASSES,
    MONACO_BUTTON_SECONDARY_CLASSES,
    CONTROL_TYPE_BUTTON,
    KEYBINDING_ACCEPT_TOOL,
    KEYBINDING_SKIP_TOOL,
)
from core.data_models.approval_request import UIElement, WindowInfo


def find_all_approval_buttons_globally() -> List[Dict]:
    """
    Find all approval buttons across all windows (global search).
    
    This is MUCH faster than searching each window individually.
    
    Returns:
        List of dicts with keys: 'type' ('allow'|'skip'), 'button' (UIElement), 'window_handle'
    """
    buttons_found = []
    
    try:
        desktop = Desktop(backend='uia')
        
        # Search for all buttons with the keybinding text globally
        # This is faster than window-by-window search
        all_windows = desktop.windows()
        
        for window in all_windows:
            try:
                # Quick class check
                if window.class_name() != 'Chrome_WidgetWin_1':
                    continue
                    
                # Only search in VSCode windows
                window_handle = window.handle
                
                # Fast shallow search for buttons with specific text
                try:
                    buttons = window.descendants(control_type=CONTROL_TYPE_BUTTON, depth=6)
                    
                    for button in buttons:
                        try:
                            if not button.is_visible():
                                continue
                                
                            button_text = button.window_text()
                            
                            # Check for Allow button (has Ctrl+Enter)
                            if KEYBINDING_ACCEPT_TOOL['human_readable'] in button_text:
                                buttons_found.append({
                                    'type': 'allow',
                                    'button': _create_ui_element(button),
                                    'window_handle': window_handle
                                })
                            
                            # Check for Skip button (has Ctrl+Alt+Enter)
                            elif KEYBINDING_SKIP_TOOL['human_readable'] in button_text:
                                buttons_found.append({
                                    'type': 'skip',
                                    'button': _create_ui_element(button),
                                    'window_handle': window_handle
                                })
                        except:
                            continue
                except:
                    # This window has no accessible buttons
                    continue
                    
            except:
                continue
                
    except:
        pass
    
    return buttons_found


def find_buttons_in_window(window_info: WindowInfo) -> Dict[str, Optional[UIElement]]:
    """
    Find Allow and Skip buttons in a specific VSCode window.
    
    Implementation:
        Uses the global button search, then filters by window handle.
        This is much faster than searching within the window.
    
    Args:
        window_info: WindowInfo to search in
    
    Returns:
        Dictionary with keys 'allow' and 'skip', values are UIElement or None.
    """
    result = {
        'allow': None,
        'skip': None,
    }
    
    # Use global search
    all_buttons = find_all_approval_buttons_globally()
    
    # Filter for this window
    for button_info in all_buttons:
        if button_info['window_handle'] == window_info.handle:
            button_type = button_info['type']
            result[button_type] = button_info['button']
    
    return result


def find_chat_content(window_info: WindowInfo) -> Optional[str]:
    """
    Extract text content from chat panel.
    
    Pure function - reads text, doesn't modify.
    
    Args:
        window_info: WindowInfo to search in
    
    Returns:
        Text content of chat panel, or None if not found.
        
    Implementation:
        Attempts to get window text with timeout.
        Avoids slow descendants() call.
    """
    try:
        desktop = Desktop(backend='uia')
        window = desktop.window(handle=window_info.handle)
        
        # Try to get text directly from window
        text = window.window_text()
        if text and len(text) > 50:  # Reasonable threshold
            return text
        
        # If that didn't work, try print_control_identifiers with capture
        try:
            from io import StringIO
            import sys
            old_stdout = sys.stdout
            sys.stdout = captured = StringIO()
            
            window.print_control_identifiers(depth=4, filename=None)
            
            sys.stdout = old_stdout
            output = captured.getvalue()
            
            if output and len(output) > 100:
                return output
        except:
            pass
        
        return None
        
    except Exception:
        return None


def _create_ui_element(element) -> UIElement:
    """
    Convert pywinauto element to UIElement dataclass.
    
    Pure function - extracts properties, doesn't modify.
    
    Args:
        element: pywinauto element wrapper
    
    Returns:
        UIElement with extracted properties
    """
    try:
        rect = element.rectangle()
        rectangle = (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        rectangle = (0, 0, 0, 0)
    
    try:
        automation_id = element.automation_id()
    except Exception:
        automation_id = ""
    
    try:
        value = element.get_value()
    except Exception:
        value = ""
    
    return UIElement(
        control_type=element.control_type(),
        name=element.window_text(),
        class_name=element.class_name(),
        automation_id=automation_id,
        value=value,
        rectangle=rectangle,
        element_ref=element  # Keep reference for interaction
    )


def has_approval_request(window_info: WindowInfo) -> bool:
    """
    Check if window has an approval request (has Allow button).
    
    Pure function - checks for button presence, doesn't interact.
    
    Args:
        window_info: WindowInfo to check
    
    Returns:
        True if Allow button is present, False otherwise.
    """
    buttons = find_buttons_in_window(window_info)
    return buttons['allow'] is not None
