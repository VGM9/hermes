"""HERMES Core - Pure functions for chat operations."""

import logging
import time
from typing import Optional
from pywinauto.keyboard import send_keys

logger = logging.getLogger(__name__)


class ChatOperationError(Exception):
    """Raised when chat operation fails."""
    pass


def open_chat(
    keybinding: str = "^+i",
    open_delay_sec: float = 0.8,
    focus_delay_sec: float = 0.3
) -> None:
    """Open VS Code chat panel using keyboard shortcut.
    
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
