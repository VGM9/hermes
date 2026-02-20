# -*- coding: utf-8 -*-
"""HERMES Config - Load and manage configuration from files and environment."""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Default workspace hashes (fallback)
DEFAULT_WORKSPACE_HASHES = [
    'fc7deee2819a0e3e3f792481dedcbc98',
    '68569d2de19d99c3fa1fe1eceaa8b90c',
    '8748b265d5d0df6fdc9d9cd506a6807f',  # ARGUS0.QuestMaster
]


class ConfigError(Exception):
    """Raised when configuration loading fails."""
    pass


def load_workspace_hashes(config_path: Optional[Path] = None) -> list[str]:
    """Load workspace hashes from config file, environment, or defaults.
    
    Priority order:
    1. HERMES_WORKSPACE_HASHES environment variable (comma-separated)
    2. hermes.config.yaml file in current directory
    3. hermes.config.yaml file in parent directories (up to home)
    4. Default list
    
    Args:
        config_path: Explicit path to config file (overrides search)
        
    Returns:
        List of workspace hash strings
        
    Raises:
        ConfigError: If provided config_path does not exist
    """
    # Check environment variable first
    env_hashes = os.getenv('HERMES_WORKSPACE_HASHES')
    if env_hashes:
        hashes = [h.strip() for h in env_hashes.split(',') if h.strip()]
        if hashes:
            logger.info(f"Loaded {len(hashes)} workspace hashes from HERMES_WORKSPACE_HASHES env var")
            return hashes
    
    # Check explicit config path
    if config_path:
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        return _load_yaml_config(config_path)
    
    # Search for config file
    search_path = Path.cwd()
    home = Path.home()
    
    while search_path >= home:
        config_file = search_path / 'hermes.config.yaml'
        if config_file.exists():
            logger.info(f"Found config file: {config_file}")
            return _load_yaml_config(config_file)
        
        parent = search_path.parent
        if parent == search_path:  # Reached root
            break
        search_path = parent
    
    # Fallback to defaults
    logger.info(f"Using default workspace hashes ({len(DEFAULT_WORKSPACE_HASHES)} hashes)")
    return DEFAULT_WORKSPACE_HASHES


def _load_yaml_config(config_path: Path) -> list[str]:
    """Load workspace hashes from YAML config file.
    
    Args:
        config_path: Path to hermes.config.yaml file
        
    Returns:
        List of workspace hashes
        
    Raises:
        ConfigError: If YAML parsing fails or workspace_hashes not found
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; cannot parse config file. Using defaults.")
        return DEFAULT_WORKSPACE_HASHES
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config or not isinstance(config, dict):
            logger.warning(f"Config file is empty or invalid: {config_path}")
            return DEFAULT_WORKSPACE_HASHES
        
        hashes = config.get('workspace_hashes', [])
        if not hashes:
            logger.warning(f"No 'workspace_hashes' key in config: {config_path}")
            return DEFAULT_WORKSPACE_HASHES
        
        logger.info(f"Loaded {len(hashes)} workspace hashes from config: {config_path}")
        return hashes
    except Exception as e:
        logger.error(f"Failed to parse config file {config_path}: {e}")
        raise ConfigError(f"Cannot parse config: {e}") from e


def get_appdata_path() -> Path:
    """Get platform-specific AppData/config path for VSCode Insiders.
    
    Returns:
        Path to workspaceStorage directory
        
    Note:
        - Windows: %APPDATA%/Code - Insiders/User/workspaceStorage
        - macOS: ~/Library/Application Support/Code - Insiders/User/workspaceStorage  
        - Linux: ~/.config/Code - Insiders/User/workspaceStorage
    """
    import platform
    
    system = platform.system()
    
    if system == "Windows":
        appdata = Path.home() / 'AppData' / 'Roaming' / 'Code - Insiders' / 'User' / 'workspaceStorage'
    elif system == "Darwin":  # macOS
        appdata = Path.home() / 'Library' / 'Application Support' / 'Code - Insiders' / 'User' / 'workspaceStorage'
    else:  # Linux and other Unix-like
        appdata = Path.home() / '.config' / 'Code - Insiders' / 'User' / 'workspaceStorage'
    
    logger.debug(f"VSCode Insiders AppData path ({system}): {appdata}")
    return appdata
