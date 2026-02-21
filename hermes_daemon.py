#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes Daemon
=============
Idempotent always-on background process. Monitors VS Code windows and acts
on configured triggers without human intervention.

Triggers (all toggled via hermes_config.json, hot-reloaded each poll cycle):

  update_button      — Detect and click VS Code "Update is ready" status bar button
  reload_dialog      — Detect and click "A chat request is in progress" cancel dialog
  chat_timeout_restart — Click retry when Copilot reports "Chat took too long to get ready"

Wake-on-reload is handled by hermes_wake.py, invoked by the VS Code
folderOpen task. This daemon no longer manages wake state.

Idempotency: writes a PID file on start. Subsequent launches check the PID file;
if the process is alive they exit 0 immediately. The folderOpen VS Code task calls
this script — safe to call every workspace open.

Usage:
    python3 hermes_daemon.py                    # start (or no-op if already running)
    python3 hermes_daemon.py --ensure-running   # alias, same behavior
    python3 hermes_daemon.py --stop             # kill running daemon
    python3 hermes_daemon.py --status           # print running/stopped + PID
    python3 hermes_daemon.py --config /path/to/hermes_config.json

Author: POLARIS1 (0.0.19), 2026-02-19
"""

import sys
import os
import time
import json
import copy
import signal
import argparse
import subprocess
from pathlib import Path

try:
    import pywinauto
    from pywinauto import Application, findwindows
    from pywinauto.keyboard import send_keys
except ImportError:
    print("ERROR: pywinauto not installed. Run: pip install pywinauto")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG = SCRIPT_DIR / "hermes_config.jsonc"
PID_FILE = SCRIPT_DIR / "hermes_daemon.pid"
VSCODE_CLASS = "Chrome_WidgetWin_1"
DETACHED_PROCESS = 0x00000008   # Windows: detach child from parent console
CREATE_NO_WINDOW = 0x08000000   # Windows: suppress console window on subprocess spawn

_UPDATE_BUTTON_FRAGMENTS = [
    "update available",
    "restart to update",
    "click to restart",
    "update is ready",
    "restart required",
]


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def safe_print(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def load_config(path):
    """Load config JSON, return dict. Returns defaults on any error.
    If hermes_config.local.jsonc exists alongside path, its values overlay
    the base config — used for per-workspace overrides.
    """
    defaults = {
        "triggers": {"update_button": True, "reload_dialog": True, "wake_on_reload": True},
        "wake_msg": "Window reloaded. #qhoami",
        "poll_interval": 0.8,
        "wake_debounce_seconds": 10,
    }
    def _parse(fpath):
        raw = Path(fpath).read_text(encoding="utf-8")
        stripped = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("/"))
        return json.loads(stripped)
    try:
        data = _parse(path)
        merged = {**defaults, **data}
        merged["triggers"] = {**defaults["triggers"], **data.get("triggers", {})}
        # Overlay with local config if present
        local_path = Path(path).parent / "hermes_config.local.jsonc"
        if local_path.exists():
            try:
                local = _parse(local_path)
                merged.update(local)
            except Exception as le:
                safe_print(f"[hermes] Local config error ({local_path}): {le} — ignored")
        return merged
    except Exception as e:
        safe_print(f"[hermes] Config load error ({path}): {e} — using defaults")
        return defaults


# ─────────────────────────────────────────────────────────────────────────────
# PID management
# ─────────────────────────────────────────────────────────────────────────────

def read_pid():
    """Return int PID from PID file, or None."""
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def is_process_alive(pid):
    """Return True if a process with the given PID is running."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except Exception:
        return False


def is_daemon_running():
    """Return (alive: bool, pid: int|None)."""
    pid = read_pid()
    if pid is None:
        return False, None
    return is_process_alive(pid), pid


def write_pid():
    PID_FILE.write_text(str(os.getpid()))


def clear_pid():
    try:
        PID_FILE.unlink()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# VS Code window utilities
# ─────────────────────────────────────────────────────────────────────────────

from core.ui_automation.window_detection import find_vscode_windows as _core_find_windows
from core.ui_automation.window_detection import find_agent_mode_in_window, find_target_window


