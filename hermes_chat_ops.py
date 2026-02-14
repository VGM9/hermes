# -*- coding: utf-8 -*-
"""HERMES Core - Pure functions for chat operations."""

import logging
import time
from typing import Optional, List, Dict
from pywinauto.keyboard import send_keys

logger = logging.getLogger(__name__)


class ChatOperationError(Exception):
    """Raised when chat operation fails."""
    pass


def click_chat_input(
    window,
    open_delay_sec: float = 0.5
) -> bool:
    """Click chat input field directly (IDENTITY-PRESERVING alternative to Ctrl+Shift+I).
    
    ✅ SAFE: This method does NOT reset agent selection dropdown.
    
    Searches for the chat input edit control and clicks it to activate chat.
    Preserves agent identity unlike keyboard shortcuts.
    
    Args:
        window: pywinauto window object (from hermes_window_ops)
        open_delay_sec: Time to wait for chat to activate (default: 0.5s)
        
    Returns:
        True if chat input found and clicked, False otherwise
        
    Raises:
        ChatOperationError: If window interaction fails
    """
    try:
        logger.debug("Searching for chat input field...")
        
        # Find Edit controls (chat input is an Edit control in VS Code)
        edit_controls = window.descendants(control_type="Edit")
        
        for edit in edit_controls:
            name = edit.element_info.name.lower() if hasattr(edit.element_info, 'name') else ""
            automation_id = edit.element_info.automation_id.lower() if hasattr(edit.element_info, 'automation_id') else ""
            class_name = edit.element_info.class_name.lower() if hasattr(edit.element_info, 'class_name') else ""
            
            # Look for chat input specifically
            # VS Code pattern: "Chat Input (AgentName), undefined, Model..."
            if "chat input" in name or class_name == "native-edit-context":
                try:
                    logger.info(f"Found chat input: {name[:60] if name else class_name}")
                    edit.click_input()
                    time.sleep(open_delay_sec)
                    logger.info("✓ Chat input activated (identity preserved)")
                    return True
                except Exception as e:
                    logger.debug(f"Failed to click edit control: {e}")
                    continue
        
        logger.warning("Could not find chat input field")
        return False
        
    except Exception as e:
        logger.error(f"Failed to activate chat: {e}")
        raise ChatOperationError(f"Cannot activate chat input: {e}") from e


def open_chat(
    keybinding: str = "^+i",
    open_delay_sec: float = 0.8,
    focus_delay_sec: float = 0.3
) -> None:
    """Open VS Code chat panel using keyboard shortcut.
    
    ⚠️ CRITICAL WARNING: Ctrl+Shift+I DESTROYS AGENT IDENTITY ⚠️
    
    This keyboard shortcut (^+i) resets VS Code agent selection dropdown
    from custom agents (e.g., "0.0.Q (HUSK)", "ALTAIR") to default "Agent".
    
    Consequences:
    - Recipient loses specialized agent identity
    - Custom tools (qhoami, qopilot, etc.) become unavailable
    - Agent instructions (.agent.md frontmatter) ignored
    - Specialized context lost
    - False memories/confusion from identity contamination
    
    DO NOT USE for inter-agent messaging unless you have:
    1. Verified agent selection before opening chat
    2. Method to restore agent selection after opening  
    3. Documented this risk to recipient
    
    RECOMMENDED ALTERNATIVE: Use click_chat_input(window) instead (identity-preserving)
    
    See: __/.github/instructions/HERMES-CRITICAL-BUG.md
    See: __/projects/hermes-protocol-fixes/M2-IDENTITY-PRESERVATION.md
    
    Args:
        keybinding: Keyboard shortcut to send (default: Ctrl+Shift+I = "^+i")
        open_delay_sec: Time to wait for chat to open (default: 0.8s)
        focus_delay_sec: Time to wait before sending keys (default: 0.3s)
        
    Raises:
        ChatOperationError: If chat open fails
        
    Note:
        Default keybinding Ctrl+Shift+I opens Copilot Chat Agent mode on Windows.
        Different modes/platforms may need adjustment.
    """
    try:
        logger.debug(f"Sending keybinding: {keybinding}")
        time.sleep(focus_delay_sec)  # Wait before sending
        send_keys(keybinding)
        logger.info("Chat panel open command sent")
        time.sleep(open_delay_sec)  # Wait for panel to render
    except Exception as e:
        logger.error(f"Failed to open chat: {e}")
        raise ChatOperationError(f"Cannot open chat panel: {e}") from e


def type_message(
    message: str,
    char_delay_sec: float = 0.01,
    post_type_delay_sec: float = 0.3
) -> None:
    """Type message into chat input (must be focused).
    
    Args:
        message: Message text to type
        char_delay_sec: Delay between characters (default: 0.01s)
        post_type_delay_sec: Delay after typing completes (default: 0.3s)
        
    Raises:
        ChatOperationError: If typing fails
    """
    try:
        logger.debug(f"Typing message: {len(message)} chars")
        send_keys(message, with_spaces=True, pause=char_delay_sec)
        logger.info(f"Message typed successfully")
        time.sleep(post_type_delay_sec)
    except Exception as e:
        logger.error(f"Failed to type message: {e}")
        raise ChatOperationError(f"Cannot type message: {e}") from e


