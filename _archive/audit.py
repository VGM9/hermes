#!/usr/bin/env python
"""
HERMES Audit - Track all messages sent and responses received
"""
import json
import os
from datetime import datetime
from collections import defaultdict

VGM9_NUCLEUS = 'C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/fc7deee2819a0e3e3f792481dedcbc98/chatSessions/'
ICNBAW_PATH = 'C:/Users/victorb/AppData/Roaming/Code - Insiders/User/workspaceStorage/7eb1d1f8c9b29654e9a159ce7a2f5b6e/chatSessions/'

def extract_text(msg):
    """Extract text from message object"""
    if isinstance(msg, dict) and 'parts' in msg:
        return ' '.join(p.get('text', '') for p in msg['parts'] if isinstance(p, dict))
    elif isinstance(msg, str):
        return msg
    return str(msg)

def scan_sessions(path, workspace_name):
    """Scan all sessions for HERMES-related activity"""
    if not os.path.exists(path):
        return []
    
    results = []
    
    for fname in os.listdir(path):
        if not fname.endswith('.json'):
            continue
        
        fpath = os.path.join(path, fname)
        try:
            with open(fpath, encoding='utf-8') as f:
                d = json.load(f)
        except:
            continue
        
        title = d.get('customTitle', 'untitled')
        sid = fname.replace('.json', '')
        requests = d.get('requests', [])
        
        for i, req in enumerate(requests):
            text = extract_text(req.get('message', ''))
            
            # Check for HERMES indicators
            indicators = ['HERMES', 'ALTAIR', 'VEGA', 'CQ=', 'Q-semver', 'session', 'qopilot']
            matches = [ind for ind in indicators if ind.upper() in text.upper()]
            
            if matches or 'HERMES' in text.upper():
                ts = req.get('variableData', {}).get('requestTime', 'unknown')
                response = req.get('response', {})
                
                # Get response text
                if isinstance(response, dict):
                    resp_text = response.get('message', '')
                    if isinstance(resp_text, dict) and 'value' in resp_text:
                        resp_text = resp_text.get('value', '')
                else:
                    resp_text = str(response)[:200]
                
                results.append({
                    'workspace': workspace_name,
                    'session_id': sid[:12],
                    'session_title': title,
                    'request_idx': i,
                    'timestamp': ts,
                    'message': text[:150],
                    'response': str(resp_text)[:200],
                    'indicators': matches
                })
    
    return results

def find_injected_messages(path, workspace_name):
    """Find messages that were likely injected (no tool calls, direct user text with HERMES markers)"""
    if not os.path.exists(path):
        return []
    
    injected = []
    
    for fname in os.listdir(path):
        if not fname.endswith('.json'):
            continue
        
        fpath = os.path.join(path, fname)
        try:
            with open(fpath, encoding='utf-8') as f:
                d = json.load(f)
        except:
            continue
        
        title = d.get('customTitle', 'untitled')
        sid = fname.replace('.json', '')
        
        for i, req in enumerate(d.get('requests', [])):
            text = extract_text(req.get('message', ''))
            
            # Messages I sent via HERMES contain these patterns
            hermes_signatures = [
                'This is ALTAIR',
                'HERMES test',
                'Message from ALTAIR',
                'Message from session',
                'Report your identity',
                'use qopilot',
                'qopilot_list_sessions',
                'CQ=8',
                'ALTAIR/2',
            ]
            
            for sig in hermes_signatures:
                if sig.lower() in text.lower():
                    ts = req.get('variableData', {}).get('requestTime', 'unknown')
                    
                    # Get response
                    resp = req.get('response', {})
                    if isinstance(resp, dict) and 'message' in resp:
                        r = resp['message']
                        if isinstance(r, dict):
                            resp_text = r.get('value', '')[:300]
                        else:
                            resp_text = str(r)[:300]
                    else:
                        resp_text = str(resp)[:300]
                    
                    injected.append({
                        'workspace': workspace_name,
                        'session_id': sid[:12],
                        'session_title': title,
                        'request_idx': i,
                        'timestamp': ts,
                        'message': text[:200],
                        'response': resp_text,
                        'signature': sig
                    })
                    break
    
    return injected

def main():
    print("=" * 80)
    print("HERMES AUDIT REPORT")
    print("=" * 80)
    print()
    
    # Scan VGM9 workspace
    print("## VGM9 Workspace (Nucleus)")
    print("-" * 40)
    injected_vgm9 = find_injected_messages(VGM9_NUCLEUS, 'VGM9')
    
    sessions_touched = set()
    for msg in injected_vgm9:
        sessions_touched.add(msg['session_id'])
        print(f"\nSession: [{msg['session_id']}] {msg['session_title']}")
        print(f"  Timestamp: {msg['timestamp']}")
        print(f"  Signature: {msg['signature']}")
        print(f"  Message: {msg['message'][:100]}...")
        if msg['response']:
            print(f"  Response: {msg['response'][:150]}...")
    
    print(f"\n\nTotal injected messages in VGM9: {len(injected_vgm9)}")
    print(f"Unique sessions touched: {len(sessions_touched)}")
    
    # Scan ICNBAW workspace
    print("\n\n## 00_ICNBAW Workspace (External)")
    print("-" * 40)
    injected_icnbaw = find_injected_messages(ICNBAW_PATH, '00_ICNBAW')
    
    for msg in injected_icnbaw:
        print(f"\nSession: [{msg['session_id']}] {msg['session_title']}")
        print(f"  Message: {msg['message'][:100]}...")
        if msg['response']:
            print(f"  Response: {msg['response'][:150]}...")
    
    print(f"\nTotal injected to ICNBAW: {len(injected_icnbaw)}")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total HERMES injections detected: {len(injected_vgm9) + len(injected_icnbaw)}")
    print(f"Workspaces touched: 2 (VGM9, 00_ICNBAW)")
    print(f"Sessions in VGM9 touched: {len(sessions_touched)}")
    
    # List unique sessions
    print("\n## Unique Sessions Disturbed:")
    for sid in sessions_touched:
        print(f"  - {sid}")

if __name__ == '__main__':
    main()
