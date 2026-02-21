"""Test global button finding approach."""

from core.ui_automation.element_detection import find_all_approval_buttons_globally
import time

print("Testing global button search...", flush=True)
start = time.time()

buttons = find_all_approval_buttons_globally()

elapsed = time.time() - start
print(f"\nCompleted in {elapsed:.2f}s", flush=True)
print(f"Found {len(buttons)} approval button(s)\n", flush=True)

for btn_info in buttons:
    print(f"{btn_info['type'].upper()} button:")
    print(f"  Window handle: {btn_info['window_handle']}")
    print(f"  Text: {btn_info['button'].name}")
    print()
