#!/usr/bin/env python3
"""
Inspect all Edit controls in VS Code windows to understand structure.
"""

from pywinauto import Application, findwindows
import sys


def inspect_window(pattern: str):
    """Inspect all Edit controls in a matching window."""
    
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
            
            # Find ALL Edit controls
            edits = win.descendants(control_type="Edit")
            print(f"Found {len(edits)} Edit controls:\n")
            
            for i, edit in enumerate(edits):
                try:
                    name = edit.window_text()
                    rect = edit.rectangle()
                    
                    # Get parent chain
                    parents = []
                    parent = edit.parent()
                    depth = 0
                    while parent and depth < 5:
                        try:
                            pname = parent.window_text()[:30] if parent.window_text() else "(no name)"
                            ptype = parent.element_info.control_type
                            parents.append(f"{ptype}: {pname}")
                        except:
                            parents.append("(error)")
                        parent = parent.parent()
                        depth += 1
                    
                    print(f"Edit #{i}:")
                    print(f"  Name: {name[:100] if name else '(empty)'}...")
                    print(f"  Rect: {rect.left}, {rect.top}, {rect.width()}x{rect.height()}")
                    print(f"  Parents: {' > '.join(parents[:3])}")
                    print()
                    
                except Exception as e:
                    print(f"Edit #{i}: Error - {e}\n")
            
            break
            
        except Exception as e:
            print(f"Error with handle {handle}: {e}")


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "VGM9"
    inspect_window(pattern)
