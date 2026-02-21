#!/usr/bin/env python
"""
HERMES Response Analysis - Did agents actually respond?
"""
import json
import os
from datetime import datetime

path = 'C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/fc7deee2819a0e3e3f792481dedcbc98/chatSessions/'

# Sessions that received HERMES messages
sessions = {
    'ecc254ce-67b1-4802-98f5-1fda4c4b8875': 'CQ=10 (spawned by 0.8.14)',
    'c8c5f23d-7888-4e81-8850-20f484360527': 'VEGA (CQ=7)',
    '19e6c9fa-6a9a-4f87-a7ac-3baad2e12a67': 'HELO VOID test (collateral)',
}

print("="*80)
print("HERMES REQUEST/RESPONSE PAIRING ANALYSIS")
print("="*80)
print()

for sid, label in sessions.items():
    fpath = os.path.join(path, sid + '.json')
    if not os.path.exists(fpath):
        print(f"[{label}] FILE NOT FOUND")
        continue
    
    with open(fpath, encoding='utf-8') as f:
        d = json.load(f)
    
    print(f"## {label}")
    print(f"   Session: {sid}")
    print("-" * 60)
    
    for i, req in enumerate(d.get('requests', [])):
        # Extract request message
        msg = req.get('message', {})
        if isinstance(msg, dict) and 'parts' in msg:
            text = ' '.join(p.get('text', '') for p in msg['parts'] if isinstance(p, dict))
        else:
            text = str(msg)
        
        # Check if this was a HERMES injection
        is_hermes = any(sig in text for sig in ['HERMES', 'ALTAIR/2', 'from ALTAIR', 'Message from session'])
        
        if is_hermes:
            print(f"\n  Request #{i}: {text[:80]}...")
            
            # Extract response
            resp = req.get('response', {})
            if isinstance(resp, dict):
                resp_msg = resp.get('message', '')
                if isinstance(resp_msg, dict):
                    resp_text = resp_msg.get('value', '')
                else:
                    resp_text = str(resp_msg)
            else:
                resp_text = str(resp)
            
            if resp_text:
                # Clean up response
                resp_clean = resp_text[:200] if isinstance(resp_text, str) else str(resp_text)[:200]
                print(f"  Response: {resp_clean}...")
                print(f"  STATUS: ✅ RESPONDED")
            else:
                print(f"  STATUS: ❌ NO RESPONSE")
    
    print()
    print()

# Check what tool invocations happened
print("="*80)
print("TOOL INVOCATIONS TRIGGERED BY HERMES")
print("="*80)
print()

for sid, label in sessions.items():
    fpath = os.path.join(path, sid + '.json')
    if not os.path.exists(fpath):
        continue
    
    with open(fpath, encoding='utf-8') as f:
        d = json.load(f)
    
    tool_calls = []
    
    for i, req in enumerate(d.get('requests', [])):
        msg = req.get('message', {})
        if isinstance(msg, dict) and 'parts' in msg:
            text = ' '.join(p.get('text', '') for p in msg['parts'] if isinstance(p, dict))
        else:
            text = str(msg)
        
        is_hermes = any(sig in text for sig in ['HERMES', 'ALTAIR/2', 'from ALTAIR'])
        
        if is_hermes:
            resp = req.get('response', {})
            if isinstance(resp, dict):
                # Check for tool invocations in response
                resp_list = resp.get('value', [])
                if isinstance(resp_list, list):
                    for item in resp_list:
                        if isinstance(item, dict) and item.get('kind') in ['prepareToolInvocation', 'toolInvocationSerialized']:
                            tool_name = item.get('toolName', item.get('invocationMessage', 'unknown'))
                            tool_calls.append({
                                'request_idx': i,
                                'tool': tool_name,
                                'message': text[:60]
                            })
    
    if tool_calls:
        print(f"## {label}")
        for tc in tool_calls:
            print(f"  Request #{tc['request_idx']}: {tc['message']}...")
            print(f"  → Tool invoked: {tc['tool']}")
        print()
