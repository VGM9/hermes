"""
Pure functions for parsing agent request text.

All functions are pure - same input always produces same output.
NO side effects, NO external dependencies except standard library.
"""

import re
import urllib.parse
from typing import List, Tuple

# ==============================================================================
# REGEX PATTERNS - Extracted from VSCode confirmation text format
# ==============================================================================

PATTERN_FILE_URI = r'file:///([^\)\s]+)'
"""Matches file:/// URIs in markdown link format [](file:///path)."""

PATTERN_TERMINAL_COMMAND = r'Ran terminal command:\s*(.+?)(?=\s+Read\s+|\s+Searched\s+|\s+Ran\s+|$)'
"""Matches terminal command text after 'Ran terminal command:' prefix."""

PATTERN_REQUEST_TYPE = r'required:\s*(.+?)\?'
"""Matches request type between 'required:' and '?'."""

# ==============================================================================
# TEXT PATTERNS - Common confirmation dialog text
# ==============================================================================

CONFIRMATION_TEXT_ALLOW_READING_EXTERNAL = 'Allow reading external directory'
"""Standard text for external directory read confirmations."""

CONFIRMATION_TEXT_ALLOW_DIRECTORY = 'Allow directory access'
"""Fallback text for directory access confirmations."""

# ==============================================================================
# PATH PATTERNS - For workspace/system path classification
# ==============================================================================

import os

SYSTEM_PATHS_WINDOWS = ['/windows/', '/system32/', '/program files/']
"""Windows system directories."""

SYSTEM_PATHS_UNIX = ['/bin/', '/usr/', '/etc/', '/dev/']
"""Unix/Linux system directories."""

SYSTEM_PATHS = SYSTEM_PATHS_WINDOWS if os.name == 'nt' else SYSTEM_PATHS_UNIX
"""OS-aware system paths."""

WORKSPACE_PATHS = ['/workspace/', '/projects/', '/vgm9/', '/www/']
"""Common workspace directory patterns."""

# ==============================================================================
# COMMAND SAFETY PATTERNS
# ==============================================================================

DANGEROUS_COMMAND_PATTERNS = [
    'rm -rf', 'del /f', 'format ', 'dd if=', 'mkfs',
    '> /dev/', 'chmod 777', 'chown root',
    'curl | bash', 'wget | sh',
]
"""Patterns indicating dangerous/destructive commands."""

MODERATE_COMMAND_PATTERNS = [
    '>', '>>', 'mv ', 'cp ', 'mkdir', 'touch ',
    'echo ', 'printf', 'sed -i', 'git commit',
]
"""Patterns indicating write operations (moderate risk)."""

READ_ONLY_REQUEST_PATTERNS = ['read', 'reading', 'view', 'search', 'grep', 'find']
"""Patterns indicating read-only operations (low risk)."""

# ==============================================================================
# DISPLAY CONSTANTS
# ==============================================================================

MAX_DISPLAY_TEXT_LENGTH = 500
"""Maximum length for truncating text in serialization."""


def extract_file_uris_from_text(text: str) -> List[str]:
    """
    Extract file:/// URIs from request text.
    
    Pure function - no side effects.
    
    Args:
        text: Full request text containing file:/// URIs
        
    Returns:
        List of URL-decoded file paths
        
    Example:
        >>> text = "Read [](file:///c%3A/Users/test/file.txt)"
        >>> extract_file_uris_from_text(text)
        ['c:/Users/test/file.txt']
    """
    if not text:
        return []
    
    matches = re.findall(PATTERN_FILE_URI, text)
    
    # URL decode each match and deduplicate
    seen = set()
    decoded_paths = []
    
    for match in matches:
        decoded = urllib.parse.unquote(match)
        if decoded not in seen:
            seen.add(decoded)
            decoded_paths.append(decoded)
    
    return decoded_paths


