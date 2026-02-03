"""HERMES Core - Session verification via AppData inspection."""

import json
import logging
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

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
