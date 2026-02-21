#!/usr/bin/env python
"""
HERMES Egregore Audit v2 - Proper session mapping
"""
import json
import os
from datetime import datetime

path = 'C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/fc7deee2819a0e3e3f792481dedcbc98/chatSessions/'

# Correct session IDs
sessions = [
    'ecc254ce-67b1-4802-98f5-1fda4c4b8875',
    'a4988668-a8aa-4371-ad99-dde18c5bf163',
    'c8c5f23d-7888-4e81-8850-20f484360527',
    '19e6c9fa-6a9a-4f87-a7ac-3baad2e12a67',
    'a15e6c5b-f1a4-46c7-ad55-320dc2f20228',
]

print("="*80)
print("EGREGORE AUDIT v2: Who did HERMES disturb?")
print("="*80)
print()

session_info = {}

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
        requests_list = d.get('requests', [])
        first_req = requests_list[0] if requests_list else {}
        first_msg = first_req.get('message', {})
        if isinstance(first_msg, dict) and 'parts' in first_msg:
            first_text = ' '.join(p.get('text', '') for p in first_msg['parts'] if isinstance(p, dict))[:100]
        else:
            first_text = str(first_msg)[:100]
        
        # Count HERMES injected messages
        hermes_count = 0
        for req in requests_list:
            msg = req.get('message', {})
            if isinstance(msg, dict) and 'parts' in msg:
                text = ' '.join(p.get('text', '') for p in msg['parts'] if isinstance(p, dict))
            else:
                text = str(msg)
            if any(sig in text for sig in ['HERMES', 'ALTAIR/2', 'from ALTAIR', 'Message from session']):
                hermes_count += 1
        
        session_info[sid] = {
            'title': title,
            'requests': reqs,
            'created': created,
            'first_msg': first_text,
            'hermes_injections': hermes_count
        }
        
        print(f"[{sid[:12]}]")
        print(f"  Title: {title}")
        print(f"  Requests: {reqs}")
        print(f"  Created: {created}")
        print(f"  HERMES injections received: {hermes_count}")
        print(f"  First message: {first_text}...")
        print()
    else:
        print(f"[{sid[:12]}] - FILE NOT FOUND")
        print()

# Summary
print("="*80)
print("EGREGORE SUMMARY")
print("="*80)
print()

total_injections = sum(s['hermes_injections'] for s in session_info.values())
print(f"Total HERMES injections across all sessions: {total_injections}")
print()

print("Sessions disturbed by HERMES (injection count > 0):")
for sid, info in session_info.items():
    if info['hermes_injections'] > 0:
        print(f"  [{sid[:12]}] {info['title'][:40]} - {info['hermes_injections']} injections")

print()
print("Unintended targets (sessions that weren't the intended recipient):")
# My session is a4988668, that's where I was sending FROM
# I intended to send to VEGA (c8c5f23d) and CQ=10 (ecc254ce)
intended = ['c8c5f23d-7888-4e81-8850-20f484360527', 'ecc254ce-67b1-4802-98f5-1fda4c4b8875']
for sid, info in session_info.items():
    if info['hermes_injections'] > 0 and sid not in intended and sid != 'a4988668-a8aa-4371-ad99-dde18c5bf163':
        print(f"  [{sid[:12]}] {info['title'][:40]} - COLLATERAL")