def extract_commands_from_text(text: str) -> List[str]:
    """
    Extract terminal commands from request text.
    
    Pure function - no side effects.
    
    Args:
        text: Full request text containing "Ran terminal command: <cmd>" patterns
        
    Returns:
        List of command strings
        
    Example:
        >>> text = "Ran terminal command: ls -la Read..."
        >>> extract_commands_from_text(text)
        ['ls -la']
    """
    if not text:
        return []
    
    matches = re.findall(PATTERN_TERMINAL_COMMAND, text, re.MULTILINE | re.DOTALL)
    
    # Clean up matches
    cleaned_commands = []
    for match in matches:
        # Remove trailing whitespace and line breaks
        cleaned = match.strip()
        if cleaned:
            cleaned_commands.append(cleaned)
    
    return cleaned_commands


def extract_request_type_from_text(text: str) -> str:
    """
    Extract the request type from confirmation text.
    
    Pure function - no side effects.
    
    Args:
        text: Full request text containing "required: <type>?" pattern
        
    Returns:
        Request type string, or "Unknown" if not found
        
    Example:
        >>> text = "Chat confirmation required: Allow reading external directory?"
        >>> extract_request_type_from_text(text)
        'Allow reading external directory'
    """
    if not text:
        return "Unknown"
    
    match = re.search(PATTERN_REQUEST_TYPE, text)
    
    if match:
        return match.group(1).strip()
    
    # Fallback: check for common patterns using module constants
    if CONFIRMATION_TEXT_ALLOW_READING_EXTERNAL in text:
        return CONFIRMATION_TEXT_ALLOW_READING_EXTERNAL
    elif 'Allow' in text and 'directory' in text:
        return CONFIRMATION_TEXT_ALLOW_DIRECTORY
    
    return "Unknown"


def count_file_operations(file_paths: List[str]) -> Tuple[int, int, int]:
    """
    Analyze file paths to count different workspace locations.
    
    Pure function - no side effects.
    
    Args:
        file_paths: List of file paths extracted from request
        
    Returns:
        Tuple of (workspace_files, external_files, system_files)
        
    Example:
        >>> paths = ['c:/workspace/file.txt', 'c:/Users/external/data.json']
        >>> count_file_operations(paths)
        (1, 1, 0)
    """
    workspace_count = 0
    external_count = 0
    system_count = 0
    
    for path in file_paths:
        path_lower = path.lower()
        
        # Check if system directory using module constant
        if any(sys_path in path_lower for sys_path in SYSTEM_PATHS):
            system_count += 1
        # Check if in typical workspace paths using module constant
        elif any(ws_path in path_lower for ws_path in WORKSPACE_PATHS):
            workspace_count += 1
        else:
            external_count += 1
    
    return (workspace_count, external_count, system_count)


def classify_command_safety(command: str) -> str:
    """
    Classify a command as safe, moderate, or dangerous.
    
    Pure function - no side effects.
    
    Args:
        command: Terminal command string
        
    Returns:
        Classification: 'safe', 'moderate', or 'dangerous'
        
    Example:
        >>> classify_command_safety("ls -la")
        'safe'
        >>> classify_command_safety("rm -rf /")
        'dangerous'
    """
    if not command:
        return 'safe'
    
    cmd_lower = command.lower()
    
    # Check dangerous patterns using module constant
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if pattern in cmd_lower:
            return 'dangerous'
    
    # Check moderate patterns using module constant
    for pattern in MODERATE_COMMAND_PATTERNS:
        if pattern in cmd_lower:
            return 'moderate'
    
    # Everything else is considered safe (read-only)
    return 'safe'


def parse_request_text(full_text: str) -> dict:
    """
    Parse complete request text and extract all structured data.
    
    Pure function - composes other pure functions.
    
    Args:
        full_text: Full text from confirmation ListItem
        
    Returns:
        Dictionary with all parsed data
        
    Example:
        >>> text = "Chat confirmation required: Allow reading external directory? Read [](file:///c:/test.txt)"
        >>> result = parse_request_text(text)
        >>> result['request_type']
        'Allow reading external directory'
    """
    return {
        'request_type': extract_request_type_from_text(full_text),
        'files': extract_file_uris_from_text(full_text),
        'commands': extract_commands_from_text(full_text),
        'file_counts': count_file_operations(extract_file_uris_from_text(full_text)),
        'command_safety': [classify_command_safety(cmd) for cmd in extract_commands_from_text(full_text)],
    }


if __name__ == '__main__':
    """
    Run doctests when module is executed directly.
    """
    import doctest
    doctest.testmod()
