#!/usr/bin/env python3
"""
Agent Approval Detection - VSCode Source-Based Implementation
Identifies paused chat agents waiting for approval using stable identifiers from VSCode source.

Based on analysis of:
- src/vs/workbench/contrib/chat/browser/actions/chatToolActions.ts
- src/vs/workbench/contrib/chat/browser/widget/chatContentParts/chatConfirmationWidget.ts
- src/vs/workbench/contrib/chat/browser/widget/chatContentParts/toolInvocationParts/chatTerminalToolConfirmationSubPart.ts

Stable identifiers (version-resilient):
- primary button class: "monaco-button small monaco-text-button"
- secondary button class: "monaco-button secondary small monaco-text-button"
- Action IDs: workbench.action.chat.acceptTool, workbench.action.chat.skipTool
- Keybindings: Ctrl+Enter (accept), Ctrl+Alt+Enter (skip)

Author: Theca (AI Agent)
Date: 2026-02-04
"""

import sys
from dataclasses import dataclass
from typing import List, Optional
from pywinauto import Application, findwindows
from pywinauto.controls.uiawrapper import UIAWrapper


@dataclass
class PausedAgentRequest:
    """
    Structured representation of an agent approval request.
    """
    window_handle: int
    window_title: str
    request_type: str  # e.g., "Allow reading external directory"
    full_request_text: str
    files_to_read: List[str]
    commands_to_run: List[str]
    allow_button: Optional[UIAWrapper]
    skip_button: Optional[UIAWrapper]
    
    def to_dict(self):
        return {
            'window_handle': self.window_handle,
            'window_title': self.window_title,
            'request_type': self.request_type,
            'full_request_text': self.full_request_text[:500],  # Truncate for display
            'files_count': len(self.files_to_read),
            'files_to_read': self.files_to_read,
            'commands_count': len(self.commands_to_run),
            'commands_to_run': self.commands_to_run,
            'has_allow_button': self.allow_button is not None,
            'has_skip_button': self.skip_button is not None,
        }


def find_vscode_windows() -> List[int]:
    """
    Find all VSCode windows using stable Chrome_WidgetWin_1 class.
    
    VSCode runs on Electron (Chromium), so this class name is stable.
    """
    return findwindows.find_windows(class_name='Chrome_WidgetWin_1')


def extract_files_from_request_text(full_text: str) -> List[str]:
    """
    Parse the full request text to extract file paths.
    
    Format: "Read [](file:///c%3A/path/to/file)"
    """
    import re
    import urllib.parse
    
    # Match file:/// URIs
    pattern = r'file:///([^\)]+)'
    matches = re.findall(pattern, full_text)
    
    files = []
    for match in matches:
        # URL decode (e.g., %3A -> :)
        decoded = urllib.parse.unquote(match)
        if decoded not in files:  # Deduplicate
            files.append(decoded)
    
    return files


def extract_commands_from_request_text(full_text: str) -> List[str]:
    """
    Parse the full request text to extract terminal commands.
    
    Format: "Ran terminal command: <command>"
    """
    import re
    
    pattern = r'Ran terminal command: (.+?)(?:\s+Read|$)'
    matches = re.findall(pattern, full_text, re.MULTILINE)
    
    return [cmd.strip() for cmd in matches if cmd.strip()]


