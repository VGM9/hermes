"""
UI Automation Module

Pure functions for interacting with VSCode UI elements.
All functions are deterministic and have no side effects.
"""

from .window_detection import find_vscode_windows, has_chat_panel
from .element_detection import find_buttons_in_window, find_chat_content

__all__ = [
    'find_vscode_windows',
    'has_chat_panel',
    'find_buttons_in_window',
    'find_chat_content',
]
