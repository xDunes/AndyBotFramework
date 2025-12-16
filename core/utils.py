"""
Core Utilities - Generic helper functions

This module provides utility functions used across the bot framework.
All logging functionality is centralized here.
"""

from datetime import datetime

# Global references for logging
_gui_instance = None
_state_manager = None
_log_db = None
_debug_enabled = None  # Callable that returns bool
_headless_mode = False  # If True, log to console; if False, only log to GUI/web


def set_gui_instance(gui):
    """Set the global GUI instance for logging

    Args:
        gui: BotGUI instance to use for logging
    """
    global _gui_instance
    _gui_instance = gui


def get_gui_instance():
    """Get the current GUI instance

    Returns:
        BotGUI instance or None
    """
    return _gui_instance


def set_state_manager(state_manager):
    """Set the state manager for web interface logging

    Args:
        state_manager: StateManager instance
    """
    global _state_manager
    _state_manager = state_manager


def set_log_db(log_db, debug_enabled_func):
    """Set the debug log database

    Args:
        log_db: LogDatabase instance
        debug_enabled_func: Callable that returns True if debug is enabled
    """
    global _log_db, _debug_enabled
    _log_db = log_db
    _debug_enabled = debug_enabled_func


def set_headless_mode(enabled):
    """Set headless mode for console logging

    When headless mode is enabled, logs are printed to console with timestamps.
    When disabled (default), logs only go to GUI and web interface.

    Args:
        enabled: True to enable console logging, False to disable
    """
    global _headless_mode
    _headless_mode = enabled


def is_headless():
    """Check if running in headless mode

    Returns:
        True if headless mode is enabled
    """
    return _headless_mode


def log(message, screenshot=None):
    """Log message to all configured destinations

    This is the central logging function. Game-specific functions should
    call this to log messages. It handles:
    - GUI display (if available)
    - Web interface via state_manager (if available)
    - Debug database (if debug mode enabled)
    - Console output (only in headless mode)

    Args:
        message: Message string to log
        screenshot: Optional screenshot image to associate with log entry
    """
    global _gui_instance, _state_manager, _log_db, _debug_enabled, _headless_mode

    # Log to GUI display - use gui.log() method if available (enables callbacks)
    if _gui_instance:
        if hasattr(_gui_instance, 'log') and callable(_gui_instance.log):
            # Use the GUI's log method (HeadlessBot or BotGUI)
            # This enables WebSocket callbacks in headless mode
            _gui_instance.log(message, screenshot)
        else:
            # Fallback: direct buffer manipulation
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            _gui_instance.log_buffer.append(formatted_message)

            # Maintain buffer size
            while len(_gui_instance.log_buffer) > _gui_instance.max_log_lines:
                _gui_instance.log_buffer.pop(0)

            # Update log widget (thread-safe)
            if hasattr(_gui_instance, 'root') and hasattr(_gui_instance, '_update_log_widget'):
                _gui_instance.root.after(0, _gui_instance._update_log_widget)

            # Log to console only in headless mode
            if _headless_mode:
                print(formatted_message)

            # Log to state manager for web interface
            if _state_manager:
                _state_manager.add_log(message, screenshot)
    else:
        # No GUI - log to console in headless mode
        if _headless_mode:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
            print(formatted_message)

        # Log to state manager for web interface
        if _state_manager:
            _state_manager.add_log(message, screenshot)

    # Log to debug database if enabled
    if _log_db and _debug_enabled and _debug_enabled():
        _log_db.add_log_entry(message, screenshot)


def camel_to_snake(name):
    """Convert camelCase to snake_case

    Args:
        name: String in camelCase (e.g., "doConcert")

    Returns:
        String in snake_case (e.g., "do_concert")

    Examples:
        >>> camel_to_snake("doConcert")
        'do_concert'
        >>> camel_to_snake("doStreet")
        'do_street'
        >>> camel_to_snake("getActiveRallyInfo")
        'get_active_rally_info'
    """
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append('_')
        result.append(char.lower())
    return ''.join(result)


def snake_to_camel(name):
    """Convert snake_case to camelCase

    Args:
        name: String in snake_case (e.g., "do_concert")

    Returns:
        String in camelCase (e.g., "doConcert")

    Examples:
        >>> snake_to_camel("do_concert")
        'doConcert'
        >>> snake_to_camel("do_street")
        'doStreet'
    """
    parts = name.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])


def build_function_map(config, functions_module):
    """Build FUNCTION_MAP dynamically from config.json function_layout

    This function reads the function_layout from config and maps each
    function name to its implementation in the functions module.

    Args:
        config: Configuration dictionary with 'function_layout' key
        functions_module: Module containing function implementations

    Returns:
        dict: Mapping of config function names to callable functions
              e.g., {"doConcert": <function do_concert>, ...}

    Note:
        - Config uses camelCase (e.g., "doConcert")
        - Python functions use snake_case (e.g., "do_concert")
        - Functions not found in module are skipped with a warning
    """
    function_map = {}

    for row in config.get('function_layout', []):
        for func_name in row:
            # Convert camelCase config name to snake_case Python name
            snake_name = camel_to_snake(func_name)

            # Get function from module if it exists
            if hasattr(functions_module, snake_name):
                function_map[func_name] = getattr(functions_module, snake_name)
            else:
                log(f"[Warning] Function '{snake_name}' not found in functions module")

    return function_map


def build_command_map(config, commands_module):
    """Build COMMAND_HANDLERS dynamically from config.json commands

    This function reads the commands from config and maps each
    command ID to its handler function in the commands module.

    Args:
        config: Configuration dictionary with 'commands' key
        commands_module: Module containing command handler implementations

    Returns:
        dict: Mapping of command IDs to handler functions
              e.g., {"min_fans": <function handle_min_fans>, ...}

    Note:
        - Config uses snake_case IDs (e.g., "min_fans")
        - Python handlers use handle_ prefix (e.g., "handle_min_fans")
        - Handlers not found in module are skipped with a warning
        - 'start_stop' command is skipped (handled by GUI)
    """
    command_map = {}

    for command in config.get('commands', []):
        command_id = command.get('id', '')

        # Skip start_stop - it's handled separately by the GUI
        if not command_id or command_id == 'start_stop':
            continue

        # Build handler function name
        handler_name = f"handle_{command_id}"

        # Get handler from module if it exists
        if hasattr(commands_module, handler_name):
            command_map[command_id] = getattr(commands_module, handler_name)
        else:
            log(f"[Warning] Command handler '{handler_name}' not found in commands module")

    return command_map
