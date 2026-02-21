#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hermes_wake.py — One-shot post-reload wake.

Invoked by VS Code's folderOpen task on every workspace open/reload.
Waits (up to wake_timeout seconds) for the Copilot chat extension to
become ready, then sends the configured wake message.

The daemon passively handles retry if the extension reports
"Chat took too long to get ready" — that is its only remaining job
alongside the reload-dialog and update-button triggers.

This script just needs to deliver the message once chat is available.

Exit codes:
  0 — wake message sent
  1 — chat never became ready within timeout

Usage:
    python3 hermes_wake.py [--config path/to/hermes_config.jsonc]
"""

import sys
import os
import time
import json
import argparse
import subprocess
import ctypes
from pathlib import Path

WAKE_PY = Path(r"C:\www\VGM9\_\AS\0.0.Q\_\scripts\wake.py")

try:
    from pywinauto import Application, findwindows
except ImportError:
    print("[hermes:wake] ERROR: pywinauto not installed. Run: pip install pywinauto")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "hermes_config.jsonc"
LOG_FILE = SCRIPT_DIR / "hermes_daemon.log"
VSCODE_CLASS = "Chrome_WidgetWin_1"
WAKE_LOCK_FILE = SCRIPT_DIR / "hermes_wake.lock"


def _acquire_wake_lock():
    """Atomically create the lock file. Return True if we got the lock,
    False if another wake instance already holds it.
    Uses open(path, 'x') — O_CREAT|O_EXCL — which is atomic on NTFS.
    """
    try:
        with open(WAKE_LOCK_FILE, 'x') as f:
            f.write(str(os.getpid()))
        return True
    except FileExistsError:
        # File already exists — check if the owning process is still alive
        try:
            other_pid = int(WAKE_LOCK_FILE.read_text().strip())
            try:
                os.kill(other_pid, 0)
                return False  # alive — another wake is running
            except (ProcessLookupError, PermissionError):
                pass  # process gone — stale lock
        except Exception:
            pass
        # Stale lock: remove and try once more (not a loop — if it fails again, yield)
        try:
            WAKE_LOCK_FILE.unlink()
            with open(WAKE_LOCK_FILE, 'x') as f:
                f.write(str(os.getpid()))
            return True
        except Exception:
            return False


def _release_wake_lock():
    try:
        WAKE_LOCK_FILE.unlink()
    except Exception:
        pass


def log(msg):
    line = msg if msg.startswith("[hermes") else f"[hermes:wake] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def load_config(path=DEFAULT_CONFIG):
    defaults = {
        "wake_msg": "Window reloaded. qhoami",
        "wake_timeout": 30,
    }
    def _parse(fpath):
        raw = Path(fpath).read_text(encoding="utf-8")
        stripped = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("/"))
        return json.loads(stripped)
    try:
        data = _parse(path)
        merged = {**defaults, **data}
        # Overlay with local config if present
        local_path = Path(path).parent / "hermes_config.local.jsonc"
        if local_path.exists():
            try:
                merged.update(_parse(local_path))
            except Exception as le:
                print(f"[hermes:wake] Local config error: {le} — ignored")
        return merged
    except Exception as e:
        print(f"[hermes:wake] Config error: {e} — using defaults")
        return defaults


def find_vscode_windows():
    """Return all VS Code windows. Use find_target_window() for session-anchored targeting."""
    handles = findwindows.find_windows(class_name=VSCODE_CLASS)
    result = []
    for h in handles:
        try:
            app = Application(backend="uia").connect(handle=h)
            win = app.window(handle=h)
            result.append({"handle": h, "title": win.window_text(), "window": win})
        except Exception:
            pass
    return result


def wait_for_chat_ready(win, timeout=30):
    """Block until chat Edit is visible+enabled, or timeout expires."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            for edit in win.descendants(control_type="Edit"):
                name = (edit.element_info.name or "").lower()
                cls = edit.element_info.class_name or ""
                if "chat input" in name or cls == "native-edit-context":
                    if edit.is_visible() and edit.is_enabled():
                        try:
                            edit.click_input()
                            return edit
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(0.5)
    return None


_SEND_BUTTON_NAMES = {"send", "send message", "submit"}


def find_agent_mode_in_window(win):
    """Return the active agent mode name for a VS Code chat window, or None.

    VS Code renders a 'Set Agent (Ctrl+.) - AGENTNAME' button in the chat
    input row (immediately around the text input area). This is the only
    stable, per-window identifier for which agent session is active.

    Confirmed via UIA probe 2026-02-20:
      Main window POLARIS1: [1076,75] 'Set Agent (Ctrl+.) - POLARIS1'
      Floating POLARIS3:    [1796,-973] 'Set Agent (Ctrl+.) - POLARIS3'

    The button is NOT in the status bar — it lives in the chat panel input
    row, which means it survives across topology changes (sidebar vs popout).
    """
    for btn in win.descendants(control_type="Button"):
        name = (btn.element_info.name or "").strip()
        if name.startswith("Set Agent") and " - " in name:
            return name.split(" - ", 1)[1].strip()
    return None