def find_vscode_windows():
    """Return all VS Code windows as dicts with handle/title/window keys.
    Use find_target_window(session_jsonl, agent_mode) for session-anchored targeting.
    """
    result = []
    for w in _core_find_windows():
        try:
            app = Application(backend="uia").connect(handle=w.handle)
            win_obj = app.window(handle=w.handle)
            result.append({"handle": w.handle, "title": w.title, "window": win_obj})
        except Exception:
            result.append({"handle": w.handle, "title": w.title, "window": None})
    return result


def handle_is_alive(handle):
    try:
        app = Application(backend="uia").connect(handle=handle)
        app.window(handle=handle).window_text()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Trigger: update button
# ─────────────────────────────────────────────────────────────────────────────

def scan_for_update_button(windows):
    """Return first matching update/restart status bar element, or None."""
    for entry in windows:
        win = entry["window"]
        if win is None:
            continue
        try:
            for ctrl_type in ("Button", "MenuItem", "Custom", "Text"):
                for elem in win.descendants(control_type=ctrl_type):
                    try:
                        name = (elem.element_info.name or "").lower()
                        if any(frag in name for frag in _UPDATE_BUTTON_FRAGMENTS):
                            return elem
                    except Exception:
                        pass
        except Exception:
            pass
    return None


def trigger_update_button(windows):
    """Click update button if found. Returns True if clicked."""
    btn = scan_for_update_button(windows)
    if btn:
        try:
            name = btn.element_info.name
            btn.click_input()
            safe_print(f"[hermes] Clicked update button: '{name}'")
            return True
        except Exception as e:
            safe_print(f"[hermes] Update button click failed: {e}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Trigger: reload dialog
# ─────────────────────────────────────────────────────────────────────────────

def trigger_reload_dialog(windows):
    """Find and click Yes/Reload on the 'chat request in progress' dialog. Returns True if clicked."""
    for entry in windows:
        win = entry["window"]
        if win is None:
            continue
        try:
            descendants = win.descendants()
            texts = [d.window_text().lower() for d in descendants if d.window_text()]
            if any(
                "chat request is in progress" in t or
                "a chat session is in progress" in t
                for t in texts
            ):
                for btn in win.descendants(control_type="Button"):
                    if btn.window_text().lower() in ("yes", "reload", "ok", "restart"):
                        btn.click_input()
                        safe_print(f"[hermes] Clicked reload dialog: '{btn.window_text()}'")
                        return True
        except Exception:
            pass
    return False



# ─────────────────────────────────────────────────────────────────────────────
# Poll loop state and main loop
# ─────────────────────────────────────────────────────────────────────────────

class DaemonState:
    def __init__(self):
        self.last_update_click_time = 0.0  # debounce: don't click update button repeatedly
        # autopulse: per-target last-pulse timestamps keyed by agent_mode (hermes#18)
        # Legacy fields kept for backward compat with any external code that reads them.
        self.pulse_times: dict = {}        # {agent_mode: last_fire_timestamp}
        self.last_pulse_time = 0.0         # legacy alias (single-target compat)
        self.pulse_paused = False          # legacy alias (single-target compat)


# ─────────────────────────────────────────────────────────────────────────────
# Autopulse: user idle detection + periodic keep-alive
# ─────────────────────────────────────────────────────────────────────────────

def _agent_is_busy(session_jsonl_path: str, hermes_prefix: str = "[hermes]",
                   age_ceiling_seconds: float = 300) -> tuple:
    """Return (is_busy, reason_str) — True if agent has unanswered non-hermes request.

    Unmatched-request heuristic: the most recent genuine human message has no
    response content AND was sent within age_ceiling_seconds → agent is processing it.

    Age ceiling prevents permanently suppressing if a response goes missing or the
    JSONL partial-write races with a read. See VGM9/hermes#14.
    """
    try:
        path = Path(session_jsonl_path)
        if not path.exists():
            return False, "no jsonl"
        lines = path.read_bytes().decode("utf-8", "replace").splitlines()
        if not lines:
            return False, "empty jsonl"

        import copy
        snap = json.loads(lines[0])
        reqs = {i: copy.deepcopy(r) for i, r in enumerate(snap.get("v", {}).get("requests", [])) if r}
        nxt = len(reqs)
        for raw in lines[1:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            kind, keys, val = obj.get("kind"), obj.get("k", []), obj.get("v")
            if kind == 2 and keys == ["requests"] and isinstance(val, list):
                for r in val:
                    if isinstance(r, dict):
                        reqs[nxt] = r
                        nxt += 1
                continue
            if kind not in (1, 2) or len(keys) < 3 or keys[0] != "requests":
                continue
            ri, field = keys[1], keys[2]
            if ri not in reqs:
                reqs[ri] = {}
            if kind == 1:
                reqs[ri][field] = val
            elif kind == 2 and field == "response" and isinstance(val, list):
                reqs[ri].setdefault("response", []).extend(val)

        # Walk from newest to oldest, find most recent genuine human message
        for i in sorted(reqs.keys(), reverse=True):
            req = reqs[i]
            msg_text = req.get("message", "")
            if not msg_text or str(msg_text).startswith(hermes_prefix):
                continue
            if req.get("response"):
                return False, "response present"  # answered → not busy
            ts_ms = req.get("timestamp", 0)
            if ts_ms:
                age = time.time() - ts_ms / 1000.0
                if age < age_ceiling_seconds:
                    return True, f"unanswered {age:.0f}s old"
                return False, f"unanswered but stale ({age:.0f}s > ceiling)"
            return False, "no timestamp"
        return False, "no genuine messages"
    except Exception as e:
        return False, f"parse error: {e}"


def _get_last_human_message_time(session_jsonl_path: str, hermes_prefix: str = "[hermes]"):
    """Return (timestamp_seconds, message_text) of the most recent genuine human message.

    Parses the JSONL mutation log format used by VS Code Insiders (v1.109+).
    A "genuine human message" is a user turn whose message text does NOT start
    with the hermes_prefix — meaning it was typed by the human, not injected by hermes.

    Returns (0.0, "") if no matching message is found or on any parse error.
    """
    try:
        path = Path(session_jsonl_path)
        if not path.exists():
            return 0.0, ""

        lines = path.read_bytes().decode("utf-8", "replace").splitlines()
        if not lines:
            return 0.0, ""

        # Reconstruct requests from JSONL mutation log
        import copy
        snap = json.loads(lines[0])
        reqs = {i: copy.deepcopy(r) for i, r in enumerate(snap.get("v", {}).get("requests", [])) if r}
        nxt = len(reqs)
        for raw in lines[1:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            kind, keys, val = obj.get("kind"), obj.get("k", []), obj.get("v")
            if kind == 2 and keys == ["requests"] and isinstance(val, list):
                for r in val:
                    if isinstance(r, dict):
                        reqs[nxt] = r
                        nxt += 1
                continue
            if kind not in (1, 2) or len(keys) < 3 or keys[0] != "requests":
                continue
            ri, field = keys[1], keys[2]
            if ri not in reqs:
                reqs[ri] = {}
            if kind == 1:
                reqs[ri][field] = val
            elif kind == 2 and field == "response" and isinstance(val, list):
                reqs[ri].setdefault("response", []).extend(val)

        # Walk requests from most recent to oldest
        for i in sorted(reqs.keys(), reverse=True):
            req = reqs[i]
            msg_text = req.get("message", "")
            if not msg_text:
                continue
            # Skip hermes-injected messages
            if str(msg_text).startswith(hermes_prefix):
                continue
            # This is a genuine human message — extract timestamp
            ts_ms = req.get("timestamp", 0)
            if ts_ms:
                return ts_ms / 1000.0, str(msg_text)
            # Fallback: use file mtime if no timestamp in record
            return path.stat().st_mtime, str(msg_text)

        return 0.0, ""
    except Exception as e:
        safe_print(f"[hermes] idle-detect error: {e}")
        return 0.0, ""


def _fire_pulse(session_jsonl: str, agent_mode: str, pulse_message: str) -> bool:
    """Spawn send_message.py to deliver one pulse to a specific session+mode.

    Fixes hermes#17: passes --session-jsonl and --agent-mode explicitly so
    send_message.py can target the correct window rather than using placeholders.

    Returns:
        True  — message delivered (exit 0)
        None  — suppressed: user content in input (exit 2), update timer to avoid pulse storm
        False — real failure (exit 1, window not found, crash), do NOT update timer
    """
    wake_script = SCRIPT_DIR / "send_message.py"
    try:
        result = subprocess.run(
            [sys.executable, str(wake_script), pulse_message,
             "--session-jsonl", session_jsonl,
             "--agent-mode", agent_mode],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return True
        if result.returncode == 2:
            return None  # suppressed
        return False
    except Exception:
        return False


def trigger_autopulse(state, config):
    """Send periodic pulse messages to keep agents alive when user is idle.

    Supports multi-target via autopulse.targets list (hermes#18).
    Each target has: session_jsonl, agent_mode, message, interval_seconds.
    If no targets list, falls back to single-target legacy config.

    Does its own window detection per target via send_message.py.
    Does not use pywinauto window walking — safe to call before find_target_window.

    User idle = most recent genuine human message is older than
    user_idle_threshold_seconds. When user returns (fresh human message),
    pulses pause until next idle window.

    Uses VS Code's steering capability (2026-02-20): if the agent is
    mid-response, the message queues instead of interrupting.
    """
    autopulse = config.get("autopulse", {})
    if not autopulse.get("enabled", False):
        return False

    hermes_prefix = autopulse.get("hermes_prefix", "[hermes]")
    idle_threshold = float(autopulse.get("user_idle_threshold_seconds", 120))
    now = time.time()

    # Build target list: multi-target (targets list) or single-target (legacy fields)
    raw_targets = autopulse.get("targets")
    if raw_targets:
        targets = raw_targets  # list of {session_jsonl, agent_mode, message, interval_seconds}
    else:
        # Legacy single-target
        session_jsonl = autopulse.get("session_jsonl", "")
        agent_mode = config.get("agent_mode", "").strip()
        if not session_jsonl or not agent_mode:
            return False
        targets = [{
            "session_jsonl": session_jsonl,
            "agent_mode": agent_mode,
            "message": autopulse.get("message", "[hermes] pulse — user away. status: alive?"),
            "interval_seconds": autopulse.get("interval_seconds", 300),
        }]

    fired_any = False
    for target in targets:
        t_session_jsonl = target.get("session_jsonl", "")
        t_agent_mode = target.get("agent_mode", "")
        t_message = target.get("message", "[hermes] pulse — user away. status: alive?")
        t_interval = float(target.get("interval_seconds", 300))
        t_key = t_agent_mode  # use agent_mode as state key

        if not t_session_jsonl or not t_agent_mode:
            continue

        # Per-target idle check
        user_is_idle = True
        if t_session_jsonl:
            last_human_ts, _ = _get_last_human_message_time(t_session_jsonl, hermes_prefix)
            user_age = now - last_human_ts if last_human_ts else float("inf")
            user_is_idle = user_age > idle_threshold

        if not user_is_idle:
            state.pulse_times[t_key] = now  # reset timer when user active
            continue

        # Per-target interval check
        last_pulse = state.pulse_times.get(t_key, 0)
        since_last = now - last_pulse
        if since_last < t_interval:
            continue

        # Fire
        safe_print(f"[hermes] autopulse → {t_agent_mode} (idle {user_age:.0f}s, interval {t_interval:.0f}s)")
        result = _fire_pulse(t_session_jsonl, t_agent_mode, t_message)
        if result is True:
            state.pulse_times[t_key] = now
            safe_print(f"[hermes] autopulse ✓ {t_agent_mode}")
            fired_any = True
        elif result is None:
            state.pulse_times[t_key] = now  # update timer: don't pulse-storm
            safe_print(f"[hermes] autopulse ⚠ {t_agent_mode} — suppressed (user content in input)")
        else:
            safe_print(f"[hermes] autopulse ✗ {t_agent_mode} — send_message.py failed")

    return fired_any


def poll_once(state, config, config_path):
    """One poll cycle. Mutates state. Hot-reloads config."""
    config = load_config(config_path)
    triggers = config["triggers"]
    agent_mode = config.get("agent_mode", "").strip()
    session_jsonl = config.get("autopulse", {}).get("session_jsonl", "")

    # ── Autopulse is independent of UI-trigger window detection ─────────────
    # Uses send_message.py per target — does its own window detection.
    # Fires here so multi-target config (no top-level session_jsonl) still works.
    if config.get("autopulse", {}).get("enabled"):
        trigger_autopulse(state, config)

    # ── Session-anchored window selection for UI triggers (VGM9/hermes#10) ──
    # session_jsonl + agent_mode needed for update-button / reload-dialog only.
    # If missing (multi-target-only config), skip UI triggers silently.
    if not (session_jsonl and agent_mode):
        return config
    target_win = find_target_window(session_jsonl, agent_mode)
    if target_win is None:
        return config  # no unique target found — skip UI triggers
    windows = [{"window": target_win, "handle": target_win.handle,
                "title": target_win.window_text()}]

    # ── Foreground window exclusion ──────────────────────────────────────────
    # Never walk descendants of the window the user is actively using.
    try:
        import win32gui
        focused_handle = win32gui.GetForegroundWindow()
        windows = [w for w in windows if w["handle"] != focused_handle]
    except Exception:
        pass  # win32gui unavailable — agent_mode filter is sufficient

    if not windows:
        return config  # active window is target — skip UI triggers

    # ── Update button ──────────────────────────────────────────────────────
    if triggers.get("update_button"):
        update_debounce = config.get("update_click_debounce_seconds", 30)
        if time.time() - state.last_update_click_time > update_debounce:
            if trigger_update_button(windows):
                state.last_update_click_time = time.time()

    # ── Reload dialog ────────────────────────────────────────────────────────
    if triggers.get("reload_dialog"):
        trigger_reload_dialog(windows)

    return config  # return hot-reloaded config for next interval


def run_daemon(config_path):
    """Main daemon loop. Runs until SIGTERM/SIGINT."""
    safe_print(f"[hermes] Daemon started (PID {os.getpid()})")
    safe_print(f"[hermes] Config: {config_path}")

    config = load_config(config_path)
    state = DaemonState()

    def _shutdown(sig, frame):
        safe_print("[hermes] Shutting down")
        clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        try:
            config = poll_once(state, config, config_path)
        except Exception as e:
            safe_print(f"[hermes] Poll error: {e}")
        time.sleep(config.get("poll_interval", 0.8))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hermes idempotent daemon")
    parser.add_argument("--ensure-running", action="store_true",
                        help="Start if not running, exit 0 if already running (default behavior)")
    parser.add_argument("--detach", action="store_true",
                        help="Self-daemonize via DETACHED_PROCESS spawn (works in cmd.exe / any shell)")
    parser.add_argument("--stop", action="store_true", help="Stop the running daemon")
    parser.add_argument("--status", action="store_true", help="Print daemon status")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help=f"Path to config JSON (default: {DEFAULT_CONFIG})")
    args = parser.parse_args()

    alive, pid = is_daemon_running()

    if args.status:
        if alive:
            safe_print(f"running (PID {pid})")
        else:
            safe_print("stopped")
        return

    if args.stop:
        if alive:
            os.kill(pid, signal.SIGTERM)
            safe_print(f"[hermes] Sent SIGTERM to PID {pid}")
            clear_pid()
        else:
            safe_print("[hermes] Not running")
        return

    # Default / --ensure-running: if already alive, exit idempotently.
    # Backgrounding is the caller's job (VS Code task, run_in_terminal isBackground=true).
    if alive:
        safe_print(f"[hermes] Already running (PID {pid}) — exiting")
        return

    if getattr(args, "detach", False):
        # Spawn self without --detach as a detached background process.
        # Works from any shell (cmd.exe, powershell, bash) — no nohup/& needed.
        log_path = SCRIPT_DIR / "hermes_daemon.log"
        with open(log_path, "a", encoding="utf-8") as log_f:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--config", args.config],
                creationflags=DETACHED_PROCESS,
                close_fds=True,
                stdout=log_f,
                stderr=log_f,
                stdin=subprocess.DEVNULL,
            )
        safe_print(f"[hermes] Detached daemon PID {child.pid} (child will self-register)")
        return

    write_pid()
    try:
        run_daemon(args.config)
    finally:
        clear_pid()


if __name__ == "__main__":
    main()
