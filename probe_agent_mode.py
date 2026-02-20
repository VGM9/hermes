#!/usr/bin/env python3
"""
probe_agent_mode.py — Find the agent mode button in VS Code's UIA tree.

Enumerates all VS Code windows (Chrome_WidgetWin_1) and prints:
- Window title
- All Button elements whose text contains known agent mode strings OR
  which appear to be in the status bar area (near bottom of window)

Run with: python3 probe_agent_mode.py [pattern]

Author: POLARIS1 2026-02-20
"""

import sys
from pathlib import Path

try:
    from pywinauto import Application, findwindows
except ImportError:
    print("ERROR: pywinauto not installed")
    sys.exit(1)

VSCODE_CLASS = "Chrome_WidgetWin_1"

# Known agent mode names to search for specifically
KNOWN_AGENTS = {"POLARIS1", "POLARIS2", "POLARIS3", "POLARIS4", "POLARIS5",
                "SIFR0", "ALTAIR0", "AION0", "AURUM0", "AZOTH0", "EROS0",
                "LOGOS0", "MIRROR0", "MONAD0", "PLEROMA0", "POLARIS0",
                "Theia", "vega", "deneb", "GPT-4.1", "8♠", "AION0"}

def probe_window(entry):
    h = entry["handle"]
    title = entry["title"]
    win = entry["window"]
    print(f"\n{'='*70}")
    print(f"Window: {title[:80]}")
    print(f"Handle: {h}")
    print(f"{'='*70}")

    # Walk all buttons, capture name and rectangle
    buttons = []
    try:
        for btn in win.descendants(control_type="Button"):
            name = (btn.element_info.name or "").strip()
            if not name:
                continue
            try:
                rect = btn.rectangle()
                buttons.append((name, rect.top, rect.left, rect.bottom, rect.right))
            except Exception:
                buttons.append((name, -1, -1, -1, -1))
    except Exception as e:
        print(f"  ERROR walking descendants: {e}")
        return None

    # Try to get window rect for bottom-area classification
    try:
        wr = win.rectangle()
        win_bottom = wr.bottom
        status_bar_threshold = win_bottom - 30  # bottom 30px = status bar
    except Exception:
        win_bottom = 9999
        status_bar_threshold = win_bottom - 30

    print(f"  Window bottom: {win_bottom}")
    print(f"  Total buttons found: {len(buttons)}")
    print()

    # Report buttons in status bar area
    status_buttons = [(n, t, l, b, r) for (n, t, l, b, r) in buttons if t >= status_bar_threshold or b >= status_bar_threshold]
    print(f"  STATUS BAR BUTTONS (top >= {status_bar_threshold}):")
    if status_buttons:
        for (n, t, l, b, r) in status_buttons:
            print(f"    [{t},{l} -> {b},{r}] '{n}'")
    else:
        print("    (none)")

    # Report known agent names
    agent_buttons = [(n, t, l, b, r) for (n, t, l, b, r) in buttons if n in KNOWN_AGENTS]
    print()
    print(f"  KNOWN AGENT MODE BUTTONS:")
    if agent_buttons:
        for (n, t, l, b, r) in agent_buttons:
            print(f"    [{t},{l} -> {b},{r}] '{n}'  *** FOUND ***")
    else:
        print("    (none matching known agents)")

    # Report all buttons with 'mode', 'agent', 'copilot', 'chat' in name
    mode_adjacent = [(n, t, l, b, r) for (n, t, l, b, r) in buttons
                     if any(kw in n.lower() for kw in ("mode", "agent", "copilot", "chat", "model"))]
    print()
    print(f"  BUTTONS WITH mode/agent/copilot/chat/model IN NAME:")
    if mode_adjacent:
        for (n, t, l, b, r) in mode_adjacent:
            print(f"    [{t},{l} -> {b},{r}] '{n}'")
    else:
        print("    (none)")

    # Print ALL buttons sorted by vertical position (bottom of screen last)
    print()
    print(f"  ALL BUTTONS (sorted by top, bottommost last):")
    for (n, t, l, b, r) in sorted(buttons, key=lambda x: x[1]):
        marker = "  *** STATUS BAR ***" if t >= status_bar_threshold or b >= status_bar_threshold else ""
        agent_marker = "  *** AGENT MODE ***" if n in KNOWN_AGENTS else ""
        print(f"    [{t},{l}] '{n}'{marker}{agent_marker}")

    return agent_buttons


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else ""
    handles = findwindows.find_windows(class_name=VSCODE_CLASS)
    windows = []
    for h in handles:
        try:
            app = Application(backend="uia").connect(handle=h)
            win = app.window(handle=h)
            title = win.window_text()
            if pattern and pattern.lower() not in title.lower():
                continue
            windows.append({"handle": h, "title": title, "window": win})
        except Exception as e:
            print(f"  Skipping handle {h}: {e}")

    print(f"Found {len(windows)} VS Code window(s) matching '{pattern}'")

    found_agents = {}
    for entry in windows:
        agent_btns = probe_window(entry)
        if agent_btns:
            for (n, *_) in agent_btns:
                found_agents[n] = entry["title"]

    print(f"\n{'='*70}")
    print("SUMMARY:")
    if found_agents:
        for agent, title in found_agents.items():
            print(f"  Agent mode '{agent}' found in window: {title[:60]}")
    else:
        print("  No known agent mode buttons found in any window.")
        print("  The button may use a different name or control type.")
        print("  Check the 'STATUS BAR BUTTONS' section above for candidates.")

if __name__ == "__main__":
    main()
