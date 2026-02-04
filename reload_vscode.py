#!/usr/bin/env python3
"""
Trigger VS Code window reload via keyboard automation
"""
import time
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys

def reload_vscode():
    """Send Ctrl+Shift+P then type 'Developer: Reload Window' and Enter"""
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if "Visual Studio Code" not in title:
                continue
            
            if "ALTAIR0" in title:  # Target the main agent window
                print(f"Found: {title[:60]}...")
                win.set_focus()
                time.sleep(0.3)
                
                # Open command palette
                print("Opening command palette (Ctrl+Shift+P)...")
                send_keys('^+p')
                time.sleep(0.5)
                
                # Type reload command
                print("Typing reload command...")
                send_keys('Developer: Reload Window', with_spaces=True, pause=0.02)
                time.sleep(0.3)
                
                # Execute
                print("Pressing Enter...")
                send_keys('{ENTER}')
                
                print("✓ Reload triggered")
                return True
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print("✗ No matching window found")
    return False

if __name__ == "__main__":
    reload_vscode()
