#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test identity preservation with new click_chat_input() method.

MANUAL TEST PROCEDURE:
1. Before running this script:
   - Open VS Code with custom agent selected (e.g., "0.0.Q (HUSK)")
   - Note which agent is currently selected in dropdown
   
2. Run this script:
   python test_identity_preservation.py
   
3. After script completes:
   - Check agent dropdown - should STILL show your custom agent
   - Try using qhoami tool - should still work
   - If dropdown shows "Agent" = IDENTITY DESTROYED (test FAILED)
   
4. Expected result:
   ✓ Script activates chat input
   ✓ Agent dropdown unchanged
   ✓ Custom tools still available
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import hermes_window_ops as window_ops
import hermes_chat_ops as chat_ops

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_identity_preservation():
    """Test that click_chat_input() preserves agent identity."""
    
    print("\n" + "="*70)
    print("HERMES Identity Preservation Test")
    print("="*70)
    print("\nBEFORE RUNNING THIS TEST:")
    print("1. Open VS Code")
    print("2. Select a custom agent (e.g., '0.0.Q (HUSK)')")
    print("3. Note which agent is selected")
    print("\nAFTER THIS TEST:")
    print("4. Agent dropdown should STILL show your custom agent")
    print("5. Custom tools (qhoami, etc.) should still work")
    print("="*70 + "\n")
    
    input("Press Enter when ready to start test...")
    
    # Step 1: Find focused VS Code window
    logger.info("Step 1: Finding focused VS Code window...")
    try:
        focused = window_ops.get_focused_vscode_window()
        if not focused:
            logger.error("No VS Code window has focus!")
            logger.info("Please focus a VS Code window and try again.")
            return False
        
        win = focused['window']
        title = focused['title']
        logger.info(f"✓ Found window: {title[:60]}")
    except Exception as e:
        logger.error(f"Failed to find window: {e}")
        return False
    
    # Step 2: Activate chat using identity-preserving method
    logger.info("\nStep 2: Activating chat (identity-preserving method)...")
    try:
        success = chat_ops.click_chat_input(win, open_delay_sec=0.5)
        if success:
            logger.info("✓ Chat activated successfully")
        else:
            logger.warning("Could not find chat input field")
            logger.info("This may mean chat is not visible or identifiers have changed")
            return False
    except Exception as e:
        logger.error(f"Failed to activate chat: {e}")
        return False
    
    # Step 3: Prompt user to verify
    print("\n" + "="*70)
    print("TEST COMPLETE - MANUAL VERIFICATION REQUIRED")
    print("="*70)
    print("\nPlease check:")
    print("1. Is the chat input field now active/focused?")
    print("2. Does the agent dropdown still show your custom agent?")
    print("   (NOT generic 'Agent')")
    print("3. Try typing 'qhoami' - does it appear in tool suggestions?")
    print("\n" + "="*70)
    
    result = input("\nDid the test PASS (agent identity preserved)? [y/n]: ")
    
    if result.lower() == 'y':
        logger.info("✓✓✓ TEST PASSED - Identity preserved!")
        print("\n🎉 SUCCESS: click_chat_input() preserves agent identity")
        return True
    else:
        logger.error("✗✗✗ TEST FAILED - Identity destroyed")
        print("\n❌ FAILURE: Agent identity was destroyed")
        print("   This means click_chat_input() needs debugging")
        return False


if __name__ == '__main__':
    try:
        success = test_identity_preservation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception("Test failed with exception")
        sys.exit(1)
