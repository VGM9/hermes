"""HERMES Core - Session verification via AppData inspection."""

import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from pywinauto.uia_element_info import UIAElementInfo

logger = logging.getLogger(__name__)


class SessionNotFoundError(Exception):
    """Raised when session cannot be found in AppData."""
    pass


class SessionVerificationError(Exception):
    """Raised when session verification fails."""
    pass


def get_appdata_sessions_dirs() -> list[Path]:
    """Get list of all ChatSessions directories from AppData.
    
    Uses hermes_session_discovery which queries VSCode via qopilot when available,
    falls back to AppData scanning only if necessary.
    
    Returns:
        List of Path objects to session directories, empty list if none found
        
    Note:
        The actual discovery logic is in hermes_session_discovery module.
        This function is kept for backward compatibility.
    """
    import hermes_session_discovery
    
    sessions = hermes_session_discovery.discover_chat_sessions_via_qopilot()
    
    # Convert to Path objects for compatibility
    return [Path(s['workspace_path']) / 'User' / 'workspaceStorage' / s['workspace_hash'] / 'chatSessions' 
            for s in sessions]


def find_session_file(agent_pattern: str) -> Optional[Path]:
    """Find session JSON file matching agent pattern.
    
    Uses declarative session discovery (qopilot VSCode API when available).
    
    Args:
        agent_pattern: Pattern to match in customTitle
        
    Returns:
        Path to session file, or None if not found
    """
    import hermes_session_discovery
    
    session = hermes_session_discovery.find_session_for_agent(agent_pattern)
    if session and 'session_file_path' in session:
        session_path = Path(session['session_file_path'])
        if session_path.exists():
            logger.info(f"Found session file: {session_path.name}")
            return session_path
    
    return None


def get_session_request_count(agent_pattern: str) -> Optional[int]:
    """Get current request count from session for verification.
    
    Uses declarative discovery via qopilot when available.
    
    Args:
        agent_pattern: Agent name/pattern to find
        
    Returns:
        Request count, or None if session not found or parse fails
    """
    import hermes_session_discovery
    
    # Try declarative discovery first (via qopilot if available)
    count = hermes_session_discovery.get_session_request_count_declarative(agent_pattern)
    if count is not None:
        logger.info(f"Session request count: {count}")
        return count
    
    # Fallback to reading file directly if discovery returns None
    session_file = find_session_file(agent_pattern)
    if not session_file:
        logger.debug(f"Session file not found for {agent_pattern}")
        return None
    
    try:
        # Read last line (JSONL format)
        with open(session_file, 'r', encoding='utf-8') as f:
            last_line = None
            for line in f:
                last_line = line
        
        if not last_line:
            logger.warning(f"Session file is empty: {session_file}")
            return None
        
        data = json.loads(last_line)
        requests = data.get('v', {}).get('requests', [])
        count = len(requests)
        logger.info(f"Session request count: {count}")
        return count
    except Exception as e:
        logger.error(f"Failed to read session {session_file}: {e}")
        return None


def verify_message_delivery(
    agent_pattern: str,
    count_before: int,
    timeout_sec: float = 5.0,
    check_interval_sec: float = 0.5
) -> bool:
    """Verify message delivery by checking request count increase.
    
    Args:
        agent_pattern: Agent to check
        count_before: Request count before sending
        timeout_sec: Maximum time to wait (default: 5.0s)
        check_interval_sec: Interval between checks (default: 0.5s)
        
    Returns:
        True if request count increased, False if timeout
    """
    logger.info(f"Verifying delivery (timeout: {timeout_sec}s)...")
    start = time.time()
    
    while time.time() - start < timeout_sec:
        count_after = get_session_request_count(agent_pattern)
        
        if count_after and count_after > count_before:
            logger.info(f"✓ Verified: request count {count_before} -> {count_after}")
            return True
        
        time.sleep(check_interval_sec)
    
    logger.warning(f"Verification timeout ({timeout_sec}s) - message may not have delivered")
    return False


