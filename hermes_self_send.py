#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# DEPRECATED: This tool uses Ctrl+I which triggers voice input, not chat
# DO NOT USE
"""
HERMES Self-Send - Send a message to yourself (same session)

**DEPRECATED - DO NOT USE**
Uses Ctrl+I which triggers voice input microphone, not chat.

This enables an agent to trigger a new turn by:
1. Typing message into their own chat input (no Enter - send button is hidden while agent runs)
2. Starting a background watcher
3. Agent finishes turn (stop button disappears, send button appears)
4. Background watcher clicks send

Usage:
    python hermes_self_send.py "Your message here"
    
The script:
1. Types the message into the focused chat input (NO Enter)
2. Spawns a background process that watches for send button
3. When send button appears, clicks it

Author: ALTAIR lineage (0.0.Q → 0.8.Q)
"""

import sys
import time
import subprocess
from pathlib import Path

# Import from sibling hermes_direct
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


def type_without_send(message: str):
    """Type a message into the current chat input but do NOT press Enter.
    
    This is for self-messaging: the agent types, then a background process
    clicks send after the agent stops.
    """
    # Find VS Code window (assume the current/focused one)
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" not in title:
                continue
            
            # This should be the focused window with the agent
            print(f"Found VS Code: {title[:60]}...")
            
            # Focus and type
            win.set_focus()
            time.sleep(0.3)
            
            # Type the message (NO Enter)
            print(f"Typing message ({len(message)} chars)...")
            send_keys(message, with_spaces=True, pause=0.02)
            
            safe_print("✓ Message typed (NOT sent)")
            return True
            
        except Exception as e:
            print(f"Error with window: {e}")
            continue
    
    safe_print("✗ No VS Code window found")
    return False


def spawn_deferred_send():
    """Spawn a background process that waits for send button and clicks it.
    
    This process monitors for the send button to become available
    (which happens when the agent stops generating) and then clicks it.
    """
    # Spawn the watcher as a detached background process
    watcher_script = SCRIPT_DIR / "hermes_wait_send.py"
    
    if not watcher_script.exists():
        safe_print(f"✗ Watcher script not found: {watcher_script}")
        print("  Creating it now...")
        create_watcher_script(watcher_script)
    
    # Run in background (detached)
    print("Spawning background watcher...")
    subprocess.Popen(
        ["python", str(watcher_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    )
    safe_print("✓ Watcher spawned")


def create_watcher_script(path: Path):
    """Create the watcher script that waits for send button."""
    content = '''#!/usr/bin/env python3
"""
HERMES Wait-Send - Background watcher that clicks send when available

Spawned by hermes_self_send.py, this script:
1. Waits for the send button to appear (agent stopped generating)
2. Clicks the send button
3. Exits

This enables the self-messaging flow where an agent types a message,
finishes their turn, and then this watcher sends it.
"""

import time
import sys
from pywinauto import Application, findwindows


def safe_print(msg):
    """Print with fallback for non-UTF8 terminals (Windows cp1252)"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace Unicode symbols with ASCII equivalents
        safe_msg = msg.replace('✓', '[OK]').replace('✗', '[FAIL]')
        print(safe_msg.encode('ascii', 'replace').decode('ascii'))

MAX_WAIT_SECONDS = 60  # Give up after 1 minute


def find_send_button():
    """Find the send button in VS Code chat."""
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" not in title:
                continue
            
            # Look for send button
            buttons = win.descendants(control_type="Button")
            for btn in buttons:
                try:
                    name = (btn.element_info.name or "").lower()
                    if "send" in name:
                        return btn, win
                except:
                    pass
        except:
            pass
    
    return None, None


def main():
    print("Waiting for send button...")
    start = time.time()
    
    while time.time() - start < MAX_WAIT_SECONDS:
        btn, win = find_send_button()
        
        if btn:
            try:
                # Verify it's clickable (not hidden/disabled)
                if btn.is_visible() and btn.is_enabled():
                    print("Send button found! Clicking...")
                    win.set_focus()
                    time.sleep(0.2)
                    btn.click_input()
                    safe_print("✓ Sent!")
                    return 0
            except Exception as e:
                print(f"Button found but click failed: {e}")
        
        time.sleep(0.5)
    
    safe_print("✗ Timeout waiting for send button")
    return 1


if __name__ == "__main__":
    sys.exit(main())
'''
    path.write_text(content)
    safe_print(f"✓ Created: {path}")


def main():
    if len(sys.argv) < 2:
        print("HERMES Self-Send - Send a message to yourself")
        print()
        print("Usage:")
        print("  python hermes_self_send.py <message>")
        print()
        print("This enables an agent to send a message to their own session.")
        print("The message is typed, then a background watcher clicks send")
        print("after the agent finishes generating.")
        return 1
    
    message = sys.argv[1]
    
    # Step 1: Type without sending
    if not type_without_send(message):
        return 1
    
    # Step 2: Spawn background watcher
    spawn_deferred_send()
    
    print()
    print("Self-send initiated!")
    print("When you finish generating, the watcher will click send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
