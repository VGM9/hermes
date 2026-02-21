"""
Element Interaction Module

Functions for interacting with UI elements (clicking buttons, executing commands).
These are NOT pure functions - they have side effects (modify UI state).
"""

from typing import Optional
import subprocess

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from vscode_ground_truth import (
    ACCEPT_TOOL_CONFIRMATION_ACTION_ID,
    SKIP_TOOL_CONFIRMATION_ACTION_ID,
)


def execute_vscode_command(action_id: str) -> bool:
    """
    Execute a VSCode command by action ID.
    
    SIDE EFFECT: Executes command in VSCode via CLI.
    
    Args:
        action_id: VSCode action ID (e.g., 'workbench.action.chat.acceptTool')
    
    Returns:
        True if command executed successfully, False otherwise.
    
    Implementation:
        Uses 'code-insiders' or 'code' CLI with --command flag.
        Falls back to 'code' if 'code-insiders' not found.
    
    Source:
        Action IDs from vscode_ground_truth.py
    """
    # Try VSCode Insiders first
    commands_to_try = [
        ['code-insiders', '--command', action_id],
        ['code', '--command', action_id],
    ]
    
    for cmd in commands_to_try:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return False


def approve_via_action_id() -> bool:
    """
    Approve agent request by executing accept action.
    
    SIDE EFFECT: Approves the agent request.
    
    Returns:
        True if approval succeeded, False otherwise.
    """
    return execute_vscode_command(ACCEPT_TOOL_CONFIRMATION_ACTION_ID)


def skip_via_action_id() -> bool:
    """
    Skip agent request by executing skip action.
    
    SIDE EFFECT: Skips the agent request.
    
    Returns:
        True if skip succeeded, False otherwise.
    """
    return execute_vscode_command(SKIP_TOOL_CONFIRMATION_ACTION_ID)
