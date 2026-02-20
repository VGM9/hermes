#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HERMES Sessions - Click on sessions in the VS Code Chat Sessions panel

This script can find and click on session items in the tree view to open
closed sessions, enabling HERMES to then send messages to them.
"""

import sys
import time
from pywinauto import Application, findwindows


def find_session_tree_items(window_pattern=None):
    """Find all tree items in VS Code windows that look like chat sessions.
    
    Returns a list of dicts with tree item info.
    """
    results = []
    
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" not in title:
                continue
            
            if window_pattern and window_pattern.lower() not in title.lower():
                continue
            
            # Find Tree Items - these are session entries in the Sessions panel
            try:
                tree_items = win.descendants(control_type="TreeItem")
            except:
                continue
            
            for item in tree_items:
                try:
                    name = item.element_info.name or ""
                    # Session items typically have AS/ or specific patterns
                    if name:
                        results.append({
                            'window_title': title,
                            'window': win,
                            'item_name': name,
                            'item': item
                        })
                except:
                    pass
        except:
            pass
    
    return results


def list_sessions(window_pattern=None):
    """List all found session tree items."""
    items = find_session_tree_items(window_pattern)
    
    print(f"Found {len(items)} TreeItem controls:")
    print("=" * 70)
    
    for i, item in enumerate(items):
        title = item['window_title'][:50].encode('ascii', 'replace').decode('ascii')
        name = item['item_name'][:60].encode('ascii', 'replace').decode('ascii')
        print(f"\n[{i}] Window: {title}...")
        print(f"    Item: {name}")
    
    print("\n" + "=" * 70)
    return items


def click_session(pattern: str, window_pattern=None):
    """Click on a session tree item matching the pattern.
    
    Args:
        pattern: String to match against the tree item name
        window_pattern: Optional string to filter windows
    """
    items = find_session_tree_items(window_pattern)
    
    print(f"Looking for session matching: '{pattern}'")
    print(f"Found {len(items)} tree items total")
    
    target = None
    for item in items:
        if pattern.lower() in item['item_name'].lower():
            target = item
            print(f"  MATCH: {item['item_name'][:60]}...")
            break
    
    if not target:
        print(f"No session found matching '{pattern}'")
        print("\nAvailable sessions (filtered by common patterns):")
        for item in items:
            name = item['item_name']
            # Filter to likely session names
            if any(x in name.lower() for x in ['0.', 'cq', 'as/', 'vega', 'altair', 'deneb', 'session']):
                print(f"  - {name[:70]}...")
        return False
    
    print(f"\nFocusing window...")
    try:
        target['window'].set_focus()
        time.sleep(0.3)
    except Exception as e:
        print(f"Warning focusing window: {e}")
    
    print(f"Clicking session: {target['item_name'][:50]}...")
    try:
        # Double-click to open the session
        target['item'].click_input(double=True)
        time.sleep(1.0)
        print("Session clicked!")
        return True
    except Exception as e:
        print(f"Error clicking: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("HERMES Sessions - Click on chat sessions in VS Code")
        print()
        print("Usage:")
        print("  python hermes_sessions.py list [window-pattern]")
        print("  python hermes_sessions.py click <session-pattern> [window-pattern]")
        print()
        print("Examples:")
        print("  python hermes_sessions.py list")
        print("  python hermes_sessions.py list 'VGM9'")
        print("  python hermes_sessions.py click '0.5.Q'")
        print("  python hermes_sessions.py click 'DENEB' 'VGM9'")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        window_pat = sys.argv[2] if len(sys.argv) > 2 else None
        list_sessions(window_pat)
    elif cmd == "click":
        if len(sys.argv) < 3:
            print("Usage: python hermes_sessions.py click <session-pattern> [window-pattern]")
            return
        pattern = sys.argv[2]
        window_pat = sys.argv[3] if len(sys.argv) > 3 else None
        click_session(pattern, window_pat)
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
