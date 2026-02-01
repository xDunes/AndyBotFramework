"""
Configuration Loader - Handles master.conf and game-specific configs

This module manages loading and merging configuration from:
- master.conf: Global settings (devices, ADB, LDPlayer, etc.)
- games/<game>/<game>.conf: Game-specific settings (functions, commands, etc.)

Device configurations are merged, with game-specific settings overlaying master settings.
"""

import json
import os

# Cached configurations
_cached_master_config = None
_cached_game_config = None
_cached_merged_config = None
_current_game = None


def _get_project_root():
    """Get the project root directory"""
    return os.path.dirname(os.path.dirname(__file__))


def load_master_config():
    """Load master configuration from master.conf

    Returns:
        dict: Master configuration dictionary containing global settings

    Note:
        Uses global cache to avoid repeated file I/O operations.
    """
    global _cached_master_config
    if _cached_master_config is None:
        master_path = os.path.join(_get_project_root(), 'master.conf')
        if os.path.exists(master_path):
            with open(master_path, 'r', encoding='utf-8') as f:
                _cached_master_config = json.load(f)
        else:
            # Fallback to empty config if master.conf doesn't exist
            _cached_master_config = {}
    return _cached_master_config


def load_game_config(game_name):
    """Load game-specific configuration

    Args:
        game_name: Name of the game (folder in games/)

    Returns:
        dict: Game configuration dictionary

    Note:
        Looks for <game_name>.conf in project root
    """
    global _cached_game_config, _current_game

    # Return cached if same game
    if _cached_game_config is not None and _current_game == game_name:
        return _cached_game_config

    game_conf_path = os.path.join(
        _get_project_root(), f'{game_name}.conf'
    )

    if os.path.exists(game_conf_path):
        with open(game_conf_path, 'r', encoding='utf-8') as f:
            _cached_game_config = json.load(f)
    else:
        # Return empty config if no game config exists
        _cached_game_config = {}

    _current_game = game_name
    return _cached_game_config


def _merge_device_configs(master_devices, game_devices):
    """Merge device configurations from master and game configs

    Args:
        master_devices: Device dict from master.conf (email, serial, window, index)
        game_devices: Device dict from game.conf (game-specific settings)

    Returns:
        dict: Merged device configurations
    """
    merged = {}

    # Start with master devices
    for device_name, device_config in master_devices.items():
        merged[device_name] = dict(device_config)

    # Overlay game-specific device settings
    for device_name, game_config in game_devices.items():
        if device_name in merged:
            merged[device_name].update(game_config)
        else:
            # Device only in game config (unusual but allowed)
            merged[device_name] = dict(game_config)

    return merged


def load_config(game_name=None):
    """Load and merge master and game configurations

    Args:
        game_name: Optional game name. If None, returns master config only.
                   If provided, merges master with game-specific config.

    Returns:
        dict: Merged configuration dictionary

    Note:
        - Master config provides: LDPlayerPath, adb, screenshot, max_reconnect_attempts
        - Master devices provide: email, index, window, serial
        - Game config provides: app_name, app_title, app_package, function_layout,
                               commands, bot_settings, cooldowns, auto_uncheck
        - Game devices provide: game-specific settings (concerttarget, stadiumtarget, etc.)
    """
    global _cached_merged_config, _current_game

    # Return cached if available and same game
    if _cached_merged_config is not None and _current_game == game_name:
        return _cached_merged_config

    master = load_master_config()

    if game_name is None:
        _cached_merged_config = dict(master)
        _current_game = None
        return _cached_merged_config

    game = load_game_config(game_name)

    # Start with master config
    merged = dict(master)

    # Overlay game-specific settings (excluding devices - those get special handling)
    for key, value in game.items():
        if key != 'devices':
            merged[key] = value

    # Merge device configurations
    master_devices = master.get('devices', {})
    game_devices = game.get('devices', {})
    merged['devices'] = _merge_device_configs(master_devices, game_devices)

    _cached_merged_config = merged
    _current_game = game_name
    return merged


def reload_config(game_name=None):
    """Force reload configuration from disk

    Args:
        game_name: Optional game name for game-specific config

    Returns:
        dict: Fresh configuration dictionary
    """
    global _cached_master_config, _cached_game_config, _cached_merged_config, _current_game
    _cached_master_config = None
    _cached_game_config = None
    _cached_merged_config = None
    _current_game = None
    return load_config(game_name)


def get_device_config(user, game_name=None):
    """Get device configuration for a specific user

    Args:
        user (str): Username identifier from config
        game_name: Optional game name for merged config

    Returns:
        dict: Device configuration containing serial, targets, etc.

    Raises:
        KeyError: If user is not found in config
    """
    config = load_config(game_name)
    devices = config.get('devices', {})
    if user not in devices:
        raise KeyError(f"Unknown user: {user}")
    return devices[user]


def get_serial(user):
    """Get Android device serial number for a user

    Args:
        user (str): Username identifier from config

    Returns:
        str: ADB device serial number
    """
    # Serial is in master config, so no game_name needed
    master = load_master_config()
    devices = master.get('devices', {})
    if user not in devices:
        raise KeyError(f"Unknown user: {user}")
    return devices[user].get("serial", "")


def get_device_option(user, option, default=None, game_name=None):
    """Get a specific option from device configuration

    Args:
        user (str): Username identifier from config
        option (str): Option key to retrieve
        default: Default value if option not found
        game_name: Optional game name for game-specific options

    Returns:
        The option value or default
    """
    try:
        device_config = get_device_config(user, game_name)
        return device_config.get(option, default)
    except KeyError:
        return default


def get_available_devices():
    """Get list of available device names from master config

    Returns:
        list: Device names defined in master.conf
    """
    master = load_master_config()
    return list(master.get('devices', {}).keys())


def format_cooldown_time(seconds):
    """Format cooldown time in condensed format

    Args:
        seconds: Remaining seconds

    Returns:
        str: Formatted time - rounded to nearest minute until < 60s
             (e.g., "5m", "3m", "45s")
    """
    if seconds < 60:
        # Less than 1 minute - show seconds only
        return f"{int(seconds)}s"
    else:
        # 1 minute or more - round to nearest minute for space saving
        minutes = round(seconds / 60)
        return f"{minutes}m"
