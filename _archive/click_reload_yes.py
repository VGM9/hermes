#!/usr/bin/env python3
import sys, time, pywinauto

def click_yes(timeout=10):
    print("[AUTO] Looking for reload dialog...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            desktop = pywinauto.Desktop(backend="uia")
            for win in [w for w in desktop.windows() if "Visual Studio Code" in w.window_text()]:
                try:
                    # Find dialog by text
                    if any("chat request is in progress" in d.window_text().lower() 
                           for d in win.descendants()):
                        # Find Yes button
                        for btn in win.descendants(control_type="Button"):
                            if btn.window_text() == "Yes":
                                print("[AUTO] Clicking Yes")
                                btn.click_input()
                                return True
                except: pass
            time.sleep(0.3)
        except: pass
    return False

sys.exit(0 if click_yes(15) else 1)
