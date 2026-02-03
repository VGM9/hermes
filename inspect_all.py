#!/usr/bin/env python3
"""
Inspect ALL controls in a VS Code window, not just Edits.
Look for any control that might be the chat input.
"""

from pywinauto import Application, findwindows
import sys


def inspect_all(pattern: str):
    """Inspect all controls in a matching window."""
    
    handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
    
    for handle in handles:
        try:
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            title = win.window_text()
            
            if pattern.lower() not in title.lower():
                continue
                
            print(f"Window: {title[:80]}...")
            print("=" * 60)
            
            # Get all descendants
            all_elems = win.descendants()
            print(f"Total descendants: {len(all_elems)}")
            
            # Find anything with "chat" or "input" in name
            print("\n--- Elements with 'chat', 'input', 'ask', 'copilot' in name ---")
            for elem in all_elems:
                try:
                    name = elem.window_text().lower()
                    ctrl_type = elem.element_info.control_type
                    if any(kw in name for kw in ['chat', 'input', 'ask', 'copilot', 'send', 'message']):
                        print(f"{ctrl_type}: {elem.window_text()[:80]}")
                except:
                    pass
            
            # Find Edit controls specifically
            print("\n--- All Edit controls ---")
            edits = [e for e in all_elems if e.element_info.control_type == "Edit"]
            for edit in edits:
                try:
                    print(f"Edit: {edit.window_text()[:100]}")
                except:
                    print("Edit: (error reading)")
            
            # Find Document controls (might be rich text inputs)
            print("\n--- All Document controls ---")
            docs = [e for e in all_elems if e.element_info.control_type == "Document"]
            for doc in docs:
                try:
                    print(f"Document: {doc.window_text()[:100]}")
                except:
                    print("Document: (error reading)")
            
            break
            
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "VGM9"
    inspect_all(pattern)
