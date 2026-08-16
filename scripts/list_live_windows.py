"""List visible top-level windows without activating them."""

from pywinauto import Desktop


def main() -> int:
    windows = Desktop(backend="uia").windows(visible_only=True)
    for window in windows:
        title = window.window_text().strip()
        if title:
            print(title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())