"""Minimal test of Desktop.windows() iteration."""

from pywinauto import Desktop
import time

print("Creating Desktop object...", flush=True)
start = time.time()
desktop = Desktop(backend='uia')
print(f"Desktop created in {time.time() - start:.2f}s", flush=True)

print("\nIterating windows...", flush=True)
count = 0
vscode_count = 0
start = time.time()

for window in desktop.windows():
    count += 1
    try:
        class_name = window.class_name()
        if class_name == "Chrome_WidgetWin_1":
            title = window.window_text()
            print(f"  VSCode window: {title[:60]}", flush=True)
            vscode_count += 1
    except:
        pass
    
    # Safety limit
    if count > 200:
        print("  (stopping at 200 windows)", flush=True)
        break

elapsed = time.time() - start
print(f"\nEnumerated {count} windows in {elapsed:.2f}s", flush=True)
print(f"Found {vscode_count} VSCode windows", flush=True)
