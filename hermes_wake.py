#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HERMES Wake - Detect and approve comatose agents

An agent is comatose when waiting for user approval on a command.
This tool detects the "Allow" button with dropdown chevron and
selects the most permissive option to wake the agent.

The Allow button is a SplitButton with options:
- Allow (run this command once)
- Always Allow (run this and future similar commands)
- Skip (reject the command)

For maximum agent autonomy, we select "Always Allow" when available.

CRITICAL: Window title alone is NOT sufficient to identify windows!
External chat windows inherit the same title as the main window.
We must distinguish by window TYPE:
- MAIN window: has Activity Bar, Explorer, Editor tabs, Status bar
- EXTERNAL chat window: just has chat panel, no editor infrastructure

We identify MAIN windows by looking for controls like:
- TabList (editor tabs)
- Tree controls for Explorer
- StatusBar
"""

import sys
import time
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


def is_main_window(window):
    """Check if this is the main VS Code window (not external chat).
    
    Main window has session tree items in sidebar.
    We detect by looking for TreeItem controls with session patterns.
    """
    try:
        # Main windows have TreeItem controls for session history
        tree_items = window.descendants(control_type="TreeItem", depth=15)
        
        # Look for session-like tree items (they have AS/, .Q, session patterns)
        for item in tree_items[:30]:
            name = item.element_info.name or ""
            if any(x in name for x in ['/AS/', '.Q', 'Local session', 'session']):
                return True
        
        return False
        
    except:
        return False


def is_external_chat_window(window):
    """Check if this is an external/detached chat window."""
    try:
        # External chat windows have chat input but lack editor infrastructure
        has_chat_input = False
        edits = window.descendants(control_type="Edit", depth=10)
        for edit in edits[:10]:
            name = edit.element_info.name or ""
            if "Chat Input" in name:
                has_chat_input = True
                break
        
        if not has_chat_input:
            return False
        
        # But should NOT have editor tabs or explorer
        return not is_main_window(window)
        
    except:
        return False


def find_all_vscode_windows():
    """Find all VS Code windows, categorized by type."""
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    windows = {
        'main': [],
        'external': [],
        'other': []
    }
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" not in title:
                continue
            
            if is_main_window(win):
                windows['main'].append({'window': win, 'title': title, 'handle': handle})
            elif is_external_chat_window(win):
                windows['external'].append({'window': win, 'title': title, 'handle': handle})
            else:
                windows['other'].append({'window': win, 'title': title, 'handle': handle})
                
        except:
            pass
    
    return windows


def find_agent_window(pattern, prefer_main=True):
    """Find VS Code window containing the target session.
    
    CRITICAL: Do NOT trust window title alone!
    Titles reflect focused chat and can lag/lie across all windows.
    
    Instead, look INSIDE the window:
    1. Check session tree items in sidebar
    2. Check chat input accessible name
    3. Check actual content
    
    Args:
        pattern: String to match in session tree/chat content (NOT title)
        prefer_main: If True, prefer main windows (they have session sidebar)
    
    Returns:
        (window, title, window_type, match_source) or (None, None, None, None)
    """
    all_windows = find_all_vscode_windows()
    
    # Search order: main windows first (they have session sidebar), then external
    search_order = []
    if prefer_main:
        search_order = [('main', e) for e in all_windows['main']] + \
                       [('external', e) for e in all_windows['external']] + \
                       [('other', e) for e in all_windows['other']]
    else:
        search_order = [('external', e) for e in all_windows['external']] + \
                       [('main', e) for e in all_windows['main']] + \
                       [('other', e) for e in all_windows['other']]
    
    for win_type, entry in search_order:
        win = entry['window']
        title = entry['title']
        
        # METHOD 1: Check session tree items (most reliable for main windows)
        try:
            tree_items = win.descendants(control_type="TreeItem")
            for item in tree_items:
                item_name = item.element_info.name or ""
                if pattern.lower() in item_name.lower():
                    return win, title, win_type, f"TreeItem: {item_name[:40]}"
        except:
            pass
        
        # METHOD 2: Check chat input accessible name
        try:
            edits = win.descendants(control_type="Edit")
            for edit in edits:
                edit_name = edit.element_info.name or ""
                if "Chat Input" in edit_name and pattern.lower() in edit_name.lower():
                    return win, title, win_type, f"ChatInput: {edit_name[:40]}"
        except:
            pass
    
    # FALLBACK: title match (unreliable but last resort)
    for win_type, entry in search_order:
        if pattern.lower() in entry['title'].lower():
            return entry['window'], entry['title'], win_type, "Title (UNRELIABLE)"
    
    return None, None, None, None


def find_session_in_main_window(main_window, session_pattern):
    """Find a session tree item in the main window's sidebar.
    
    The main window has a secondary sidebar with chat session history.
    We can click on sessions there to switch which session is active.
    """
    try:
        tree_items = main_window.descendants(control_type="TreeItem")
        for item in tree_items:
            name = item.element_info.name or ""
            if session_pattern.lower() in name.lower():
                return item, name
    except:
        pass
    return None, None


def detect_approval_state(window):
    """Detect if window has pending approval buttons.
    
    Returns dict with:
        - has_approval: True if Allow/Skip buttons found
        - allow_button: The Allow button control (or None)
        - skip_button: The Skip button control (or None)
        - is_split: True if Allow has dropdown (SplitButton)
    """
    state = {
        'has_approval': False,
        'allow_button': None,
        'skip_button': None,
        'is_split': False,
        'all_buttons': []
    }
    
    try:
        # First check for SplitButton (Allow with dropdown)
        # In UIA, a SplitButton may appear as Button with expandable pattern
        buttons = window.descendants(control_type="Button")
        
        for btn in buttons:
            try:
                name = (btn.element_info.name or "").lower()
                
                # Track all relevant buttons for debugging
                if any(x in name for x in ['allow', 'skip', 'run', 'cancel', 'always']):
                    state['all_buttons'].append(btn.element_info.name)
                
                # Allow button detection
                if 'allow' in name and 'skip' not in name:
                    state['allow_button'] = btn
                    state['has_approval'] = True
                    
                    # Check if it's expandable (has dropdown)
                    try:
                        patterns = btn.element_info.control_type
                        # Try to detect if button has expand capability
                        expand = btn.get_expand_collapse_pattern()
                        if expand:
                            state['is_split'] = True
                    except:
                        pass
                
                # Skip button
                if 'skip' in name:
                    state['skip_button'] = btn
                    state['has_approval'] = True
                    
            except:
                pass
                
    except Exception as e:
        state['error'] = str(e)
    
    return state


def approve_agent(window, always=True):
    """Click the Allow button to approve pending command.
    
    Args:
        window: The VS Code window
        always: If True, try to select "Always Allow" from dropdown
    
    Returns:
        True on success
    """
    state = detect_approval_state(window)
    
    if not state['allow_button']:
        print("ERROR: No Allow button found")
        return False
    
    btn = state['allow_button']
    
    if always:
        # Try to expand dropdown and select Always Allow
        print("Attempting to expand Allow dropdown...")
        
        try:
            # Method 1: Look for chevron/dropdown indicator and click it
            # The dropdown is typically to the right of the button text
            rect = btn.rectangle()
            
            # Click on the right edge of button (where chevron is)
            chevron_x = rect.right - 10
            chevron_y = rect.top + (rect.height() // 2)
            
            from pywinauto import mouse
            mouse.click(coords=(chevron_x, chevron_y))
            time.sleep(0.3)
            
            # Now look for menu items
            menu_items = window.descendants(control_type="MenuItem")
            for item in menu_items:
                name = (item.element_info.name or "").lower()
                if 'always' in name:
                    print(f"Found: {item.element_info.name}")
                    item.click_input()
                    print("Clicked 'Always Allow'")
                    return True
            
            # If no menu appeared, try keyboard
            print("No menu found, trying keyboard...")
            send_keys("{DOWN}")  # Open dropdown
            time.sleep(0.2)
            send_keys("{DOWN}")  # Select second option (Always Allow)
            time.sleep(0.1)
            send_keys("{ENTER}")
            return True
            
        except Exception as e:
            print(f"Dropdown failed: {e}, falling back to simple click")
    
    # Fallback: just click Allow
    print("Clicking Allow button...")
    btn.click_input()
    time.sleep(0.5)
    
    # VERIFY the click worked - button should be gone
    return True


def skip_agent(window):
    """Click the Skip button to reject the pending command.
    
    Args:
        window: The VS Code window
    
    Returns:
        True on success
    """
    state = detect_approval_state(window)
    
    if not state['skip_button']:
        print("ERROR: No Skip button found")
        return False
    
    btn = state['skip_button']
    
    print("Clicking Skip button...")
    try:
        btn.click_input()
        time.sleep(0.5)
        print("Clicked Skip button successfully")
        return True
    except Exception as e:
        print(f"Failed to click Skip button: {e}")
        return False


def verify_wake(window, max_attempts=3):
    """Verify the agent is actually awake (no more approval pending).
    
    Returns True if verified awake, False if still comatose.
    """
    for attempt in range(max_attempts):
        time.sleep(1.0)  # Wait for UI to update
        state = detect_approval_state(window)
        if not state['has_approval']:
            return True
        print(f"  Verification attempt {attempt + 1}: Still comatose...")
    return False


def scan_all_windows():
    """Scan all VS Code windows for comatose agents."""
    all_windows = find_all_vscode_windows()
    comatose = []
    
    # Check all window types
    for win_type, entries in all_windows.items():
        for entry in entries:
            try:
                state = detect_approval_state(entry['window'])
                
                if state['has_approval']:
                    comatose.append({
                        'window': entry['window'],
                        'title': entry['title'],
                        'type': win_type,
                        'state': state
                    })
            except:
                pass
    
    return comatose


def main():
    if len(sys.argv) < 2:
        print("HERMES Wake - Detect and approve comatose agents")
        print()
        print("Usage:")
        print("  python hermes_wake.py scan              Scan for comatose agents")
        print("  python hermes_wake.py windows           List all VS Code windows by type")
        print("  python hermes_wake.py detect <pattern>  Check specific window")
        print("  python hermes_wake.py wake <session>    Approve via main window sidebar")
        print("  python hermes_wake.py wake-all          Wake all comatose agents")
        print()
        print("Examples:")
        print("  python hermes_wake.py scan")
        print("  python hermes_wake.py windows")
        print("  python hermes_wake.py wake '0.5.Q'      # Finds in session sidebar")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "windows":
        print("Enumerating VS Code windows...")
        print("=" * 70)
        
        all_windows = find_all_vscode_windows()
        
        for win_type, entries in all_windows.items():
            if entries:
                print(f"\n{win_type.upper()} WINDOWS ({len(entries)}):")
                for entry in entries:
                    title = entry['title'][:65]
                    print(f"  {title}...")
        
        print("\n" + "=" * 70)
        total = sum(len(e) for e in all_windows.values())
        print(f"Total: {total} VS Code windows")
    
    elif cmd == "scan":
        print("Scanning for comatose agents...")
        print("=" * 60)
        
        comatose = scan_all_windows()
        
        if not comatose:
            print("No comatose agents found. All clear.")
            return
        
        print(f"Found {len(comatose)} comatose agent(s):")
        print()
        
        for agent in comatose:
            title = agent['title'][:55]
            win_type = agent['type']
            buttons = agent['state']['all_buttons']
            print(f"  [{win_type.upper()}] {title}...")
            print(f"    Buttons: {buttons}")
        
        print()
        print("Use 'hermes_wake.py wake <session-pattern>' to approve.")
    
    elif cmd == "detect":
        if len(sys.argv) < 3:
            print("Usage: python hermes_wake.py detect <pattern>")
            return
        
        pattern = sys.argv[2]
        print(f"Detecting approval state for '{pattern}'...")
        
        win, title, win_type, match_source = find_agent_window(pattern)
        if not win:
            print(f"No window found containing '{pattern}'")
            return
        
        print(f"Window: {title[:60]}...")
        print(f"Type: {win_type}")
        print(f"Matched via: {match_source}")
        
        state = detect_approval_state(win)
        print(f"Has approval pending: {state['has_approval']}")
        print(f"Allow button: {'FOUND' if state['allow_button'] else 'NOT FOUND'}")
        print(f"Skip button: {'FOUND' if state['skip_button'] else 'NOT FOUND'}")
        print(f"Is split button: {state['is_split']}")
        print(f"All buttons found: {state['all_buttons']}")
    
    elif cmd == "wake":
        if len(sys.argv) < 3:
            print("Usage: python hermes_wake.py wake <session-pattern>")
            return
        
        session_pattern = sys.argv[2]
        print(f"Waking session '{session_pattern}'...")
        
        # Find a MAIN window (which has the session sidebar)
        all_windows = find_all_vscode_windows()
        
        if not all_windows['main']:
            print("ERROR: No main VS Code windows found")
            return
        
        # Try each main window
        for entry in all_windows['main']:
            main_win = entry['window']
            title = entry['title']
            
            print(f"Checking main window: {title[:50]}...")
            
            # Look for the session in the sidebar
            item, item_name = find_session_in_main_window(main_win, session_pattern)
            
            if item:
                print(f"Found session: {item_name[:50]}...")
                
                # Focus and click the session
                main_win.set_focus()
                time.sleep(0.3)
                
                item.click_input(double=True)
                time.sleep(1.0)
                
                # Now check for approval buttons
                state = detect_approval_state(main_win)
                
                if state['has_approval']:
                    print("Approval pending, attempting to click Allow...")
                    
                    # Try multiple times with verification
                    for attempt in range(3):
                        approve_agent(main_win, always=True)
                        
                        # Verify the wake worked
                        time.sleep(1.0)
                        state = detect_approval_state(main_win)
                        
                        if not state['has_approval']:
                            print(f"VERIFIED: Agent awakened after attempt {attempt + 1}!")
                            return
                        else:
                            print(f"  Attempt {attempt + 1} failed, still comatose. Retrying...")
                    
                    print("FAILED: Could not wake agent after 3 attempts")
                    print("Manual intervention required.")
                    return
                else:
                    print("No approval pending for this session")
                    return
        
        print(f"Session '{session_pattern}' not found in any main window sidebar")
    
    elif cmd == "wake-all":
        print("Waking all comatose agents...")
        
        comatose = scan_all_windows()
        
        if not comatose:
            print("No comatose agents found.")
            return
        
        for agent in comatose:
            title = agent['title'][:40]
            print(f"Waking: {title}...")
            
            agent['window'].set_focus()
            time.sleep(0.3)
            
            approve_agent(agent['window'], always=True)
            time.sleep(0.5)
        
        print(f"Attempted to wake {len(comatose)} agent(s)")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
