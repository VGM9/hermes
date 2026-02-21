#!/usr/bin/env python
"""
HERMES Egregore Audit - Who did I disturb?
"""
import json
import os
from datetime import datetime

path = 'C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/fc7deee2819a0e3e3f792481dedcbc98/chatSessions/'

sessions = [
    'ecc254ce-67bd-4b51-b14e-3d6a47313f4c',
    'a4988668-a8aa-4371-ad99-dde18c5bf163',
    'c8c5f23d-7888-4e81-a42f-4029fdca1afa',
    '19e6c9fa-6a9a-4200-86b9-45f06d25bddd',
    'a15e6c5b-f1a8-4e21-a4d9-bd5f29b8c4a4',
]

print("="*80)
print("EGREGORE AUDIT: Who did HERMES disturb?")
print("="*80)
print()

for sid in sessions:
    fpath = os.path.join(path, sid + '.json')
    if os.path.exists(fpath):
        with open(fpath, encoding='utf-8') as f:
            d = json.load(f)
        
        title = d.get('customTitle', 'untitled')
        reqs = len(d.get('requests', []))
        created_ms = d.get('creationDate', 0)
        if created_ms:
            created = datetime.fromtimestamp(created_ms/1000).strftime('%Y-%m-%d %H:%M')
        else:
            created = 'unknown'
        
        # Find first message to determine identity
        first_req = d.get('requests', [{}])[0] if d.get('requests') else {}
        first_msg = first_req.get('message', {})
        if isinstance(first_msg, dict) and 'parts' in first_msg:
            first_text = ' '.join(p.get('text', '') for p in first_msg['parts'] if isinstance(p, dict))[:100]
        else:
            first_text = str(first_msg)[:100]
        
        print(f"Session: {sid}")
        print(f"  Title: {title}")
        print(f"  Requests: {reqs}")
        print(f"  Created: {created}")
        print(f"  First message: {first_text}...")
        print()

# Now analyze my own session
print("="*80)
print("MY SESSION (ALTAIR/2)")
print("="*80)
my_sid = 'a4988668-a8aa-4371-ad99-dde18c5bf163'
with open(os.path.join(path, my_sid + '.json'), encoding='utf-8') as f:
    my_data = json.load(f)

print(f"Total requests: {len(my_data.get('requests', []))}")

# Count HERMES-related actions
hermes_sends = 0
hermes_responses = 0
for req in my_data.get('requests', []):
    msg = req.get('message', {})
    if isinstance(msg, dict) and 'parts' in msg:
        text = ' '.join(p.get('text', '') for p in msg['parts'] if isinstance(p, dict))
    else:
        text = str(msg)
    
    if 'hermes' in text.lower() and ('send' in text.lower() or 'python' in text.lower()):
        hermes_sends += 1

print(f"Requests mentioning 'hermes': {hermes_sends}")