def find_paused_agents_in_window(handle: int) -> Optional[PausedAgentRequest]:
    """
    Inspect a single VSCode window for paused agent approval requests.
    
    Uses stable identifiers from VSCode source:
    - ListItem with "Chat confirmation required"
    - Primary button: "monaco-button small monaco-text-button"
    - Secondary button: "monaco-button secondary small monaco-text-button"
    
    Returns None if no paused agent found.
    """
    try:
        app = Application(backend='uia').connect(handle=handle)
        win = app.window(handle=handle)
        title = win.window_text()
        
        # Find the confirmation request text
        all_elements = win.descendants()
        
        full_request_text = None
        request_type = None
        
        for elem in all_elements:
            try:
                ctrl_type = elem.element_info.control_type
                text = elem.window_text()
                
                # VSCode chat confirmations appear as ListItem elements
                if ctrl_type == 'ListItem' and 'Chat confirmation required' in text:
                    full_request_text = text
                    
                    # Extract request type (text between "required:" and "?")
                    if 'Allow reading external directory?' in text:
                        request_type = 'Allow reading external directory'
                    elif 'Allow' in text:
                        # Generic extraction
                        import re
                        match = re.search(r'required:\s*(.+?)\?', text)
                        if match:
                            request_type = match.group(1).strip()
                    
                    break
            except:
                continue
        
        if not full_request_text:
            return None  # No paused agent in this window
        
        # Extract structured data from the request
        files_to_read = extract_files_from_request_text(full_request_text)
        commands_to_run = extract_commands_from_request_text(full_request_text)
        
        # Find buttons using stable class names
        buttons = win.descendants(control_type='Button')
        allow_button = None
        skip_button = None
        
        for btn in buttons:
            try:
                class_name = btn.element_info.class_name or ''
                btn_text = btn.element_info.name or ''
                
                # Stable identifier: monaco-button small monaco-text-button
                if 'small monaco-text-button' in class_name:
                    if 'secondary' in class_name:
                        skip_button = btn
                    elif 'Allow' in btn_text or 'Accept' in btn_text:
                        allow_button = btn
            except:
                continue
        
        return PausedAgentRequest(
            window_handle=handle,
            window_title=title,
            request_type=request_type or 'Unknown',
            full_request_text=full_request_text,
            files_to_read=files_to_read,
            commands_to_run=commands_to_run,
            allow_button=allow_button,
            skip_button=skip_button,
        )
        
    except Exception as e:
        # Window may have closed or be inaccessible
        return None


def find_all_paused_agents() -> List[PausedAgentRequest]:
    """
    Scan all VSCode windows and return list of paused agent requests.
    """
    vscode_windows = find_vscode_windows()
    paused_agents = []
    
    for handle in vscode_windows:
        agent = find_paused_agents_in_window(handle)
        if agent:
            paused_agents.append(agent)
    
    return paused_agents


def main():
    """
    CLI interface for detecting paused agents.
    """
    import json
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Detect paused chat agents in VSCode windows',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all paused agents
  python hermes_agent_approval_detection.py
  
  # JSON output for processing
  python hermes_agent_approval_detection.py --json
  
  # Verbose output with full request text
  python hermes_agent_approval_detection.py --verbose
"""
    )
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show full request text')
    
    args = parser.parse_args()
    
    paused_agents = find_all_paused_agents()
    
    if args.json:
        output = [agent.to_dict() for agent in paused_agents]
        print(json.dumps(output, indent=2))
    else:
        if not paused_agents:
            print("No paused agents found.")
            sys.exit(0)
        
        print(f"Found {len(paused_agents)} paused agent(s):")
        print("=" * 80)
        
        for i, agent in enumerate(paused_agents, 1):
            print(f"\n#{i} - {agent.window_title[:60]}...")
            print(f"Request Type: {agent.request_type}")
            print(f"Files to read: {len(agent.files_to_read)}")
            for f in agent.files_to_read[:5]:  # Show first 5
                print(f"  - {f}")
            if len(agent.files_to_read) > 5:
                print(f"  ... and {len(agent.files_to_read) - 5} more")
            
            print(f"Commands to run: {len(agent.commands_to_run)}")
            for cmd in agent.commands_to_run:
                print(f"  - {cmd[:70]}...")
            
            print(f"Allow button: {'Found' if agent.allow_button else 'Missing'}")
            print(f"Skip button: {'Found' if agent.skip_button else 'Missing'}")
            
            if args.verbose:
                print(f"\nFull request text:")
                print(agent.full_request_text[:1000])
                if len(agent.full_request_text) > 1000:
                    print("... (truncated)")


if __name__ == '__main__':
    main()
