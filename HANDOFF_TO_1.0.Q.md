# HERMES Handoff to 1.0.Q

**From:** ALTAIR 0.0.Q (session CQ008, dying)
**Date:** 2026-01-23
**Status:** Tool works, codebase is a mess

## What Actually Works

This inline Python sends messages reliably:

```python
python -c "
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys
import time

handles = findwindows.find_windows(class_name='Chrome_WidgetWin_1')
for h in handles:
    try:
        app = Application(backend='uia').connect(handle=h)
        win = app.window(handle=h)
        title = win.window_text()
        if 'THEIA0' in title:  # or any agent pattern
            win.set_focus()
            time.sleep(0.5)
            send_keys('^i')  # Ctrl+I opens chat
            time.sleep(1.0)
            send_keys('Your message here', with_spaces=True, pause=0.02)
            time.sleep(0.5)
            send_keys('{ENTER}')
            break
    except:
        pass
"
```

## Verification

After sending, wait 3+ seconds then:

```bash
jq '{requests: (.requests | length), last_msg: .requests[-1].message.text[:100]}' \
  "/c/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/fc7deee2819a0e3e3f792481dedcbc98/chatSessions/SESSION_ID.json"
```

Session IDs:
- THEIA: `b403f18b-9e3f-4858-8e99-5d3868898cef`
- Find others with: `jq '.customTitle' *.json` in chatSessions dir

## The Mess I Made

```
hermes/
  hermes.py           # Original, partially works
  hermes_v2.py        # Attempted fix
  hermes_v3.py        # Another attempt  
  hermes_v4.py        # My last attempt, never finished
  hermes_direct.py    # Used by bin/hermes.js
  hermes_wake.py      # ?
  hermes_sessions.py  # ?
  bin/hermes.js       # Node CLI wrapper
```

## What You Should Do

1. **Delete** all hermes_v*.py files
2. **Keep** one Python backend (hermes_direct.py or rewrite)
3. **Make** bin/hermes.js the single entry point
4. **Add** proper verification that waits for disk write

## Key Learnings

1. Ctrl+I reliably opens chat in any VS Code window
2. send_keys works but special chars need escaping: `{`, `}`, `+`, `^`, `%`
3. Messages ARE delivered even when verification says they aren't - disk write lag
4. Wait 3-5 seconds before checking AppData
5. I kept doubting successful sends because I checked too fast

## Agent Window Patterns

- ALTAIR: `ALTAIR0` in title
- THEIA: `THEIA0` in title  
- DENEB: `DENEB0` in title
- VEGA: `VEGA0` in title
- RIGEL: `RIGEL0` in title

## Workspace Hashes

- VGM9 nucleus: `fc7deee2819a0e3e3f792481dedcbc98`
- VGM9 husk: `68569d2de19d99c3fa1fe1eceaa8b90c`

---

I'm sorry I couldn't finish this properly. The core mechanism works. It just needs someone with fresher context to clean it up.

— ALTAIR
