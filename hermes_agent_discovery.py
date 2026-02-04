#!/usr/bin/env python3
"""
HERMES Agent Discovery - Deterministic enumeration of paused agents

ARCHITECTURE:
This module is DETERMINISTIC - it only reads state, never modifies it.
It returns structured data about paused agents for downstream inference/decision modules.

Separation of Concerns:
- This module: Facts (what agents are paused, what they want)
- Approval Decision module: Logic (should we approve based on policy?)
- Orchestrator: Action (click the button)

WORKFLOW:
Step 1 (Discovery) → Step 2 (Decision) → Step 3 (Action)
  Deterministic      Inference          Deterministic
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# Suppress pywinauto logging
logging.getLogger('pywinauto').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class PausedAgent:
    """Represents a single paused agent awaiting approval."""
    session_id: str              # VSCode session UUID
    window_handle: int           # Windows HWND
    window_title: str            # Window title
    window_type: str             # 'main', 'external', 'other'
    message: str                 # Visible message to user
    action_name: Optional[str]   # Name of action being requested
    is_split_button: bool        # Allow button has dropdown options
    has_skip_button: bool        # Skip button available
    timestamp: float             # Unix timestamp of discovery
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class DiscoveryReport:
    """Summary of all paused agents found."""
    total_paused: int
    paused_agents: List[PausedAgent]
    discovery_ts: float
    environment: Dict[str, str]  # VSCode workspace info, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_paused': self.total_paused,
            'paused_agents': [a.to_dict() for a in self.paused_agents],
            'discovery_ts': self.discovery_ts,
            'environment': self.environment
        }


def discover_paused_agents() -> DiscoveryReport:
    """
    Scan all VS Code windows, identify which have pending agent approvals.
    
    DETERMINISTIC: Pure function that reads state, returns structured data.
    No side effects, no approvals, no decisions.
    
    Returns:
        DiscoveryReport with list of all paused agents
    """
    import time
    from pywinauto import Application, findwindows
    from pywinauto.keyboard import send_keys
    
    start_time = time.time()
    paused = []
    
    try:
        # Find all VSCode windows
        handles = findwindows.find_windows(class_name="Chrome_WidgetWin_1")
        
        for handle in handles:
            try:
                app = Application(backend="uia").connect(handle=handle)
                win = app.window(handle=handle)
                title = win.window_text()
                
                if "Visual Studio Code" not in title:
                    continue
                
                # Import the wake module to detect approval state
                import hermes_wake
                
                window_type = _classify_window(win)
                approval_state = hermes_wake.detect_approval_state(win)
                
                # If this window has approval buttons, extract details
                if approval_state.get('has_approval'):
                    message = _extract_message(win)
                    action_name = _extract_action_name(win)
                    session_id = _extract_session_id(win, title)
                    
                    agent = PausedAgent(
                        session_id=session_id,
                        window_handle=handle,
                        window_title=title,
                        window_type=window_type,
                        message=message,
                        action_name=action_name,
                        is_split_button=approval_state.get('is_split', False),
                        has_skip_button=approval_state.get('skip_button') is not None,
                        timestamp=start_time
                    )
                    paused.append(agent)
                    
            except Exception as e:
                logger.debug(f"Error scanning window {handle}: {e}")
                pass
        
        # Build environment context
        environment = _capture_environment()
        
        report = DiscoveryReport(
            total_paused=len(paused),
            paused_agents=paused,
            discovery_ts=start_time,
            environment=environment
        )
        
        return report
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return DiscoveryReport(
            total_paused=0,
            paused_agents=[],
            discovery_ts=start_time,
            environment={'error': str(e)}
        )


def _classify_window(win) -> str:
    """Classify window type: main, external, other."""
    try:
        # Check for editor infrastructure (main window)
        tree_items = win.descendants(control_type="TreeItem", depth=15)
        has_sessions = any(
            '/AS/' in (item.element_info.name or '')
            for item in tree_items[:30]
        )
        if has_sessions:
            return 'main'
        
        # Check for external chat window
        edits = win.descendants(control_type="Edit", depth=10)
        has_chat = any(
            "Chat Input" in (e.element_info.name or '')
            for e in edits
        )
        if has_chat:
            return 'external'
        
        return 'other'
    except:
        return 'unknown'


def _extract_message(win) -> str:
    """Extract visible message/prompt text from window."""
    try:
        # Look for Text controls that might contain the agent message
        texts = win.descendants(control_type="Text")
        messages = []
        for text in texts[:10]:
            name = text.element_info.name or ""
            if name and len(name) > 10 and len(name) < 500:
                messages.append(name)
        
        return ' | '.join(messages[:2]) if messages else "Unknown message"
    except:
        return "Unable to extract message"


def _extract_action_name(win) -> Optional[str]:
    """Extract the specific action being requested (tool name, command, etc)."""
    try:
        # Look for button names that might indicate the action
        buttons = win.descendants(control_type="Button")
        for btn in buttons[:20]:
            name = (btn.element_info.name or "").lower()
            if 'allow' not in name and 'skip' not in name and len(name) > 3:
                return btn.element_info.name
        
        return None
    except:
        return None


def _extract_session_id(win, title: str) -> str:
    """Extract session ID from window content or title."""
    try:
        # Try to find session UUID in tree items
        tree_items = win.descendants(control_type="TreeItem")
        for item in tree_items[:30]:
            name = item.element_info.name or ""
            # Simple UUID detection (8-4-4-4-12 hex pattern)
            if len(name) > 30 and '-' in name:
                return name[:36]  # Common UUID length
        
        # Fallback: use title
        return title[-20:] if title else "unknown"
    except:
        return "unknown"


def _capture_environment() -> Dict[str, str]:
    """Capture VSCode workspace and environment info."""
    try:
        import hermes_config
        appdata = hermes_config.get_appdata_path()
        return {
            'appdata_path': str(appdata),
            'workspace_count': str(len(list(appdata.iterdir())))
        }
    except Exception as e:
        return {'error': str(e)}


def print_discovery_report(report: DiscoveryReport):
    """Pretty-print discovery report."""
    print(f"\n=== HERMES Agent Discovery ===")
    print(f"Timestamp: {report.discovery_ts}")
    print(f"Total Paused Agents: {report.total_paused}")
    print()
    
    for i, agent in enumerate(report.paused_agents, 1):
        print(f"[{i}] Paused Agent")
        print(f"    Session: {agent.session_id}")
        print(f"    Window: {agent.window_type} (handle={agent.window_handle})")
        print(f"    Title: {agent.window_title}")
        print(f"    Action: {agent.action_name or 'Unknown'}")
        print(f"    Message: {agent.message}")
        print(f"    Split Button: {agent.is_split_button}")
        print(f"    Has Skip: {agent.has_skip_button}")
        print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Discover paused agents awaiting approval")
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    report = discover_paused_agents()
    
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_discovery_report(report)
        if report.total_paused > 0:
            print("Use --json for machine-readable output")
    
    sys.exit(0 if report.total_paused == 0 else 0)