def _find_send_button(win):
    """Return the Send button control, or None."""
    for btn in win.descendants(control_type="Button"):
        name = (btn.element_info.name or "").lower()
        if name in _SEND_BUTTON_NAMES:
            return btn
    return None


def _read_input_content(win) -> str:
    """Return current text in the chat input Edit control, or empty string."""
    try:
        for edit in win.descendants(control_type="Edit"):
            name = (edit.element_info.name or "").lower()
            cls = edit.element_info.class_name or ""
            if "chat input" in name or cls == "native-edit-context":
                return edit.window_text() or ""
    except Exception:
        pass
    return ""


def _clear_input(win):
    """Select-all + Delete to clear the chat input box."""
    try:
        for edit in win.descendants(control_type="Edit"):
            name = (edit.element_info.name or "").lower()
            cls = edit.element_info.class_name or ""
            if "chat input" in name or cls == "native-edit-context":
                edit.click_input()
                time.sleep(0.05)
                win.type_keys("^a{DEL}")
                time.sleep(0.1)
                return
    except Exception:
        pass


def _clipboard_paste(win, message):
    """Write message to clipboard and paste into chat input via ^v.

    Replaces type_keys(per_char, pause=0.02) with Win32 clipboard write + ^v.
    Instantaneous: no per-character delay, no extended focus hold.
    Saves and restores prior clipboard content. See VGM9/hermes#13.
    """
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Focus the chat input edit control
    for edit in win.descendants(control_type="Edit"):
        name = (edit.element_info.name or "").lower()
        cls = edit.element_info.class_name or ""
        if "chat input" in name or cls == "native-edit-context":
            edit.click_input()
            time.sleep(0.05)
            break

    def _clip_read():
        text = ""
        if user32.OpenClipboard(0):
            if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                h = user32.GetClipboardData(CF_UNICODETEXT)
                if h:
                    ptr = kernel32.GlobalLock(h)
                    if ptr:
                        text = ctypes.wstring_at(ptr)
                        kernel32.GlobalUnlock(h)
            user32.CloseClipboard()
        return text

    def _clip_write(text):
        encoded = (text + "\0").encode("utf-16-le")
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h:
            return
        ptr = kernel32.GlobalLock(h)
        if ptr:
            ctypes.memmove(ptr, encoded, len(encoded))
            kernel32.GlobalUnlock(h)
        if user32.OpenClipboard(0):
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h)
            user32.CloseClipboard()

    saved = _clip_read()
    try:
        _clip_write(message)
        win.type_keys("^v")
        time.sleep(0.1)
    finally:
        if saved:
            _clip_write(saved)
        else:
            if user32.OpenClipboard(0):
                user32.EmptyClipboard()
                user32.CloseClipboard()


def send_wake_message(win, message, hermes_prefix="[hermes]"):
    """Type and submit a message into the chat input.

    Pre-send state contract (hermes#11):
      - Empty input          → proceed normally
      - Starts with prefix   → stuck prior hermes message, safe to clear
      - User content         → abort, return False (do NOT overwrite user work)

    Post-send verification: waits up to 2s for input to clear, logs if not.

    Returns True on successful send, False if aborted due to user content or error.
    """
    # Dismiss any open autocomplete/picker before reading or typing.
    try:
        win.type_keys("{ESC}")
    except Exception:
        pass
    time.sleep(0.1)

    # ── Pre-send state check (hermes#11) ─────────────────────────────────────
    existing = _read_input_content(win)
    if existing:
        if existing.startswith(hermes_prefix):
            log(f"[hermes:wake] clearing stuck hermes input: {existing[:60]!r}")
            _clear_input(win)
            time.sleep(0.1)
        else:
            log(f"[hermes:wake] aborting — user content in input: {existing[:60]!r}")
            return False

    _clipboard_paste(win, message)
    time.sleep(0.2)

    # Prefer clicking the Send button — avoids Enter being swallowed by
    # any picker that got re-triggered by the message text.
    btn = _find_send_button(win)
    if btn:
        btn.click_input()
    else:
        win.type_keys("{ENTER}")

    # ── Post-send verification ────────────────────────────────────────────────
    deadline = time.time() + 2.0
    while time.time() < deadline:
        time.sleep(0.2)
        if not _read_input_content(win):
            return True
    log("[hermes:wake] warning: input not empty after send — may not have submitted")
    return True  # best-effort; don't fail the wake for this


def send_failure_to_chat(win, reason):
    """Best-effort: send a failure notice into chat so the agent sees it."""
    try:
        chat = wait_for_chat_ready(win, timeout=5)
        if chat:
            send_wake_message(win, f"hermes:wake failed — {reason}")
    except Exception:
        pass


