"""
Detection Module - Public API

Declarative wrapper for detecting paused agents in VSCode.
Composes pure functions from core modules.
"""

from typing import List

from core.ui_automation.window_detection import find_vscode_windows, has_chat_panel
from core.ui_automation.element_detection import (
    find_buttons_in_window,
    find_chat_content,
    has_approval_request,
)
from core.parsers.request_text_parser import parse_request_text
from core.data_models.approval_request import ApprovalRequest


def find_paused_agents() -> List[ApprovalRequest]:
    """
    Find all paused agents awaiting approval in VSCode windows.
    
    This is the main entry point for detecting approval requests.
    Composes pure functions from core modules.
    
    Returns:
        List of ApprovalRequest objects for each paused agent.
        May be empty if no paused agents are found.
    
    Example:
        >>> from hermes import detection
        >>> agents = detection.find_paused_agents()
        >>> for agent in agents:
        ...     print(f"Agent wants to: {agent.request_type}")
        ...     print(f"Files: {len(agent.files_to_access)}")
        ...     print(f"Commands: {len(agent.commands_to_run)}")
    
    Implementation:
        1. Find all VSCode windows
        2. Filter for windows with chat panels
        3. Find windows with approval requests (Allow button present)
        4. Extract chat content and parse request text
        5. Find buttons and build ApprovalRequest objects
    """
    paused_agents = []
    
    # Step 1: Find all VSCode windows
    vscode_windows = find_vscode_windows()
    
    for window in vscode_windows:
        # Step 2: Filter for windows with chat panels
        if not has_chat_panel(window):
            continue
        
        # Step 3: Check if window has approval request
        if not has_approval_request(window):
            continue
        
        # Step 4: Extract and parse chat content
        chat_text = find_chat_content(window)
        if not chat_text:
            continue
        
        parsed_data = parse_request_text(chat_text)
        
        # Step 5: Find buttons
        buttons = find_buttons_in_window(window)
        
        # Build ApprovalRequest
        approval_request = ApprovalRequest(
            window_handle=window.handle,
            window_title=window.title,
            window_class=window.class_name,
            window_process_id=window.process_id,
            request_type=parsed_data['request_type'],
            files_to_access=parsed_data['files'],
            commands_to_run=parsed_data['commands'],
            has_allow_button=buttons['allow'] is not None,
            has_skip_button=buttons['skip'] is not None,
            allow_button=buttons['allow'],
            skip_button=buttons['skip'],
            raw_text=chat_text[:500],  # Truncate for storage
            workspace_file_count=parsed_data['workspace_files'],
            external_file_count=parsed_data['external_files'],
            system_file_count=parsed_data['system_files'],
            command_safety=parsed_data['command_safety'],
        )
        
        paused_agents.append(approval_request)
    
    return paused_agents


def find_agent_by_window_handle(handle: int) -> ApprovalRequest:
    """
    Find approval request for a specific window handle.
    
    Args:
        handle: Windows HWND handle
    
    Returns:
        ApprovalRequest if found, None otherwise.
    
    Example:
        >>> agent = detection.find_agent_by_window_handle(0x12345)
        >>> if agent:
        ...     print(f"Found: {agent.request_type}")
    """
    agents = find_paused_agents()
    for agent in agents:
        if agent.window_handle == handle:
            return agent
    return None
