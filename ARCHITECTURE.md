# hermes — Architecture (live code map)

**Last updated:** 2026-02-20 by POLARIS3/0.0.38  
**Status:** Post-cleanup. 35 dead files archived. window_pattern antipattern removed. Clipboard paste implemented.

---

## Entry Points (what gets executed)

| File | Lines | How invoked | Purpose |
|------|-------|-------------|---------|
| `hermes_daemon.py` | 578 | `npm run daemon` | Main poll loop — triggers + autopulse |
| `hermes_wake.py` | 490 | `npm run wake` / VS Code `folderOpen` task | One-shot: send wake message to chat |
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

## Message Send Path in `hermes_wake.py`

```
_wake(args)
  └─ load_config()
  └─ find_target_window(session_jsonl, agent_mode)
  └─ wait_for_chat_ready(win, timeout)
  └─ send_wake_message(win, message)
       ├─ win.type_keys("{ESC}")          — dismiss autocomplete
       ├─ _read_input_content(win)        — pre-send state check (hermes#11)
       │    ├─ [hermes] prefix → _clear_input()
       │    └─ user content → abort, return False
       ├─ _clipboard_paste(win, message)  — Win32 clipboard + ^v (hermes#13)
       │    saves/restores prior clipboard; instantaneous
       ├─ _find_send_button(win)          — click Send btn or fall back to {ENTER}
       └─ poll input cleared (2s timeout)
```

**What was removed:** `type_keys(escaped, with_spaces=True, pause=0.02)` — per-character delays stole OS focus for the full message duration. Replaced with `ctypes` Win32 clipboard write + `^v`.

---

## Autopulse (Heartbeat Auto-Pilot)

Fires when user_is_idle AND interval elapsed:

```
trigger_autopulse(state, config, windows)
  ├─ flag_path = hermes_user_away.flag
  ├─ flag present → user_is_idle = True (explicit departure)
  ├─ flag absent + session_jsonl → check JSONL last human message timestamp
  └─ elapsed >= interval_seconds → subprocess.run(hermes_wake.py, message)
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

## Subprocess Spawn (daemon → wake)

`hermes_daemon.py` calls `hermes_wake.py` via:
```python
subprocess.run([sys.executable, wake_script, "--config", config_path, "--message", msg], ...)
```

**Known issue:** No `creationflags=0x08000000` → spawns visible cmd window. See VGM9/hermes#12 (filed, not yet fixed).

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

## Open Issues (filed, not yet implemented)

| Issue | Title | Severity |
|-------|-------|----------|
| hermes#12 | cmd window visible on daemon subprocess spawn | UX |
| hermes#14 | busy-agent detection: suppress heartbeat if JSONL shows unmatched request | Logic |
| hermes#10 | `reload_and_wake.py` still uses `window_pattern` for update cycle | Tech debt |
| hermes#5 | UIA agent-mode label probe (POLARIS1 wall) | Capability |
| hermes#7 | Per-target wake implementation (blocked on #5) | Feature |
