"""Probe legacy target discovery without delivering input."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ui_automation.window_detection import (
    VSCODE_WINDOW_CLASS_NAME,
    find_agent_mode_in_window,
    find_target_window,
)
from pywinauto import Desktop


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-jsonl", required=True)
    parser.add_argument("--agent-mode", required=True)
    args = parser.parse_args()
    for window in Desktop(backend="uia").windows(visible_only=True):
        title = window.window_text().strip()
        if "AO_SLUMBER_BHARTI_AS" in title:
            print(
                f"candidate title={title!r} class={window.class_name()!r} "
                f"agent={find_agent_mode_in_window(window)!r} "
                f"expected_class={VSCODE_WINDOW_CLASS_NAME!r}"
            )
    window = find_target_window(args.session_jsonl, args.agent_mode)
    if window is None:
        print("target: NOT_FOUND")
        return 1
    print(f"target: FOUND title={window.window_text()!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())