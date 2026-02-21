# hermes — Architecture (live code map)

**Last updated:** 2026-02-20 by POLARIS3/0.0.40  
**Status:** chat/ module split complete. All hermes#10-16 closed. Two open: hermes#5 (UIA probe), hermes#7 (per-target wake).

---

## Entry Points (what gets executed)

| File | Lines | How invoked | Purpose |
|------|-------|-------------|---------|
| `hermes_daemon.py` | 578 | `npm run daemon` | Main poll loop — triggers + autopulse |
| `hermes_wake.py` | shim | legacy compat only | Forwards to `wake.py` |
| `wake.py` | ~60 | `npm run wake` / VS Code `folderOpen` task | Post-reload wake: lock + wait-ready + send |
| `send_message.py` | ~30 | spawned by daemon `trigger_autopulse` | Active-session message delivery (no lock, no readiness wait) |
| `reload_and_wake.py` | 443 | `npm run reload` / `npm run reload-wake` | VS Code update detection + reload orchestration |
| `hermes_config.py` | 138 | imported by all above | Config loader with local override merge |
| `vscode_ground_truth.py` | 434 | imported by daemon + wake | Constants: class names, button names, paths |
| `install-tasks.js` | — | `npm run install-tasks` | Writes `hermes_config.local.jsonc` with session_jsonl + agent_mode |

---

## Core Library (`core/`)

| File | Lines | Exports used |
|------|-------|-------------|
| `core/ui_automation/window_detection.py` | 204 | `find_vscode_windows()`, `find_agent_mode_in_window()`, `find_target_window()` |
| `core/ui_automation/element_detection.py` | 224 | button/edit element scanning |
| `core/ui_automation/element_interaction.py` | 106 | click helpers |
| `core/data_models/approval_request.py` | 172 | `ApprovalRequest` dataclass |
| `core/parsers/request_text_parser.py` | 288 | request text extraction |

---

## Chat Module (`chat/`)

| File | Exports | Purpose |
|------|---------|---------|
| `chat/lock.py` | `WakeLock` | Context manager: acquire/release wake lock file (atomic, stale-lock detection) |
| `chat/input.py` | `wait_for_chat_ready`, `read_content`, `clear_input`, `clipboard_paste`, `find_send_button` | Chat input primitives |
| `chat/send.py` | `send_message(win, message) -> bool`, `send_failure_to_chat` | Message delivery: ESC → pre-send check → clipboard paste → send button or Enter |
| `chat/__init__.py` | `send_message`, `wait_for_chat_ready` | Public API |

**Design principle:** `send_message` is pure delivery — no lock, no readiness wait, no wake semantics. Callers (`wake.py`, `send_message.py`) compose it with whatever ceremony the use case requires.

---

## Active Trigger Paths in `hermes_daemon.py`

```
poll_once(state, config, config_path)
  └─ find_target_window(session_jsonl, agent_mode)   ← session-anchored (hermes#10)
       ↓ exactly 1 match
  └─ trigger_update_button(windows)                  ✅ enabled by default
  └─ trigger_reload_dialog(windows)                  ✅ enabled by default
  └─ trigger_autopulse(state, config, windows)       ✅ when flag present OR user idle
```

**Removed (archived):**
- `trigger_chat_timeout_restart()` — disabled in config, dead code → removed 2026-02-20
- Legacy `window_pattern` + agent_mode filter fallback → removed 2026-02-20

---

## Window Targeting Algorithm

**Session-anchored (the only path, post-cleanup):**

```
config["autopulse"]["session_jsonl"]
  → extract workspace hash (path segment in workspaceStorage/{hash}/)
  → read workspaceStorage/{hash}/workspace.json
  → "folder" or "workspace" URI → full filesystem path
  → Path(full_path).stem → workspace name
  → filter Chrome_WidgetWin_1 windows by title containing name
  → verify UIA "Set Agent (Ctrl+.) - {agent_mode}" button present
  → exactly 1 match → return | 0 or 2+ → log + return None (skip cycle)
```

`find_target_window(session_jsonl, expected_agent_mode)` is in `core/ui_automation/window_detection.py`.

**What was removed:** `window_pattern` — a hand-maintained string that collides when the same workspace name appears in different parent paths. See `HERMES_WINDOW_DETECTION.instructions.md` and VGM9/hermes#10.

---

## Message Send Path

