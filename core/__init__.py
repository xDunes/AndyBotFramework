"""
Core Framework Module - Generic bot infrastructure

This module provides the generic framework for game bots:
- BOT class for image recognition and device control
- Android class for ADB device communication
- Bot loop execution
- Configuration loading
- OCR utilities

All components are game-agnostic and can be reused for any game.
"""

# Re-export core classes from existing modules
from .bot import BOT, BotStoppedException
from .android import Android, AndroidStoppedException, ADBTimeoutError
from .state_manager import StateManager
from .log_database import LogDatabase, get_available_devices, clear_all_devices_logs
from .ldplayer import LDPlayer, launch_devices_if_needed

# Export core utilities
from .config_loader import (
    load_config,
    load_master_config,
    load_game_config,
    reload_config,
    get_device_config,
    get_serial,
    get_device_option,
    get_available_devices as get_available_devices_config,
    format_cooldown_time
)

from .ocr import (
    extract_ratio_from_image,
    RATIO_PATTERN,
    RATIO_PATTERN_FLEXIBLE,
    LEVEL_PATTERN,
    NUMBER_SLASH_PATTERN
)

from .bot_loop import run_bot_loop
from .bot_controller import BotController

from .utils import (
    log,
    set_gui_instance,
    set_state_manager,
    set_log_db,
    set_headless_mode,
    is_headless,
    build_function_map,
    build_command_map
)

__all__ = [
    # Classes
    'BOT',
    'BotStoppedException',
    'Android',
    'AndroidStoppedException',
    'ADBTimeoutError',
    'StateManager',
    'LogDatabase',
    'get_available_devices',
    'clear_all_devices_logs',
    'LDPlayer',
    'launch_devices_if_needed',

    # Config
    'load_config',
    'load_master_config',
    'load_game_config',
    'reload_config',
    'get_device_config',
    'get_serial',
    'get_device_option',
    'get_available_devices_config',
    'format_cooldown_time',

    # OCR
    'extract_ratio_from_image',
    'RATIO_PATTERN',
    'RATIO_PATTERN_FLEXIBLE',
    'LEVEL_PATTERN',
    'NUMBER_SLASH_PATTERN',

    # Bot loop and controller
    'run_bot_loop',
    'BotController',

    # Utils
    'log',
    'set_gui_instance',
    'set_state_manager',
    'set_log_db',
    'set_headless_mode',
    'is_headless',
    'build_function_map',
    'build_command_map',
]
