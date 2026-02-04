#!/usr/bin/env python3
# DEPRECATED: Relies on hermes_self_send.py which is broken (Ctrl+I = voice input)
# DO NOT USE
"""
HERMES Wait-Send - Background watcher that clicks send when available

Spawned by hermes_self_send.py, this script:
1. Waits for the send button to appear (agent stopped generating)
2. Clicks the send button
3. Exits

This enables the self-messaging flow where an agent types a message,
finishes their turn, and then this watcher sends it.

Author: ALTAIR lineage (0.0.Q → 0.8.Q)
"""

import time
import sys
from pywinauto import Application, findwindows

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
                    # Send button or submit button
                    if "send" in name or name == "submit":
                        return btn, win
                except:
                    pass
        except:
            pass
    
    return None, None


def main():
    print("HERMES Wait-Send: Watching for send button...")
    start = time.time()
    
    while time.time() - start < MAX_WAIT_SECONDS:
        btn, win = find_send_button()
        
        if btn:
            try:
                # Verify it's clickable (not hidden/disabled)
                if btn.is_visible() and btn.is_enabled():
                    print(f"[{time.time() - start:.1f}s] Send button found! Clicking...")
                    win.set_focus()
                    time.sleep(0.2)
                    btn.click_input()
                    print("✓ Message sent!")
                    return 0
            except Exception as e:
                print(f"Button found but click failed: {e}")
        
        time.sleep(0.5)
    
    print(f"✗ Timeout after {MAX_WAIT_SECONDS}s waiting for send button")
    return 1


if __name__ == "__main__":
    sys.exit(main())
