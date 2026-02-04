"""HERMES Nonce-Based Session Verification - Deterministic caller identification.

This module provides nonce-based session identification to solve race conditions.
When you call run_in_terminal with a nonce embedded in the command, this module
can find which session made that call by searching for the nonce in session files.

USAGE:
    nonce = "HERMES_NONCE_abc123xyz"
    # Pass this nonce to your tool call:
    # run_in_terminal(command=f"echo {nonce} && ls")
    
    # Later, find the session:
    session = verify_session_by_nonce(nonce)
    if session:
        print(f"Found! Session ID: {session['session_id']}")
    else:
        print("Not found or validation failed")

Without a nonce, use the race-condition-prone mtime method and get a warning.
With a nonce, this module validates deterministically using thinking traces.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Tuple
import warnings

logger = logging.getLogger(__name__)


class NonceVerificationWarning(UserWarning):
    """Warning issued when nonce validation is recommended."""
    pass


class NonceNotFoundError(Exception):
    """Raised when nonce cannot be found in any session file."""
    pass


def find_session_by_modification_with_warning() -> Optional[Dict[str, str]]:
    """Find session by mtime (file modification time) - WITH RACE CONDITION WARNING.
    
    This method is NOT reliable when multiple agents/tools execute simultaneously.
    Each will modify session files within milliseconds, making mtime detection
    ambiguous.
    
    You should ALWAYS use find_session_by_nonce() instead.
    
    Returns:
        Session info dict, or None if cannot determine.
        
    Example:
        >>> # BAD - use this only if you have no nonce
        >>> session = find_session_by_modification_with_warning()
        >>> # GOOD - use this instead
        >>> session = find_session_by_nonce("YOUR_NONCE_HERE")
    """
    warnings.warn(
        "[WARNING] Using file modification time to find session. "
        "THIS IS UNRELIABLE when multiple agents run concurrently! "
        "Race conditions can cause incorrect session identification. "
        "Use find_session_by_nonce(nonce) instead.",
        NonceVerificationWarning,
        stacklevel=2
    )
    
    logger.warning("[RACE CONDITION RISK] file modification time detection enabled")
    logger.warning("    Consider passing a nonce for deterministic verification")
    
    # Fall back to the mtime-based method from hermes_session_verify
    import hermes_session_verify
    result = hermes_session_verify.get_calling_session_by_modification()
    
    if result:
        # Normalize keys to match find_session_by_nonce() return format
        # hermes_session_verify returns: session_id, workspace_hash, path, title, mtime
        # We return: session_id, workspace_hash, session_file, validation_method
        return {
            'session_id': result.get('session_id'),
            'workspace_hash': result.get('workspace_hash'),
            'session_file': result.get('path'),  # Map 'path' to 'session_file'
            'validation_method': 'mtime ([UNRELIABLE])'
        }
    
    return None


def _search_session_files_for_nonce(
    nonce: str,
    check_thinking: bool = True,
    check_tool_metadata: bool = True,
    timeout_sec: float = 10.0
) -> Tuple[Optional[Dict[str, str]], str]:
    """Internal: Search all session files for nonce, return session and where found.
    
    Args:
        nonce: The nonce to search for
        check_thinking: Include thinking traces in search (fastest)
        check_tool_metadata: Include tool invocation metadata
        timeout_sec: Time limit for search
        
    Returns:
        Tuple of (session_info_dict, location_description)
        or (None, "") if not found
    """
    import hermes_config
    
    start_time = time.time()
    
    try:
        appdata = hermes_config.get_appdata_path()
    except Exception as e:
        logger.error(f"Cannot get AppData path: {e}")
        return None, ""
    
    # Scan all workspace hashes
    for ws_hash_dir in appdata.iterdir():
        if not ws_hash_dir.is_dir():
            continue
        
        workspace_hash = ws_hash_dir.name
        sessions_dir = ws_hash_dir / 'chatSessions'
        
        if not sessions_dir.exists():
            continue
        
        # Check all session files
        for session_file_path in sessions_dir.iterdir():
            if not session_file_path.name.endswith('.jsonl'):
                continue
            
            # Check timeout
            if time.time() - start_time > timeout_sec:
                logger.warning(f"Nonce search timed out after {timeout_sec}s")
                return None, ""
            
            try:
                with open(session_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    all_lines = f.readlines()
                    
                    # Get session ID from last line (full state)
                    session_id = None
                    for line in reversed(all_lines):
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if 'v' in data and isinstance(data['v'], dict) and 'sessionId' in data['v']:
                                session_id = data['v']['sessionId']
                                break
                        except:
                            pass
                    
                    # Now search all lines for the nonce
                    for line in all_lines:
                        if nonce not in line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            
                            # Check thinking traces (fastest path)
                            if check_thinking and 'v' in data:
                                v = data['v']
                                
                                # If v is a list, check for thinking items
                                if isinstance(v, list):
                                    for item in v:
                                        if item.get('kind') == 'thinking':
                                            value = item.get('value', '')
                                            if nonce in value:
                                                return {
                                                    'session_id': session_id,
                                                    'workspace_hash': workspace_hash,
                                                    'session_file': session_file_path.name,
                                                }, "thinking trace (FAST)"
                                        
                                        # Check tool invocations
                                        elif check_tool_metadata and item.get('toolId') == 'run_in_terminal':
                                            cmd = item.get('toolSpecificData', {}).get(
                                                'commandLine', {}
                                            ).get('original', '')
                                            if nonce in cmd:
                                                return {
                                                    'session_id': session_id,
                                                    'workspace_hash': workspace_hash,
                                                    'session_file': session_file_path.name,
                                                }, "tool invocation metadata"
                        
                        except json.JSONDecodeError:
                            # Skip malformed JSON lines
                            continue
                        except Exception as e:
                            logger.debug(f"Error parsing line in {session_file_path.name}: {e}")
                            
            except (IOError, OSError) as e:
                logger.debug(f"Cannot read session file {session_file_path.name}: {e}")
                continue
    
    return None, ""


def _extract_session_id(data: dict) -> Optional[str]:
    """Extract session ID from a JSON line (works for both full and partial updates)."""
    # Attempt to get from various locations
    if 'v' in data and isinstance(data['v'], dict):
        return data['v'].get('sessionId')
    
    if 'v' in data and isinstance(data['v'], list):
        # For response arrays, we need to look at parent context
        # This is a fallback - the key path might have it
        if 'k' in data:
            keys = data['k']
            if len(keys) >= 2 and keys[0] == 'requests':
                # We're in a request, but we don't have session_id directly
                # It should be in the full line somewhere
                return None
    
    return None


def find_session_by_nonce(
    nonce: str,
    prefer_thinking: bool = True,
    timeout_sec: float = 10.0
) -> Optional[Dict[str, str]]:
    """Find which session called you by searching for a nonce in session files.
    
    The nonce you pass here MUST be embedded in the command you passed to run_in_terminal.
    This function searches all session files for that exact nonce, validates it was
    used by your tool call, and returns the matching session info.
    
    This is 100% race-condition-safe: even if multiple agents execute simultaneously,
    each has a unique nonce, so identification is deterministic.
    
    Args:
        nonce: The unique string you generated and passed to run_in_terminal.
               Format suggestion: "HERMES_NONCE_<random>"
        prefer_thinking: Prefer searching thinking traces first (faster, gets written immediately)
        timeout_sec: Maximum time to spend searching (default: 10.0s)
        
    Returns:
        Dict with session info:
            {
                'session_id': 'uuid-of-session',
                'workspace_hash': 'hash-of-workspace-path',
                'session_file': 'uuid.jsonl',
                'validation_method': 'thinking trace' | 'tool metadata'
            }
        Or None if nonce not found.
        
    Raises:
        NonceNotFoundError: If nonce is not found after timeout
        
    Example:
        >>> nonce = "HERMES_NONCE_x7k2j9mw"
        >>> run_in_terminal(command=f"echo {nonce} && pwd")
        >>> time.sleep(0.5)  # Wait for serialization
        >>> session = find_session_by_nonce(nonce)
        >>> if session:
        ...     print(f"Session: {session['session_id']}")
        ...     print(f"Found in: {session['validation_method']}")
    """
    logger.info(f"Searching for nonce: {nonce}")
    logger.info(f"  Search timeout: {timeout_sec}s")
    if prefer_thinking:
        logger.info(f"  Will prefer thinking traces (fastest)")
    
    start = time.time()
    
    # First search: thinking traces (fastest)
    if prefer_thinking:
        session, location = _search_session_files_for_nonce(
            nonce,
            check_thinking=True,
            check_tool_metadata=False,
            timeout_sec=timeout_sec
        )
        
        if session:
            elapsed = time.time() - start
            logger.info(f"[OK] FOUND in {location} ({elapsed:.2f}s)")
            session['validation_method'] = location
            return session
    
    # Second search: tool metadata
    session, location = _search_session_files_for_nonce(
        nonce,
        check_thinking=False,
        check_tool_metadata=True,
        timeout_sec=timeout_sec - (time.time() - start)
    )
    
    if session:
        elapsed = time.time() - start
        logger.info(f"[OK] FOUND in {location} ({elapsed:.2f}s)")
        session['validation_method'] = location
        return session
    
    # Not found
    elapsed = time.time() - start
    logger.error(f"[NOTFOUND] Nonce NOT FOUND after {elapsed:.2f}s")
    raise NonceNotFoundError(
        f"Nonce '{nonce}' not found in any session file. "
        f"Did you embed it in your run_in_terminal command? "
        f"Wait time: {elapsed:.2f}s"
    )


def get_session_info(nonce: Optional[str] = None) -> Dict[str, str]:
    """Get session info using nonce (preferred) or mtime (with warning).
    
    This is the high-level API you should use in your scripts.
    Pass a nonce for reliable identification, or None to use race-prone mtime.
    
    Args:
        nonce: Optional nonce to validate. If None, uses mtime (with warning).
        
    Returns:
        Session info dict with keys:
        - session_id: UUID of the chat session
        - workspace_hash: Hash of workspace path
        - session_file: Filename of session JSONL
        - validation_method: How it was found ("nonce:<location>" or "mtime")
        
    Example:
        >>> # GOOD: with nonce
        >>> nonce = "HERMES_NONCE_abc123"
        >>> # pass to tool call...
        >>> session = get_session_info(nonce=nonce)
        >>>
        >>> # LESS GOOD: without nonce (gets warning)
        >>> session = get_session_info()
    """
    if nonce:
        try:
            session = find_session_by_nonce(nonce)
            session['validation_method'] = f"nonce:{session.get('validation_method', 'unknown')}"
            return session
        except NonceNotFoundError as e:
            logger.error(str(e))
            raise
    else:
        session = find_session_by_modification_with_warning()
        if session:
            return session
        else:
            raise RuntimeError("Cannot determine calling session")


# CLI interface
if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Find which VSCode session called you via nonce validation',
        epilog='Use with a nonce for 100% reliable identification, without for race-prone mtime detection'
    )
    parser.add_argument('--nonce', type=str, help='Nonce to search for (recommended)')
    parser.add_argument('--timeout', type=float, default=10.0, help='Search timeout in seconds')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    try:
        session = get_session_info(nonce=args.nonce)
        
        if args.json:
            print(json.dumps(session, indent=2))
        else:
            print(f"[OK] Session found:")
            print(f"  ID: {session['session_id']}")
            print(f"  Workspace: {session['workspace_hash']}")
            print(f"  File: {session['session_file']}")
            print(f"  Validation: {session['validation_method']}")
        
        sys.exit(0)
    
    except NonceNotFoundError as e:
        print(f"[ERROR] Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