def send_message(
    post_send_delay_sec: float = 0.5
) -> None:
    """Send message via Enter key.
    
    Args:
        post_send_delay_sec: Delay after pressing Enter (default: 0.5s)
        
    Raises:
        ChatOperationError: If send fails
    """
    try:
        logger.debug("Pressing Enter to send")
        send_keys('{ENTER}')
        logger.info("Message sent")
        time.sleep(post_send_delay_sec)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise ChatOperationError(f"Cannot send message: {e}") from e


def type_without_send(
    message: str,
    char_delay_sec: float = 0.01,
    post_type_delay_sec: float = 0.3
) -> None:
    """Type message into chat without pressing Enter (for defer-send scenarios).
    
    Args:
        message: Message text to type
        char_delay_sec: Delay between characters (default: 0.01s)
        post_type_delay_sec: Delay after typing completes (default: 0.3s)
        
    Raises:
        ChatOperationError: If typing fails
    """
    try:
        logger.debug(f"Typing message (no send): {len(message)} chars")
        send_keys(message, with_spaces=True, pause=char_delay_sec)
        logger.info(f"Message typed (awaiting send)")
        time.sleep(post_type_delay_sec)
    except Exception as e:
        logger.error(f"Failed to type message: {e}")
        raise ChatOperationError(f"Cannot type message: {e}") from e


def find_unsent_chat_messages() -> List[Dict[str, str]]:
    """Find all unsent messages across open VSCode windows.
    
    Scans all open VSCode windows for text in chat input boxes that has not yet
    been sent. Useful for verification or recovery workflows.
    
    Returns:
        List of dicts with:
        - 'window_title': Full window title
        - 'chat_text': Unsent message text
        - 'text_length': Length of unsent text
        
    Example:
        >>> messages = find_unsent_chat_messages()
        >>> for msg in messages:
        ...     print(f"{msg['window_title']}: {msg['chat_text']}")
    
    Note:
        Returns empty list if no unsent messages found.
        Must be run on Windows (uses pywinauto).
    """
    # Import here to avoid circular import
    import hermes_window_ops
    import signal
    
    unsent_messages = []
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Window inspection timeout")
    
    try:
        windows = hermes_window_ops.find_vscode_windows()
        logger.debug(f"Scanning {len(windows)} VSCode windows for unsent messages")
        
        for w in windows:
            try:
                window_spec = w['window']
                
                # Set timeout for this window's inspection
                try:
                    # Only inspect if window is still valid
                    title = w['title']
                    descendants = []
                    
                    # Try to get descendants with minimal timeout
                    try:
                        descendants = list(window_spec.descendants())
                    except Exception as e:
                        logger.debug(f"Skipping window (inspection error): {e}")
                        continue
                    
                except Exception as e:
                    logger.debug(f"Error with window: {e}")
                    continue
                
                for control in descendants:
                    try:
                        control_type = str(control.element_info.control_type)
                        if "Edit" not in control_type:
                            continue
                        
                        text = control.window_text()
                        
                        # Filter for substantial unsent messages
                        if not text or len(text) < 5:
                            continue
                        
                        # Skip known non-chat UI text
                        skip_patterns = [
                            'Copyright', 'PowerShell', 'Terminal', 'environment is stale',
                            'Allow reading', 'outside of', 'Show Environment',
                            'Restart Visual Studio', 'update.', 'command for more',
                            'The editor is not accessible', 'screen reader',
                            'Press Enter to send', 'Chat Input', 'Chat Accessibility'
                        ]
                        
                        if any(pattern in text for pattern in skip_patterns):
                            continue
                        
                        # Don't report file content (detect by looking for too many newlines)
                        newline_count = text.count('\n')
                        if newline_count > 5:
                            continue
                        
                        unsent_messages.append({
                            'window_title': w['title'],
                            'chat_text': text,
                            'text_length': len(text)
                        })
                        
                        logger.info(f"Found unsent message in {w['title']}: {len(text)} chars")
                    
                    except Exception as e:
                        logger.debug(f"Error inspecting control: {e}")
                        continue
                        
            except KeyboardInterrupt:
                logger.warning("Window inspection interrupted")
                break
            except Exception as e:
                logger.debug(f"Error scanning window: {e}")
                continue
        
        logger.info(f"Found {len(unsent_messages)} unsent message(s)")
        return unsent_messages
        
    except Exception as e:
        logger.error(f"Failed to find unsent messages: {e}")
        raise ChatOperationError(f"Cannot find unsent messages: {e}") from e