def _count_chat_text_elements(win, cap=60) -> int:
    """Count Text controls in the window as a proxy for conversation history.

    An active session with history has many Text elements (message content,
    timestamps, tool calls, etc.). An empty/fresh session has very few.
    Cap the scan to keep it fast.
    """
    try:
        count = 0
        for _ in win.descendants(control_type="Text"):
            count += 1
            if count >= cap:
                break
        return count
    except Exception:
        return 0


def _select_wake_window(windows, agent_mode=None, short_timeout=3):
    """Select the VS Code window that contains the expected agent session.

    Strategy (in priority order):
    1. If agent_mode is configured: find window whose 'Set Agent' button
       matches that mode exactly. This is the reliable per-window anchor.
       See find_agent_mode_in_window() and VGM9/hermes#5.
    2. Fallback (agent_mode not set): use Text-element count heuristic —
       the window with the most Text controls is the active session.
    3. Last resort: windows[0].
    """
    if len(windows) <= 1:
        return windows[0]["window"]

    if agent_mode:
        for entry in windows:
            win = entry["window"]
            mode = find_agent_mode_in_window(win)
            if mode and mode.lower() == agent_mode.lower():
                log(f"Agent mode match: '{mode}' in window '{entry['title'][:60]}'")
                return win
        log(f"No window with agent_mode='{agent_mode}' found — falling back to text-count heuristic")

    # Fallback: text element count heuristic (original behavior for unconfigured state)
    best_win = None
    best_score = -1
    for entry in windows:
        win = entry["window"]
        chat = wait_for_chat_ready(win, timeout=short_timeout)
        if not chat:
            continue
        score = _count_chat_text_elements(win)
        log(f"Window '{entry['title'][:60]}' chat-text score: {score}")
        if score > best_score:
            best_score = score
            best_win = win

    if best_win is not None:
        return best_win
    log("_select_wake_window: no window ready within short timeout — using windows[0]")
    return windows[0]["window"]


def main():
    parser = argparse.ArgumentParser(description="Hermes one-shot post-reload wake")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help=f"Path to config JSONC (default: {DEFAULT_CONFIG})")
    parser.add_argument("--message", default=None,
                        help="Override wake message from config (used by autopulse)")
    parser.add_argument("--no-brief", action="store_true",
                        help="Skip appending wake.py --brief status line")
    args = parser.parse_args()

    if not _acquire_wake_lock():
        log("Another wake instance is already running — exiting")
        sys.exit(0)

    try:
        _wake(args)
    finally:
        _release_wake_lock()


def _wake(args):
    config = load_config(args.config)
    timeout = int(config.get("wake_timeout", 30))
    message = args.message if args.message else config["wake_msg"]

    # Append wake.py --brief status line if available (skip if --no-brief or --message override)
    if not args.no_brief and not args.message and WAKE_PY.exists():
        try:
            r = subprocess.run(
                [sys.executable, str(WAKE_PY), "--brief"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=45
            )
            brief = (r.stdout or r.stderr or "").strip()
            if brief:
                message = f"{message}\n{brief}"
        except Exception as _wake_err:
            log(f"wake.py --brief failed: {_wake_err}")

    # Session-anchored targeting (VGM9/hermes#10):
    # session_jsonl + agent_mode are the canonical target anchors.
    # Both must be present in hermes_config.local.jsonc (written by install-tasks.js).
    session_jsonl = config.get("autopulse", {}).get("session_jsonl", "")
    agent_mode = config.get("agent_mode", "").strip()

    if not (session_jsonl and agent_mode):
        log("session_jsonl or agent_mode not configured in hermes_config.local.jsonc — giving up")
        sys.exit(1)
    from core.ui_automation.window_detection import find_target_window
    win = find_target_window(session_jsonl, agent_mode)
    if win is None:
        log(f"No unique window found (agent_mode={agent_mode!r}) — giving up")
        sys.exit(1)
    log(f"Target: agent_mode='{agent_mode}' window='{win.window_text()[:60]}'")
    log(f"Waiting for chat ready (timeout={timeout}s)...")

    try:
        chat = wait_for_chat_ready(win, timeout=timeout)
        if not chat:
            reason = "chat never ready (timeout exceeded)"
            log(reason)
            send_failure_to_chat(win, reason)
            sys.exit(1)

        log(f"Sending: '{message}'")

        # Abort if the box is non-empty — session is active, not post-reload idle.
        # Typing into a non-empty box would corrupt the user's draft (hermes#4).
        try:
            current = chat.get_value() or chat.window_text() or ''
            if current.strip():
                log("Chat box non-empty — session active, skipping wake")
                sys.exit(0)
        except Exception:
            pass  # can't read value — proceed anyway

        ok = send_wake_message(win, message)
        if ok is False:
            log("Pulse suppressed — user content in input box. Not a failure.")
            sys.exit(0)
        log("Done")
    except Exception as e:
        reason = str(e)
        log(f"Exception: {reason}")
        send_failure_to_chat(win, reason)
        sys.exit(1)


if __name__ == "__main__":
    main()
