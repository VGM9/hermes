#!/usr/bin/env python3
"""
Session ID to Window Mapper for HERMES
Maps VSCode session IDs to window handles for reliable messaging.
"""

import os
import json
import glob
from pathlib import Path
from pywinauto import Desktop
from typing import Optional, Dict, Tuple, List


def get_vscode_appdata() -> Path:
    """Get VSCode Insiders AppData path"""
    return Path(os.environ["APPDATA"]) / "Code - Insiders" / "User"


def get_all_workspace_hashes() -> List[str]:
    """Get all workspace storage hashes"""
    storage_path = get_vscode_appdata() / "workspaceStorage"
    if not storage_path.exists():
        return []
    
    return [d.name for d in storage_path.iterdir() if d.is_dir()]


def find_session_workspace(session_id: str) -> Optional[Tuple[str, Path]]:
    """
    Find which workspace hash contains the given session ID.
    
    Returns:
        (workspace_hash, session_file_path) or None
    """
    hashes = get_all_workspace_hashes()
    
    for workspace_hash in hashes:
        sessions_dir = get_vscode_appdata() / "workspaceStorage" / workspace_hash / "chatSessions"
        if not sessions_dir.exists():
            continue
        
        # Look for session file starting with session_id
        pattern = str(sessions_dir / f"{session_id}*.jsonl")
        matches = glob.glob(pattern)
        
        if matches:
            return (workspace_hash, Path(matches[0]))
    
    return None


def read_workspace_config(workspace_hash: str) -> Optional[Dict]:
    """
    Read workspace.json to get config including folder paths.
    
    Returns:
        Workspace config dict or None
    """
    config_path = get_vscode_appdata() / "workspaceStorage" / workspace_hash / "workspace.json"
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def get_workspace_identifier(workspace_hash: str) -> Optional[str]:
    """
    Get a unique identifier for the workspace from its config.
    Could be workspace name, folder path, or URI.
    
    Returns:
        String that might appear in window title, or None
    """
    config = read_workspace_config(workspace_hash)
    if not config:
        return None
    
    # Try to extract workspace identifier
    # Workspace config has: folder (URI), workspace (if .code-workspace), etc.
    if 'workspace' in config:
        # Multi-root workspace (.code-workspace file)
        workspace_uri = config['workspace']
        # Extract filename from URI: file:///c:/path/to/name.code-workspace
        if 'file:///' in workspace_uri:
            path_part = workspace_uri.split('file:///')[-1]
            # Decode URI escapes and get filename
            from urllib.parse import unquote
            decoded = unquote(path_part)
            name = Path(decoded).stem  # Get filename without extension
            return name
    
    elif 'folder' in config:
        # Single-folder workspace
        folder_uri = config['folder']
        if 'file:///' in folder_uri:
            path_part = folder_uri.split('file:///')[-1]
            from urllib.parse import unquote
            decoded = unquote(path_part)
            name = Path(decoded).name  # Get last folder name
            return name
    
    return None


def find_vscode_windows() -> List[Tuple[any, str]]:
    """
    Find all VSCode Insiders windows.
    
    Returns:
        List of (window_handle, title) tuples
    """
    desktop = Desktop(backend="uia")
    windows = []
    
    # Find all Chrome_WidgetWin_1 windows (VSCode Electron app)
    for window in desktop.windows():
        try:
            class_name = window.class_name()
            if class_name == "Chrome_WidgetWin_1":
                title = window.window_text()
                if "Visual Studio Code" in title and "Insiders" in title:
                    windows.append((window, title))
        except:
            continue
    
    return windows


def find_window_by_session_id(session_id: str) -> Optional[Tuple[any, str]]:
    """
    Find VSCode window handle for a given session ID.
    
    Algorithm:
    1. Find which workspace hash contains the session
    2. Get workspace identifier from workspace.json
    3. Search VSCode windows for title containing identifier
    
    Returns:
        (window_handle, title) or None
    """
    # Find session's workspace
    result = find_session_workspace(session_id)
    if not result:
        print(f"✗ Session {session_id} not found in any workspace")
        return None
    
    workspace_hash, session_file = result
    print(f"✓ Found session in workspace {workspace_hash}")
    print(f"  Session file: {session_file.name}")
    
    # Get workspace identifier
    identifier = get_workspace_identifier(workspace_hash)
    if not identifier:
        print(f"⚠ Could not determine workspace identifier for {workspace_hash}")
        return None
    
    print(f"  Workspace identifier: {identifier}")
    
    # Find matching VSCode window
    vscode_windows = find_vscode_windows()
    print(f"  Found {len(vscode_windows)} VSCode windows")
    
    for window, title in vscode_windows:
        if identifier.lower() in title.lower():
            print(f"✓ Matched window: {title}")
            return (window, title)
    
    print(f"✗ No window found with identifier '{identifier}' in title")
    print(f"  Available windows:")
    for _, title in vscode_windows:
        print(f"    - {title}")
    
    return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hermes_session_mapper.py <session_id>")
        print("\nExample:")
        print("  python hermes_session_mapper.py 627004f9-d8cf-435d-95d9-5382aef48240")
        sys.exit(1)
    
    session_id = sys.argv[1]
    
    # Support partial session IDs (just the first part)
    if len(session_id) < 36:
        print(f"Partial session ID provided: {session_id}")
        print("Searching for full session ID...\n")
    
    result = find_window_by_session_id(session_id)
    
    if result:
        window, title = result
        print(f"\n✓ SUCCESS: Found window for session {session_id}")
        print(f"  Title: {title}")
    else:
        print(f"\n✗ FAILED: Could not find window for session {session_id}")
        sys.exit(1)
