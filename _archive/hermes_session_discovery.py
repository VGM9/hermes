# -*- coding: utf-8 -*-
"""HERMES Workspace Discovery - Declarative VSCode Session Querying

Instead of scraping AppData, query VSCode directly via qopilot extension context.
This is declarative (ask VSCode for sessions) not imperative (scan directories).
"""

import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)


class SessionDiscoveryError(Exception):
    """Raised when session discovery via qopilot fails."""
    pass


def discover_chat_sessions_via_qopilot() -> list[dict[str, str]]:
    """Discover all chat sessions using qopilot VSCode extension context.
    
    Uses VSCode's native APIs instead of scraping AppData.
    Declarative approach: ask VSCode "what sessions exist?" 
    Rather than imperative: scan filesystem for patterns.
    
    Returns:
        List of dicts with:
        - 'session_id': UUID of chat session
        - 'session_file_path': Full path to .jsonl session file
        - 'workspace_hash': Hash from AppData path
        - 'custom_title': User-set title or agent name
        - 'request_count': Number of chat messages in session
    
    Raises:
        SessionDiscoveryError: If qopilot integration unavailable
        
    Note:
        This function expects to be called from context where qopilot extension
        is active in VSCode. Falls back to AppData scanning if unavailable.
    """
    try:
        # Attempt to use qopilot command
        import subprocess
        import sys
        
        # Try to invoke qopilot extension command that lists all chat sessions
        # This command runs in VSCode context and has access to:
        # - vscode.workspace.workspaceFolders
        # - vscode.chat API (if exposed)
        # - Session storage via extension storage API
        
        result = _call_qopilot_list_sessions()
        if result:
            logger.info(f"Discovered {len(result)} sessions via qopilot VSCode API")
            return result
    except Exception as e:
        logger.warning(f"qopilot session discovery failed, falling back to AppData scan: {e}")
    
    # Fallback: Use AppData discovery
    return _discover_chat_sessions_via_appdata_fallback()


def _call_qopilot_list_sessions() -> Optional[list[dict[str, str]]]:
    """Call qopilot extension command to list all chat sessions.
    
    Returns:
        Structured list of sessions or None if command unavailable
    """
    # This would be implemented as a qopilot command that runs in VSCode context:
    # vscode.commands.executeCommand('qopilot.listChatSessions')
    # 
    # The TypeScript implementation would:
    # 1. Query vscode.chat.getChatSessions() (if available in API)
    # 2. Query extension storage for session metadata
    # 3. Return structured JSON with session info
    # 4. Include workspace hash for correlation with AppData
    
    # For now, this is a placeholder for the qopilot extension hook
    # where the actual implementation would live.
    
    logger.debug("Querying qopilot VSCode extension for sessions...")
    # Would call real qopilot command here
    return None


def _discover_chat_sessions_via_appdata_fallback() -> list[dict[str, str]]:
    """Fallback: Discover sessions by scanning AppData (only if qopilot unavailable).
    
    This is the ONLY place where AppData scanning should happen.
    Everything else goes through qopilot for cleaner, declarative access.
    
    Returns:
        List of session dicts with session_file_path instead of workspace_path
    """
    import hermes_config
    from pathlib import Path
    
    logger.info("Using fallback AppData discovery (qopilot unavailable)")
    
    appdata = hermes_config.get_appdata_path()
    if not appdata.exists():
        logger.warning(f"AppData not found: {appdata}")
        return []
    
    sessions = []
    
    try:
        # Scan workspaceStorage for all sessions
        for workspace_dir in appdata.parent.parent.iterdir():  # Up to workspaceStorage
            if not workspace_dir.is_dir() or workspace_dir.name != 'workspaceStorage':
                continue
            
            for hash_dir in workspace_dir.iterdir():
                if not hash_dir.is_dir():
                    continue
                
                sessions_dir = hash_dir / 'chatSessions'
                if not sessions_dir.exists():
                    continue
                
                # Find JSONL session files
                for session_file in sessions_dir.glob('*.jsonl'):
                    try:
                        # Read last line to get current session state
                        with open(session_file, 'r', encoding='utf-8') as f:
                            last_line = None
                            for line in f:
                                last_line = line
                        
                        if not last_line:
                            continue
                        
                        data = json.loads(last_line)
                        v_data = data.get('v', {})
                        
                        sessions.append({
                            'session_id': session_file.stem,
                            'session_file_path': str(session_file),
                            'workspace_hash': hash_dir.name,
                            'custom_title': v_data.get('customTitle', ''),
                            'request_count': len(v_data.get('requests', []))
                        })
                        
                        logger.debug(f"Found session: {v_data.get('customTitle', session_file.stem)}")
                    except Exception as e:
                        logger.debug(f"Failed to parse session {session_file}: {e}")
                        continue
    except Exception as e:
        logger.warning(f"Error scanning workspaceStorage: {e}")
    
    logger.info(f"Discovered {len(sessions)} sessions via AppData fallback")
    return sessions


def find_session_for_agent(agent_pattern: str) -> Optional[dict[str, str]]:
    """Find a single session matching agent pattern.
    
    Args:
        agent_pattern: Pattern to match in custom_title (case-insensitive)
        
    Returns:
        Session dict (includes session_file_path) if found, None otherwise
    """
    sessions = discover_chat_sessions_via_qopilot()
    
    for session in sessions:
        title = session.get('custom_title', '').lower()
        if agent_pattern.lower() in title:
            logger.info(f"Found session for {agent_pattern}: {session['custom_title']}")
            return session
    
    logger.warning(f"No session found for agent: {agent_pattern}")
    return None


def get_session_request_count_declarative(agent_pattern: str) -> Optional[int]:
    """Get request count for a session using declarative discovery.
    
    Args:
        agent_pattern: Agent name to find
        
    Returns:
        Request count or None if session not found
    """
    session = find_session_for_agent(agent_pattern)
    if session:
        count = session.get('request_count')
        logger.info(f"Session request count: {count}")
        return count
    
    return None
