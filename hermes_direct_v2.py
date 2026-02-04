#!/usr/bin/env python3
"""
HERMES Direct v2 - Refactored with proper structure, typing, and error handling

Send messages to VS Code Copilot agents via UI automation.
Uses pywinauto for window/keyboard control and AppData inspection for verification.

Exit codes:
  0 = Success
  1 = Usage/argument error
  2 = Window not found
  3 = Window operation failed
  4 = Chat operation failed
  5 = Verification failed
"""

import sys
import os
import logging
from typing import Optional, Tuple

# Import refactored modules
import hermes_window_ops as window_ops
import hermes_chat_ops as chat_ops
import hermes_session_verify as session_verify
import hermes_config


# Configure logging
def configure_logging(verbose: bool = False) -> None:
    """Set up structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )


def send_message_to_agent(
    agent_pattern: str,
    message: str,
    verify: bool = True,
    timeout_sec: float = 5.0,
    send_enter: bool = True,
    keybinding: str = "^+i"
) -> Tuple[bool, Optional[str]]:
    """Send message to agent window with proper error handling.
    
    Args:
        agent_pattern: Agent identifier in window title
        message: Message to send
        verify: Whether to verify delivery via AppData
        timeout_sec: Verification timeout
        send_enter: Whether to press Enter after typing
        keybinding: Keyboard shortcut to open chat (default Ctrl+Shift+I)
        
    Returns:
        (success: bool, error_message: str or None)
    """
    logger = logging.getLogger(__name__)
    
    # Step 1: Find window
    try:
        logger.info(f"Finding window for agent: {agent_pattern}")
        win, title = window_ops.find_agent_window(agent_pattern)
        logger.info(f"✓ Found: {title[:70]}")
    except window_ops.WindowNotFoundError as e:
        logger.error(str(e))
        return False, str(e)
    
    # Step 2: Get initial request count (for verification)
    count_before = None
    if verify:
        count_before = session_verify.get_session_request_count(agent_pattern)
        if count_before is None:
            logger.warning(f"Could not find session for verification - continuing without it")
            verify = False
        else:
            logger.info(f"Initial request count: {count_before}")
    
    # Step 3: Focus window
    try:
        window_ops.focus_window(win)
        logger.info("✓ Window focused")
    except Exception as e:
        logger.error(f"Failed to focus window: {e}")
        return False, f"Window focus failed: {e}"
    
    # Step 4: Open chat
    try:
        chat_ops.open_chat(keybinding=keybinding)
        logger.info("✓ Chat opened")
    except chat_ops.ChatOperationError as e:
        logger.error(str(e))
        return False, str(e)
    
    # Step 5: Type message
    try:
        if send_enter:
            chat_ops.type_message(message)
        else:
            chat_ops.type_without_send(message)
        logger.info(f"✓ Message typed ({len(message)} chars)")
    except chat_ops.ChatOperationError as e:
        logger.error(str(e))
        return False, str(e)
    
    # Step 6: Send if requested
    if send_enter:
        try:
            chat_ops.send_message()
            logger.info("✓ Message sent")
        except chat_ops.ChatOperationError as e:
            logger.error(str(e))
            return False, str(e)
    else:
        logger.info("Message typed (awaiting manual send)")
    
    # Step 7: Verify delivery
    if verify and count_before is not None:
        if session_verify.verify_message_delivery(
            agent_pattern,
            count_before,
            timeout_sec=timeout_sec
        ):
            logger.info(f"✓ Message verified delivered to {agent_pattern}")
            return True, None
        else:
            logger.warning("Verification failed - message may not have delivered")
            return False, f"Verification timeout ({timeout_sec}s)"
    
    logger.info(f"✓ Message sent to {agent_pattern} (unverified)")
    return True, None


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 3:
        print("HERMES Direct v2 - Send message to VS Code Copilot agent")
        print()
        print("Usage:")
        print("  python hermes_direct.py <agent> <message> [options]")
        print()
        print("Arguments:")
        print("  <agent>       Agent identifier in window title (e.g., THEIA0, 0.6.Q)")
        print("  <message>     Message to send")
        print()
        print("Options:")
        print("  --no-enter    Type message but don't press Enter (defer send)")
        print("  --no-verify   Skip delivery verification via AppData")
        print("  --timeout N   Verification timeout in seconds (default: 5)")
        print("  --verbose     Enable debug logging")
        print()
        print("Examples:")
        print("  python hermes_direct.py THEIA0 'Hello from HERMES'")
        print("  python hermes_direct.py 0.6.Q 'Check tools' --no-verify")
        print("  python hermes_direct.py self 'Continue' --no-enter --verbose")
        return 1
    
    # Parse arguments
    agent = sys.argv[1]
    message = sys.argv[2]
    
    # Parse flags
    no_enter = '--no-enter' in sys.argv
    no_verify = '--no-verify' in sys.argv
    verbose = '--verbose' in sys.argv
    
    timeout = 5.0
    for i, arg in enumerate(sys.argv):
        if arg == '--timeout' and i + 1 < len(sys.argv):
            try:
                timeout = float(sys.argv[i + 1])
            except ValueError:
                print(f"Error: Invalid timeout value: {sys.argv[i + 1]}")
                return 1
    
    # Configure logging
    configure_logging(verbose=verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 70)
    logger.info(f"HERMES Direct - Agent: {agent}")
    logger.info(f"Message: {message[:60]}..." if len(message) > 60 else f"Message: {message}")
    logger.info(f"Verify: {not no_verify}, Send Enter: {not no_enter}")
    logger.info("=" * 70)
    
    # Don't verify if not sending (message not delivered yet)
    verify_delivery = (not no_verify) and (not no_enter)
    
    success, error = send_message_to_agent(
        agent,
        message,
        verify=verify_delivery,
        timeout_sec=timeout,
        send_enter=(not no_enter)
    )
    
    print()  # Blank line
    if success:
        logger.info(f"✓ SUCCESS: Message sent to {agent}")
        return 0
    else:
        logger.error(f"✗ FAILED: {error}")
        
        # Return appropriate exit code
        if "not found" in str(error).lower() or "no window" in str(error).lower():
            return 2  # Window not found
        elif "timeout" in str(error).lower():
            return 5  # Verification failed
        elif "Chat" in str(error) or "chat" in str(error):
            return 4  # Chat operation failed
        else:
            return 3  # Generic operation failed


if __name__ == "__main__":
    sys.exit(main())
