"""
Element Detection Module

Pure functions for finding UI elements within VSCode windows.
All identifiers imported from vscode_ground_truth.py.
"""

from typing import List, Optional, Dict
import pywinauto
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


def find_chat_content(window_info: WindowInfo) -> Optional[str]:
    """
    Extract text content from chat panel.
    
    Pure function - reads text, doesn't modify.
    
    Args:
        window_info: WindowInfo to search in
    
    Returns:
        Text content of chat panel, or None if not found.
    
    Implementation:
        Searches for visible text elements in the window.
        Concatenates all text to get full chat content.
    """
    try:
        desktop = Desktop(backend='uia')
        window = desktop.window(handle=window_info.handle)
        
        # Get all text elements
        text_elements = window.descendants(control_type='Text', depth=15)
        
        text_parts = []
        for elem in text_elements:
            try:
                if elem.is_visible():
                    text = elem.window_text()
                    if text and text.strip():
                        text_parts.append(text)
            except Exception:
                continue
        
        if text_parts:
            return '\n'.join(text_parts)
        
        return None
        
    except Exception:
        return None


def find_buttons_in_window(window_info: WindowInfo) -> Dict[str, Optional[UIElement]]:
    """
    Find Allow and Skip buttons in a VSCode window.
    
    Pure function - searches for buttons, doesn't interact.
    
    Args:
        window_info: WindowInfo to search in
    
    Returns:
        Dictionary with keys 'allow' and 'skip', values are UIElement or None.
        
    Implementation:
        Uses button class names from ground truth and keybinding text.
        Primary button (with "Ctrl+Enter") is Allow.
        Secondary button (with "Ctrl+Alt+Enter") is Skip.
        
        Performance: Uses find_elements with limited depth instead of full descendants.
    
    Source:
        MONACO_BUTTON_PRIMARY_CLASSES from vscode_ground_truth.py
        MONACO_BUTTON_SECONDARY_CLASSES from vscode_ground_truth.py
    """
    buttons = {
        'allow': None,
        'skip': None,
    }
    
    try:
        desktop = Desktop(backend='uia')
        window = desktop.window(handle=window_info.handle)
        
        # Use find_elements instead of descendants for better performance
        # Search with shallower depth
        all_buttons = window.descendants(control_type=CONTROL_TYPE_BUTTON, depth=8)
        
        button_count = 0
        for button in all_buttons:
            try:
                if not button.is_visible():
                    continue
                
                button_text = button.window_text()
                button_class = button.class_name()
                
                # Check if it's an Allow button (primary, has Ctrl+Enter)
                if KEYBINDING_ACCEPT_TOOL['human_readable'] in button_text:
                    # Verify it's a primary button style
                    if any(cls in button_class for cls in MONACO_BUTTON_PRIMARY_CLASSES.split()):
                        buttons['allow'] = _create_ui_element(button)
                
                # Check if it's a Skip button (secondary, has Ctrl+Alt+Enter)
                elif KEYBINDING_SKIP_TOOL['human_readable'] in button_text:
                    # Verify it's a secondary button style
                    if any(cls in button_class for cls in MONACO_BUTTON_SECONDARY_CLASSES.split()):
                        buttons['skip'] = _create_ui_element(button)
                
                # Stop early if found both
                if buttons['allow'] and buttons['skip']:
                    break
                    
                button_count += 1
                if button_count > 100:  # Safety limit
                    break
                    
            except Exception:
                continue
        
    except Exception:
        pass
    
    return buttons


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
