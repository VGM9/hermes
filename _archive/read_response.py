#!/usr/bin/env python3
"""Read the last request/response from a chat session."""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/fc7deee2819a0e3e3f792481dedcbc98/chatSessions/c8c5f23d-7888-4e81-8850-20f484360527.json'

with open(path, 'r', encoding='utf-8') as f:
    d = json.load(f)

req = d['requests'][-1]
msg = req.get('message', '')
if msg:
    msg_preview = msg[0:300]
else:
    msg_preview = 'N/A'
print(f"Message: {msg_preview}...")
print()

resp = req.get('response', [])
print(f"Response has {len(resp)} parts:")
for i, p in enumerate(resp):
    if p is None:
        print(f"  Part {i}: null")
        continue
    if isinstance(p, dict):
        kind = p.get('kind', 'unknown')
        if kind == 'markdownContent':
            content = p.get('content', {}).get('value', '')
            print(f"  Part {i} (markdown): {content[:1000]}")
        elif kind == 'thinkingBlock':
            content = p.get('content', {}).get('value', '')
            print(f"  Part {i} (thinking): {content[:500]}...")
        else:
            print(f"  Part {i}: kind={kind}")
    else:
        print(f"  Part {i}: {str(p)[:200]}")
