"""HERMES Core - Session verification via AppData inspection."""

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SessionNotFoundError(Exception):
    """Raised when session cannot be found in AppData."""
    pass


class SessionVerificationError(Exception):
    """Raised when session verification fails."""
    pass


def get_appdata_sessions_dir(workspace_hashes: list[str]) -> Optional[list[Path]]:
    """Get list of valid ChatSessions directories from AppData.
    
    Args:
        workspace_hashes: List of workspace hash strings to check
        
    Returns:
        List of valid Path objects to session directories, or empty list if none found
    """
    appdata = Path.home() / 'AppData' / 'Roaming' / 'Code - Insiders' / 'User' / 'workspaceStorage'
    
    if not appdata.exists():
        logger.debug(f"AppData not found: {appdata}")
        return []
    
    valid_dirs = []
    for hash_str in workspace_hashes:
        sessions_dir = appdata / hash_str / 'chatSessions'
        if sessions_dir.exists():
            logger.debug(f"Found sessions directory: {sessions_dir}")
            valid_dirs.append(sessions_dir)
    
    return valid_dirs


def find_session_file(
    agent_pattern: str,
    workspace_hashes: list[str]
) -> Optional[Path]:
    """Find session JSON file matching agent pattern.
    
    Args:
        agent_pattern: Pattern to match in customTitle
        workspace_hashes: List of workspace hashes to search
        
    Returns:
        Path to session file, or None if not found
    """
    session_dirs = get_appdata_sessions_dir(workspace_hashes)
    
    for sessions_dir in session_dirs:
        try:
            for json_file in sessions_dir.glob('*.jsonl'):
                # Try reading as JSONL (one JSON object per line)
                last_line = None
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            last_line = line
                    
                    if last_line:
                        data = json.loads(last_line)
                        title = data.get('v', {}).get('customTitle', '')
                        if agent_pattern.lower() in title.lower():
                            logger.info(f"Found session file: {json_file.name}")
                            return json_file
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.debug(f"Failed to parse {json_file}: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Error scanning {sessions_dir}: {e}")
            continue
    
    return None


def get_session_request_count(
    agent_pattern: str,
    workspace_hashes: list[str]
) -> Optional[int]:
    """Get current request count from session for verification.
    
    Args:
        agent_pattern: Agent name/pattern to find
        workspace_hashes: List of workspace hashes to check
        
    Returns:
        Request count, or None if session not found or parse fails
    """
    session_file = find_session_file(agent_pattern, workspace_hashes)
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
    workspace_hashes: list[str],
    timeout_sec: float = 5.0,
    check_interval_sec: float = 0.5
) -> bool:
    """Verify message delivery by checking request count increase.
    
    Args:
        agent_pattern: Agent to check
        count_before: Request count before sending
        workspace_hashes: List of workspace hashes to check
        timeout_sec: Maximum time to wait (default: 5.0s)
        check_interval_sec: Interval between checks (default: 0.5s)
        
    Returns:
        True if request count increased, False if timeout
    """
    logger.info(f"Verifying delivery (timeout: {timeout_sec}s)...")
    start = time.time()
    
    while time.time() - start < timeout_sec:
        count_after = get_session_request_count(agent_pattern, workspace_hashes)
        
        if count_after and count_after > count_before:
            logger.info(f"✓ Verified: request count {count_before} -> {count_after}")
            return True
        
        time.sleep(check_interval_sec)
    
    logger.warning(f"Verification timeout ({timeout_sec}s) - message may not have delivered")
    return False
