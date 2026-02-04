"""Test window detection."""

from core.ui_automation.window_detection import find_vscode_windows, has_chat_panel

print("Finding VSCode windows...", flush=True)
windows = find_vscode_windows()

print(f"Found {len(windows)} VSCode window(s)\n")

for i, win in enumerate(windows, 1):
    print(f"Window #{i}:")
    print(f"  Title: {win.title}")
    print(f"  Class: {win.class_name}")
    print(f"  Handle: {win.handle}")
    print(f"  PID: {win.process_id}")
    
    # Check if it has chat panel
    has_chat = has_chat_panel(win)
    print(f"  Has chat panel: {has_chat}")
    print()
