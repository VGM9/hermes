#!/usr/bin/env python3
"""
Integration test for hermes#35: switch_to_session_via_quick_pick.

Reads agent mode from session JSONL, finds a VS Code window,
attempts session switch, verifies "Set Agent" button changed.

Run from hermes-dev directory:
  python3 test_session_switch_live.py

Author: AION0 — TDD for hermes#35
"""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if len(sys.argv) < 2:
    print("Usage: python3 test_session_switch_live.py <path/to/source_session.jsonl>", file=sys.stderr)
    sys.exit(1)
JSONL_POLARIS4 = sys.argv[1]

# ── 1. Extract customTitle from JSONL ────────────────────────────────────────
from core.ui_automation.session_switcher import get_session_custom_title

title = get_session_custom_title(JSONL_POLARIS4)
print(f"[1] customTitle: {title!r}")
assert title, "customTitle not found — ABORT"

# ── 2. Extract agent mode from JSONL (v.inputState.mode.id is a file URI) ────
def get_session_agent_mode(jsonl_path: str):
    """Extract the agent mode name from v.inputState.mode.id in JSONL.
    
    The mode.id is a file URI like:
      file:///c%3A/www/VGM9/.github/agents/LOGOS0.agent.md
    The stem = agent name.
    """
    from urllib.parse import unquote
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                    v = obj.get("v", {})
                    mode_id = v.get("inputState", {}).get("mode", {}).get("id", "")
                    if mode_id and "agents" in mode_id:
                        stem = Path(unquote(mode_id.replace("file:///", "").replace("file://", ""))).stem
                        # stem is e.g. "POLARIS4.agent" — strip .agent suffix
                        if stem.endswith(".agent"):
                            stem = stem[:-6]
                        return stem
                except (json.JSONDecodeError, TypeError):
                    pass
    except OSError:
        pass
    return None

target_mode = get_session_agent_mode(JSONL_POLARIS4)
print(f"[2] session agent mode from JSONL: {target_mode!r}")

# ── 3. Find a VS Code window for this workspace ───────────────────────────────
from pywinauto import Desktop
from core.ui_automation.window_detection import find_agent_mode_in_window
from vscode_ground_truth import VSCODE_WINDOW_CLASS_NAME

desktop = Desktop(backend="uia")

windows = []
all_vscode = []
for win in desktop.windows():
    try:
        if win.class_name() != VSCODE_WINDOW_CLASS_NAME:
            continue
        title_text = win.window_text()
        if "visual studio code" not in title_text.lower():
            continue
        all_vscode.append(win)
        windows.append(win)
    except Exception:
        continue

print(f"[3] VS Code windows found: {len(windows)}")
for w in windows:
    try:
        print(f"   title: {w.window_text()!r}")
    except Exception:
        pass

# Pick the window whose title contains this session's customTitle
win = None
for w in windows:
    try:
        if title and title[:30].lower() in w.window_text().lower():
            win = w
            break
    except Exception:
        pass
if win is None and windows:
    # Fallback: pick first window that has an actual agent mode set
    for w in windows:
        m = find_agent_mode_in_window(w)
        if m and m != "Open Agent Picker":
            win = w
            break
if win is None:
    print("  No suitable window found — SKIP")
    sys.exit(0)
print(f"   selected: {win.window_text()!r}")
if not windows:
    print("  No VS Code windows for this workspace — SKIP live test")
    sys.exit(0)

win = windows[0]
mode_before = find_agent_mode_in_window(win)
print(f"[4] mode before switch: {mode_before!r}")

# ── 4. Pick a DIFFERENT session to switch to (auto-discover from chatSessions dir) ─────────
JSONL_POLARIS1 = None  # hardcoded UUID removed (qopilot#19)
title_p1 = get_session_custom_title(JSONL_POLARIS1) if JSONL_POLARIS1 else None
print(f"[5] alternate session title (from discovery): {title_p1!r}")

# Find a valid target session: any other JSONL in the same chatSessions dir with a real title
chat_sessions_dir = Path(JSONL_POLARIS4).parent
others = [f for f in chat_sessions_dir.glob("*.jsonl")
          if f.name != Path(JSONL_POLARIS4).name]
target_jsonl = None
target_title = title_p1
if not target_title:
    for other in sorted(others, key=lambda f: f.stat().st_mtime, reverse=True):
        t = get_session_custom_title(str(other))
        if t:
            target_jsonl = str(other)
            target_title = t
            print(f"  Using fallback target: {other.name[:8]}... title={t!r}")
            break
if not target_jsonl:
    target_jsonl = JSONL_POLARIS1

if not target_title:
    print("  No valid target session found — SKIP")
    sys.exit(0)

# ── 5. Attempt switch ─────────────────────────────────────────────────────────
from core.ui_automation.session_switcher import switch_to_session_via_quick_pick

print(f"[6] Attempting switch to: {target_title!r}")
title_before_switch = win.window_text()
result = switch_to_session_via_quick_pick(win, target_title, timeout_ms=3000)
print(f"[7] switch returned: {result}")

# Poll for mode/title change up to 4 seconds
mode_after = None
title_after = None
for attempt in range(8):
    time.sleep(0.5)
    try:
        title_after = win.window_text()
        mode_after = find_agent_mode_in_window(win)
        print(f"  poll {attempt+1}: title={title_after[:50]!r} mode={mode_after!r}")
        if mode_after and mode_after != "Open Agent Picker":
            break
    except Exception as e:
        print(f"  poll {attempt+1}: exception {e}")

print(f"[8] mode after switch: {mode_after!r}")
print(f"    window title before: {title_before_switch[:60]!r}")
print(f"    window title after:  {(title_after[:60] if title_after else None)!r}")

# ── 6. Result ─────────────────────────────────────────────────────────────────
if mode_after and mode_before and mode_after.lower() != mode_before.lower():
    print(f"\n✅ PASS — session switched: {mode_before} → {mode_after}")
elif mode_after and mode_after.lower() == mode_before.lower():
    print(f"\n⚠ INCONCLUSIVE — mode unchanged: {mode_after}")
    print("  Either: (a) both sessions share same agent mode, or (b) switch failed")
    target_mode_p1 = get_session_agent_mode(target_jsonl)
    print(f"  target session agent mode (from JSONL): {target_mode_p1!r}")
    if target_mode_p1 and mode_after and mode_after.lower() == target_mode_p1.lower():
        print(f"  \u2705 PASS — mode matches target session mode")
    else:
        print(f"  ❌ FAIL — mode {mode_after!r} != expected {target_mode_p1!r}")
        sys.exit(1)
else:
    print(f"\n❌ FAIL — mode_after={mode_after!r}")
    sys.exit(1)