def get_sessions_in_workspace(workspace_hash: str) -> List[Dict[str, str]]:
    """List all chat sessions in a specific workspace.
    
    Args:
        workspace_hash: Workspace hash (directory name in workspaceStorage)
        
    Returns:
        List of dicts with session info: session_id, folder path, etc.
        Empty list if workspace not found or no sessions.
    """
    import hermes_config
    
    appdata_path = hermes_config.get_appdata_path()
    workspace_dir = appdata_path / workspace_hash / 'chatEditingSessions'
    
    sessions = []
    
    if not workspace_dir.exists():
        logger.debug(f"Workspace directory not found: {workspace_dir}")
        return []
    
    try:
        # List all session directories
        for session_dir in workspace_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_id = session_dir.name
            state_file = session_dir / 'state.json'
            
            # Try to read session state to get metadata
            title = None
            try:
                if state_file.exists():
                    with open(state_file, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                        # State file structure may have title/metadata
                        title = state.get('title', 'Unknown')
            except Exception as e:
                logger.debug(f"Cannot read state for {session_id}: {e}")
            
            sessions.append({
                'session_id': session_id,
                'workspace_hash': workspace_hash,
                'path': str(session_dir),
                'title': title or 'Untitled Session'
            })
            
            logger.debug(f"Found session: {session_id}")
        
        logger.info(f"Found {len(sessions)} session(s) in workspace {workspace_hash}")
        return sessions
    
    except Exception as e:
        logger.error(f"Error listing sessions in {workspace_hash}: {e}")
        return []


def get_current_window_sessions() -> List[Dict[str, str]]:
    """Get list of sessions in the currently focused VSCode window.
    
    Returns:
        List of session dicts for the focused window's workspace,
        or empty list if cannot determine focused window/workspace.
        
    Note:
        Returns sessions in the focused window's workspace if detectable.
        Uses window title heuristics to determine workspace.
    """
    import hermes_window_ops
    import hermes_config
    import hashlib
    
    # Get focused window
    focused = hermes_window_ops.get_focused_vscode_window()
    if not focused:
        logger.warning("No focused VSCode window found")
        return []
    
    window_title = focused['title']
    logger.info(f"Current window: {window_title[:70]}")
    
    # Try to extract workspace from title
    workspace_path = hermes_window_ops.get_window_workspace_path(window_title)
    if not workspace_path:
        logger.debug("Cannot extract workspace path from window title")
        # Try to find ALL sessions (less useful, but something)
        try:
            appdata = hermes_config.get_appdata_path()
            all_workspaces = []
            for ws_dir in appdata.iterdir():
                if ws_dir.is_dir():
                    sessions = get_sessions_in_workspace(ws_dir.name)
                    all_workspaces.extend(sessions)
            return all_workspaces
        except Exception as e:
            logger.error(f"Cannot enumerate workspaces: {e}")
            return []
    
    # Compute workspace hash
    try:
        hash_input = str(workspace_path).encode('utf-8')
        workspace_hash = hashlib.sha256(hash_input).hexdigest()[:32]
        logger.debug(f"Computed workspace hash: {workspace_hash}")
        
        # Get sessions in this workspace
        return get_sessions_in_workspace(workspace_hash)
    
    except Exception as e:
        logger.error(f"Error computing workspace hash: {e}")
        return []


def get_calling_session_by_modification() -> Optional[Dict[str, str]]:
    """Find the session that called this code by looking at file modification times.
    
    CRITICAL ARCHITECTURE: Don't rely on window focus.
    When a tool (run_in_terminal, etc.) executes, it modifies the session state.
    Find the MOST RECENTLY MODIFIED session - that's the one that called us.
    
    This is immune to window switching:
    - User runs command in Session A
    - Session A state file gets modified (timestamp updated)
    - Even if user switches to Window B, Session A has the newest timestamp
    - We find Session A by looking at file modification times, not UI focus
    
    Returns:
        Dict with session info {session_id, workspace_hash, path, title},
        or None if cannot determine (e.g., no sessions exist).
        
    Example:
        >>> session = get_calling_session_by_modification()
        >>> if session:
        ...     print(f"Code called from: {session['session_id']}")
        ...     print(f"In workspace: {session['workspace_hash']}")
    """
    import hermes_config
    import os
    
    logger.info("Scanning for recently modified session (execution artifact detection)")
    
    try:
        appdata = hermes_config.get_appdata_path()
        
        recent_sessions = []
        
        # Scan all workspaces
        for ws_dir in appdata.iterdir():
            if not ws_dir.is_dir():
                continue
            
            workspace_hash = ws_dir.name
            
            # Scan all sessions in this workspace
            sessions_dir = ws_dir / 'chatEditingSessions'
            if not sessions_dir.exists():
                continue
            
            for session_dir in sessions_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                
                session_id = session_dir.name
                state_file = session_dir / 'state.json'
                
                # Get modification time
                try:
                    if state_file.exists():
                        mtime = os.path.getmtime(state_file)
                        
                        # Try to read session title
                        title = 'Unknown'
                        try:
                            with open(state_file, 'r', encoding='utf-8') as f:
                                state = json.load(f)
                                title = state.get('title', 'Unknown')
                        except Exception:
                            pass
                        
                        recent_sessions.append({
                            'session_id': session_id,
                            'workspace_hash': workspace_hash,
                            'path': str(session_dir),
                            'title': title,
                            'mtime': mtime
                        })
                except Exception as e:
                    logger.debug(f"Cannot get mtime for {session_id}: {e}")
        
        if not recent_sessions:
            logger.warning("No sessions found in AppData")
            return None
        
        # Find most recently modified
        most_recent = max(recent_sessions, key=lambda s: s['mtime'])
        
        logger.info(f"Most recently modified session: {most_recent['session_id']}")
        logger.info(f"  Title: {most_recent['title']}")
        logger.info(f"  Workspace: {most_recent['workspace_hash']}")
        logger.info(f"  Modified: {time.ctime(most_recent['mtime'])}")
        
        # Return without mtime field
        return {
            'session_id': most_recent['session_id'],
            'workspace_hash': most_recent['workspace_hash'],
            'path': most_recent['path'],
            'title': most_recent['title']
        }
    
    except Exception as e:
        logger.error(f"Failed to find calling session: {e}")
        return None
