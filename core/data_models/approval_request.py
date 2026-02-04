"""
Data models for agent approval requests.

All data models are frozen dataclasses (immutable) to ensure functional purity.
NO business logic in these models - only data containers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any

# Import constants from parser module to avoid duplication
from ..parsers.request_text_parser import (
    DANGEROUS_COMMAND_PATTERNS,
    READ_ONLY_REQUEST_PATTERNS,
    MAX_DISPLAY_TEXT_LENGTH,
    classify_command_safety,
)


@dataclass(frozen=True)
class ApprovalRequest:
    """
    Immutable representation of an agent approval request.
    
    All fields are extracted from VSCode UI using ground truth identifiers.
    """
    window_handle: int
    """Windows HWND of the VSCode window containing the request."""
    
    window_title: str
    """Full title of the VSCode window."""
    
    request_type: str
    """Type of request (e.g., 'Allow reading external directory')."""
    
    full_request_text: str
    """Complete text from the confirmation ListItem element."""
    
    files_to_access: List[str]
    """List of file paths/URIs that the agent wants to access."""
    
    commands_to_run: List[str]
    """List of terminal commands that the agent wants to execute."""
    
    allow_button_present: bool
    """True if a primary button (Allow/Accept) was found."""
    
    skip_button_present: bool
    """True if a secondary button (Skip/Reject) was found."""
    
    raw_ui_elements: dict = field(default_factory=dict)
    """Raw pywinauto element references (for debugging/advanced use)."""
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.
        
        Pure function - no side effects.
        Excludes raw_ui_elements to avoid serialization issues.
        """
        return {
            'window_handle': self.window_handle,
            'window_title': self.window_title,
            'request_type': self.request_type,
            'full_request_text': self.full_request_text[:MAX_DISPLAY_TEXT_LENGTH],
            'files_count': len(self.files_to_access),
            'files_to_access': self.files_to_access,
            'commands_count': len(self.commands_to_run),
            'commands_to_run': self.commands_to_run,
            'allow_button_present': self.allow_button_present,
            'skip_button_present': self.skip_button_present,
        }
    
    def is_valid(self) -> bool:
        """
        Check if this request has minimum required data.
        
        Pure function - no side effects.
        """
        return (
            self.window_handle > 0 and
            len(self.request_type) > 0 and
            (self.allow_button_present or self.skip_button_present)
        )
    
    def is_read_only_request(self) -> bool:
        """
        Heuristic to check if request is read-only (low risk).
        
        Pure function - delegates to parser module for safety classification.
        Returns True if all operations are safe (no dangerous or moderate commands).
        """
        # Delegate command safety check to parser module
        for cmd in self.commands_to_run:
            safety = classify_command_safety(cmd)
            if safety in ['dangerous', 'moderate']:
                return False
        
        # Check if request type suggests read-only using module constant
        request_lower = self.request_type.lower()
        return any(pattern in request_lower for pattern in READ_ONLY_REQUEST_PATTERNS)


@dataclass(frozen=True)
class WindowInfo:
    """
    Immutable representation of a VSCode window.
    
    Used for window discovery and filtering.
    """
    handle: int
    """Windows HWND."""
    
    title: str
    """Full window title."""
    
    class_name: str
    """Window class name (should be Chrome_WidgetWin_1 for VSCode)."""
    
    process_id: int
    """PID of the process owning this window."""
    
    def is_vscode_window(self, expected_class_name: str) -> bool:
        """
        Check if this window matches expected VSCode class name.
        
        Pure function - parameterized with expected value from ground truth.
        """
        return self.class_name == expected_class_name


@dataclass(frozen=True)
class UIElement:
    """
    Immutable representation of a UI Automation element.
    
    Extracted from pywinauto element_info but with only relevant data.
    """
    control_type: str
    """UIA control type (e.g., 'Button', 'ListItem', 'Edit')."""
    
    name: str
    """Element name/label."""
    
    class_name: str
    """CSS or automation class name."""
    
    automation_id: str
    """Automation ID (if present)."""
    
    value: str
    """Element text value."""
    
    rectangle: tuple
    """(left, top, right, bottom) screen coordinates."""
    
    def matches_class_pattern(self, pattern: str) -> bool:
        """
        Check if element class name contains pattern.
        
        Pure function - parameterized pattern.
        """
        return pattern in self.class_name
    
    def matches_text_pattern(self, pattern: str) -> bool:
        """
        Check if element text contains pattern.
        
        Pure function - parameterized pattern.
        """
        text_combined = f"{self.name} {self.value}".lower()
        return pattern.lower() in text_combined
