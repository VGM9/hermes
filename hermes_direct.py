#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HERMES Direct - Send message to agent via UI automation

Finds VS Code window with agent in title, opens chat (Ctrl+I), types message.

Exit codes:
  0 = Success
  1 = Usage error
  2 = Window not found
  3 = Send failed
"""

import sys
import time
import os
import json
from pathlib import Path
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


def safe_print(msg):
    """Print with fallback for non-UTF8 terminals (Windows cp1252)"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace Unicode symbols with ASCII equivalents
        safe_msg = msg.replace('✓', '[OK]').replace('✗', '[FAIL]')
        print(safe_msg.encode('ascii', 'replace').decode('ascii'))


# AppData for verification
APPDATA = Path(os.environ.get('APPDATA', '')) / 'Code - Insiders' / 'User' / 'workspaceStorage'
WORKSPACE_HASHES = ['fc7deee2819a0e3e3f792481dedcbc98', '68569d2de19d99c3fa1fe1eceaa8b90c']


def find_agent_window(agent_pattern):
    """Find VS Code window with agent pattern in title.
    
    Args:
        agent_pattern: String to match in window title (e.g., 'THEIA0', '0.6.Q')
    
    Returns:
        (window, title) or (None, error_message)
    """
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    vscode_windows = []
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" in title:
                vscode_windows.append({'window': win, 'title': title})
                
                if agent_pattern.lower() in title.lower():
                    return win, title
        except:
            pass
    
    if not vscode_windows:
        return None, "No VS Code windows found"
    
    # Build helpful error with available windows
    available = "\n".join(f"  - {w['title'][:60]}..." for w in vscode_windows[:5])
    return None, f"No window matching '{agent_pattern}'. Available:\n{available}"


def get_session_request_count(agent_pattern):
    """Get current request count from session JSON for verification."""
    for hash_dir in WORKSPACE_HASHES:
        sessions_dir = APPDATA / hash_dir / 'chatSessions'
        if not sessions_dir.exists():
            continue
        
        for f in sessions_dir.glob('*.json'):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                title = data.get('customTitle', '')
                if agent_pattern.lower() in title.lower():
                    return len(data.get('requests', []))
            except:
                pass
    return None


def send_message(agent_pattern, message, verify=True, timeout=5.0, no_enter=False):
    """Send message to agent.
    
    Args:
        agent_pattern: Agent name/pattern (e.g., 'theia', 'THEIA0', '0.6.Q')
        message: Message text
        verify: Verify delivery via AppData
        timeout: Verification timeout in seconds
        no_enter: If True, type message but DON'T press Enter (for self-messaging)
    
    Returns:
        (success, error_or_none)
    """
    # Find window
    win, result = find_agent_window(agent_pattern)
    if not win:
        return False, result
    
    print(f"Found: {result[:60]}...")
    
    # Get request count before
    count_before = get_session_request_count(agent_pattern) if verify else None
    
    # Focus window
    win.set_focus()
    time.sleep(0.3)
    
    # Open chat using keyboard shortcut
    # Common shortcuts: Ctrl+Shift+I (Copilot Chat), Ctrl+L (some versions)
    print("Opening chat panel...")
    send_keys('^+i')  # Ctrl+Shift+I (Copilot Chat)
    time.sleep(0.8)
    
    # Type message into chat input (should be focused after opening)
    print(f"Typing message ({len(message)} chars)...")
    send_keys(message, with_spaces=True, pause=0.01)
    time.sleep(0.3)
    
    # Press Enter unless --no-enter
    if not no_enter:
        print("Sending (Enter)...")
        send_keys('{ENTER}')
        time.sleep(0.5)
    else:
        print("Message typed (not sent - use --no-enter)")
    
    # Verify
    if verify and count_before is not None:
        print("Verifying delivery...")
        start = time.time()
        while time.time() - start < timeout:
            count_after = get_session_request_count(agent_pattern)
            if count_after and count_after > count_before:
                safe_print(f"✓ Verified: request count {count_before} -> {count_after}")
                return True, None
            time.sleep(0.5)
        
        return False, f"Verification timeout ({timeout}s). Message may not have been delivered."
    
    safe_print("✓ Sent (unverified)")
    return True, None


def main():
    if len(sys.argv) < 3:
        print("HERMES Direct - Send message to VS Code Copilot agent")
        print()
        print("Usage:")
        print("  python hermes_direct.py <agent> <message>")
        print("  python hermes_direct.py <agent> <message> --no-enter")
        print("  python hermes_direct.py <window> <agent> <message>  # legacy 3-arg")
        print()
        print("Examples:")
        print("  python hermes_direct.py theia 'Hello THEIA!'")
        print("  python hermes_direct.py THEIA0 'Check your tools'")
        print("  python hermes_direct.py 0.6.Q 'Message for 0.6.Q'")
        print("  python hermes_direct.py self 'Continue with this' --no-enter")
        print()
        print("Options (env vars):")
        print("  HERMES_NO_VERIFY=1    Skip delivery verification")
        print("  HERMES_TIMEOUT=10     Verification timeout (default: 5s)")
        print()
        print("Flags:")
        print("  --no-enter            Type message but don't press Enter")
        print("                        (for self-messaging, use with hermes_wait_send.py)")
        sys.exit(1)
    
    # Check for --no-enter flag
    no_enter = '--no-enter' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--no-enter']
    
    # Handle legacy 3-arg format: <window> <session> <message>
    if len(args) >= 3:
        # Ignore window pattern, use session pattern as agent
        agent = args[1]
        message = args[2]
    else:
        agent = args[0]
        message = args[1]
    
    verify = os.environ.get('HERMES_NO_VERIFY', '').lower() not in ('1', 'true', 'yes')
    timeout = float(os.environ.get('HERMES_TIMEOUT', '5'))
    
    # Don't verify if no_enter (message won't be sent yet)
    if no_enter:
        verify = False
    
    success, error = send_message(agent, message, verify=verify, timeout=timeout, no_enter=no_enter)
    
    if success:
        safe_print(f"✓ Message delivered to {agent}")
        sys.exit(0)
    else:
        safe_print(f"✗ FAILED: {error}")
        if "No window" in str(error) or "not found" in str(error).lower():
            sys.exit(2)
        else:
            sys.exit(3)


if __name__ == "__main__":
    main()
