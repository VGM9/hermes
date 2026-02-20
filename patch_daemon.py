#!/usr/bin/env python3
"""
Patch hermes_daemon.py:
1. Replace timer-based reload wake with event-driven woken_handles logic
2. Add update button debounce
Uses anchor-based section replacement — robust against exact separator lengths.
"""
import sys

TARGET = "c:/www/VGM9/_/AS/0.0.Q/_/software/hermes/hermes_daemon.py"

with open(TARGET, "rb") as f:
    content = f.read().decode("utf-8")

# ── Patch 1: DaemonState ─────────────────────────────────────────────────
# Find the class body and replace reload_in_progress + last_wake_time
state_old = (
    "        self.reload_in_progress = False   # True once we see a handle disappear\r\n"
    "        self.last_wake_time = 0.0\r\n"
    "        self.last_update_click_time = 0.0  # debounce: don't click update button repeatedly"
)
state_new = (
    "        self.reload_pending = False       # a reload was detected (handles disappeared)\r\n"
    "        self.woken_handles = set()        # handles already woken — never re-wake the same handle\r\n"
    "        self.last_update_click_time = 0.0  # debounce: don't click update button repeatedly"
)
if state_old not in content:
    print("ERROR: DaemonState fields not found")
    sys.exit(1)
content = content.replace(state_old, state_new, 1)
print("OK: DaemonState patched")

# ── Patch 2: Wake + Update sections ──────────────────────────────────────
WAKE_ANCHOR  = "    # \u2500\u2500 Wake-on-reload detection"
RELOAD_ANCHOR = "    # \u2500\u2500 Reload dialog"

wake_i   = content.find(WAKE_ANCHOR)
reload_i = content.find(RELOAD_ANCHOR)
if wake_i == -1 or reload_i == -1:
    print(f"ERROR: anchors not found wake={wake_i} reload={reload_i}")
    sys.exit(1)

new_wake_update = (
    "    # \u2500\u2500 Wake-on-reload detection \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\r\n"
    "    # Event-driven: fires ONCE per new handle, only after a reload_pending event.\r\n"
    "    # woken_handles guarantees no re-fire on the same handle.\r\n"
    "    if triggers.get(\"wake_on_reload\"):\r\n"
    "        lost_handles = state.known_handles - current_handles\r\n"
    "\r\n"
    "        if lost_handles:\r\n"
    "            safe_print(f\"[hermes] Detected window exit \u2014 reload pending\")\r\n"
    "            state.reload_pending = True\r\n"
    "            state.woken_handles -= lost_handles  # gone handles no longer woken\r\n"
    "\r\n"
    "        if state.reload_pending and current_handles:\r\n"
    "            unwoken = [w for w in windows if w[\"handle\"] not in state.woken_handles]\r\n"
    "            for entry in unwoken:\r\n"
    "                win = entry[\"window\"]\r\n"
    "                if win is None:\r\n"
    "                    continue\r\n"
    "                safe_print(f\"[hermes] New window up \u2014 waiting for chat ready...\")\r\n"
    "                chat = wait_for_chat_ready(win, timeout=30)\r\n"
    "                if chat:\r\n"
    "                    send_wake_message(win, config[\"wake_msg\"])\r\n"
    "                    state.woken_handles.add(entry[\"handle\"])\r\n"
    "                    state.reload_pending = False\r\n"
    "                else:\r\n"
    "                    safe_print(\"[hermes] Chat never ready \u2014 skipping wake\")\r\n"
    "                break  # one window per poll cycle\r\n"
    "\r\n"
    "    # \u2500\u2500 Update button \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\r\n"
    "    if triggers.get(\"update_button\") and windows:\r\n"
    "        update_debounce = config.get(\"update_click_debounce_seconds\", 30)\r\n"
    "        if time.time() - state.last_update_click_time > update_debounce:\r\n"
    "            clicked = trigger_update_button(windows)\r\n"
    "            if clicked:\r\n"
    "                state.reload_pending = True  # update restart coming\r\n"
    "                state.last_update_click_time = time.time()\r\n"
    "\r\n"
)

content = content[:wake_i] + new_wake_update + content[reload_i:]

with open(TARGET, "wb") as f:
    f.write(content.encode("utf-8"))
print("OK: wake + update button sections patched")
print("OK: file written")