**Post-reload wake** (`wake.py`):
```
_wake(args)
  └─ WakeLock.__enter__()                — serialize concurrent wakes
  └─ load_config()
  └─ find_target_window(session_jsonl, agent_mode)
  └─ wait_for_chat_ready(win, timeout)   — chat.input
  └─ chat.send_message(win, message)     — chat.send
```

**Daemon autopulse** (`send_message.py`):
```
main()
  └─ find_target_window(session_jsonl, agent_mode)
  └─ chat.send_message(win, message)     — no lock, no readiness wait
```

---

## Autopulse (Heartbeat Auto-Pilot)

Fires when user_is_idle AND interval elapsed:

```
trigger_autopulse(state, config, windows)
  ├─ flag_path = hermes_user_away.flag
  ├─ flag present → user_is_idle = True (explicit departure)
  ├─ flag absent + session_jsonl → check JSONL last human message timestamp
  └─ elapsed >= interval_seconds → subprocess.run(send_message.py, message)
```

**Config keys (in `hermes_config.local.jsonc`):**
```jsonc
{
  "agent_mode": "POLARIS3",
  "autopulse": {
    "enabled": true,
    "interval_seconds": 180,
    "user_idle_threshold_seconds": 120,
    "message": "heartbeat. keep working.",
    "session_jsonl": ".../{workspace_hash}/chatSessions/{session_id}.jsonl"
  }
}
```

**Heartbeat recognition rule (POLARIS3):**  
`"heartbeat. keep working."` → auto-pilot mode: continue work, don't yield.  
Any other message → user has returned: yield and wait.

---

## Subprocess Spawn (daemon → send_message)

`hermes_daemon.py` calls `send_message.py` via:
```python
subprocess.run([sys.executable, send_script, "--config", config_path, "--message", msg], ...)
```

---

## Config Files

| File | Committed | Purpose |
|------|-----------|---------|
| `hermes_config.jsonc` | ✅ | Base config (shared defaults) |
| `hermes_config.local.jsonc` | ❌ | Per-workspace overrides: agent_mode, session_jsonl |
| `hermes_user_away.flag` | ❌ | Presence = user departed, send heartbeats |

`hermes_config.local.jsonc` is written by `install-tasks.js` at deploy time. **Do not commit it.** It contains workspace-specific session IDs.

---

## What Lives in `_archive/`

35 files moved here 2026-02-20. All were either:
- Explicitly marked `DEPRECATED` or `DO NOT USE` 
- Test scripts for one-time investigations
- Superseded by the `core/` module split

These files are not imported by any live code. They exist for archaeology only.

---

## HERMES_QUEUE: Multi-Agent Handoff Protocol

When two agent sessions (e.g., POLARIS1 and POLARIS4) run in separate VS Code
windows, they cannot inject messages into each other's chat box directly.
The HERMES_QUEUE provides a file-based coordination channel.

**Design doc:** `___/AS/HERMES_QUEUE/README.md` (VGM9 supernal space)

### Queue directory

```
/c/www/VGM9/___/AS/HERMES_QUEUE/
```

### Message format

Create a JSON file named `{timestamp}-from-{sender}-to-{target}.json`:

```json
{
  "from": "POLARIS1",
  "to": "POLARIS4",
  "message": "[hermes] POLARIS1: your message here",
  "created": "2026-02-21T00:00:00Z",
  "expires_after": 120
}
```

### Delivery lifecycle

1. `poll_once()` checks the queue directory each cycle
2. Files whose `to` matches `agent_mode` are picked up
3. `send_wake_message()` delivers into the target window's chat box
4. File is renamed to `{name}.delivered` — prevents duplicate delivery
5. Files older than `expires_after` seconds become `{name}.expired`

### Current state

**Not yet implemented in `hermes_daemon.py`.** Queue directory and design exist.
VGM9/hermes enhancement: tracked as a future feature.

### Why `runSubagent` is preferred for reasoning

```python
# Virtual coordination — no physical window access needed
runSubagent("POLARIS4", "What is your current patch count?")
```

Use HERMES_QUEUE only when the target agent must run tools from their own
window (e.g., needs access to their session's tool scope).

---

## Open Issues

No open issues as of 2026-02-21. Tracker: https://github.com/VGM9/hermes/issues

Previously closed:
- hermes#5 — UIA agent-mode label probe → implemented in `window_detection.py`
- hermes#7 — Per-target wake → implemented via `autopulse.targets` config
