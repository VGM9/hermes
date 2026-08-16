"""Inspect accessible controls in VS Code windows without interaction."""

import sys

from pywinauto import Desktop


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for window in Desktop(backend="uia").windows(visible_only=True):
        title = window.window_text().strip()
        if "Visual Studio Code" not in title:
            continue
        print(f"WINDOW {title}")
        for button in window.descendants(control_type="Button"):
            label = button.window_text().strip()
            if label:
                print(f"BUTTON {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())