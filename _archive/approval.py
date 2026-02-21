"""
Approval Module - Public API

Declarative wrapper for approving/skipping agent requests.
Composes functions from core modules (interaction layer).
"""

from typing import Optional
import time

from core.ui_automation.element_interaction import (
    click_button,
    approve_via_action_id,
    skip_via_action_id,
)
from core.data_models.approval_request import ApprovalRequest
from detection import find_agent_by_window_handle


def approve_agent(agent: ApprovalRequest, method: str = 'button') -> bool:
    """
    Approve an agent's request.
    
    SIDE EFFECT: Clicks approval button or executes approval command.
    
    Args:
        agent: ApprovalRequest to approve
        method: 'button' (click UI) or 'command' (execute action ID)
    
    Returns:
        True if approval succeeded, False otherwise.
    
    Example:
        >>> from hermes import detection, approval
        >>> agents = detection.find_paused_agents()
        >>> if agents:
        ...     result = approval.approve_agent(agents[0])
        ...     print(f"Approved: {result}")
    
    Implementation:
        If method='button': Clicks the Allow button
        If method='command': Executes workbench.action.chat.acceptTool
    """
    if method == 'button':
        if agent.allow_button is None:
            return False
        return click_button(agent.allow_button)
    
    elif method == 'command':
        return approve_via_action_id()
    
    else:
        raise ValueError(f"Invalid method: {method}. Use 'button' or 'command'.")


def skip_agent(agent: ApprovalRequest, method: str = 'button') -> bool:
    """
    Skip an agent's request.
    
    SIDE EFFECT: Clicks skip button or executes skip command.
    
    Args:
        agent: ApprovalRequest to skip
        method: 'button' (click UI) or 'command' (execute action ID)
    
    Returns:
        True if skip succeeded, False otherwise.
    
    Example:
        >>> from hermes import detection, approval
        >>> agents = detection.find_paused_agents()
        >>> if agents:
        ...     result = approval.skip_agent(agents[0])
        ...     print(f"Skipped: {result}")
    
    Implementation:
        If method='button': Clicks the Skip button
        If method='command': Executes workbench.action.chat.skipTool
    """
    if method == 'button':
        if agent.skip_button is None:
            return False
        return click_button(agent.skip_button)
    
    elif method == 'command':
        return skip_via_action_id()
    
    else:
        raise ValueError(f"Invalid method: {method}. Use 'button' or 'command'.")


def approve_by_window_handle(handle: int, method: str = 'button') -> bool:
    """
    Approve agent by window handle.
    
    Convenience function that combines detection + approval.
    
    Args:
        handle: Windows HWND handle
        method: 'button' or 'command'
    
    Returns:
        True if agent found and approved, False otherwise.
    
    Example:
        >>> from hermes import approval
        >>> result = approval.approve_by_window_handle(0x12345)
        >>> print(f"Approved: {result}")
    """
    agent = find_agent_by_window_handle(handle)
    if agent is None:
        return False
    
    return approve_agent(agent, method=method)


def skip_by_window_handle(handle: int, method: str = 'button') -> bool:
    """
    Skip agent by window handle.
    
    Convenience function that combines detection + skip.
    
    Args:
        handle: Windows HWND handle
        method: 'button' or 'command'
    
    Returns:
        True if agent found and skipped, False otherwise.
    
    Example:
        >>> from hermes import approval
        >>> result = approval.skip_by_window_handle(0x12345)
        >>> print(f"Skipped: {result}")
    """
    agent = find_agent_by_window_handle(handle)
    if agent is None:
        return False
    
    return skip_agent(agent, method=method)


def approve_all_safe_requests(safety_threshold: str = 'safe') -> int:
    """
    Approve all requests that meet safety threshold.
    
    SIDE EFFECT: Approves multiple agents.
    
    Args:
        safety_threshold: 'safe' (only read-only), 'moderate' (includes moderate risk)
    
    Returns:
        Number of agents approved.
    
    Example:
        >>> from hermes import approval
        >>> count = approval.approve_all_safe_requests(safety_threshold='safe')
        >>> print(f"Approved {count} safe requests")
    
    WARNING:
        Use with caution! This automatically approves multiple agents.
    """
    from detection import find_paused_agents
    
    agents = find_paused_agents()
    approved_count = 0
    
    for agent in agents:
        # Check safety based on threshold
        if safety_threshold == 'safe':
            if agent.is_read_only_request():
                if approve_agent(agent):
                    approved_count += 1
                    time.sleep(0.5)  # Brief delay between approvals
        
        elif safety_threshold == 'moderate':
            if agent.command_safety in ['safe', 'moderate']:
                if approve_agent(agent):
                    approved_count += 1
                    time.sleep(0.5)
    
    return approved_count
