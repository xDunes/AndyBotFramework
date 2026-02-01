"""
Master of Bots - Centralized headless bot manager with integrated web server

This script manages multiple bot instances in a single process with integrated
Flask web interface. All state is stored in-memory for instant access with no
database lag.

Architecture:
- HeadlessBot instances run in separate threads
- Flask web server with direct in-memory state access
- WebSocket streaming for real-time updates
- No database relay - all commands and queries are instant

Key features:
- Direct in-memory state access (< 1ms state queries)
- Instant command execution (< 100ms)
- Real-time screenshot streaming
- Multi-device dashboard at http://localhost:5000
- Mobile-friendly web interface

Comparison with start_bot.py:
- start_bot.py: Single bot, Tkinter GUI, local only
- master_of_bots.py: Multi-bot, headless, web interface

Usage:
    python master_of_bots.py <game_name> [options]

Examples:
    python master_of_bots.py apex_girl
    python master_of_bots.py apex_girl --port 5001
    python master_of_bots.py apex_girl --devices Gelvil,Gelvil1
    python master_of_bots.py apex_girl --no-auto-start-bot
    python master_of_bots.py apex_girl --no-auto-start-device
    python master_of_bots.py apex_girl --no-web

Options:
    game_name               Required. Game module name (folder in games/)
    --port PORT             Web server port (default: 5000)
    --devices DEVICES       Comma-separated list of devices to manage (default: all)
    --no-auto-start-bot     Disable auto-starting all bots on launch
    --no-auto-start-device  Disable auto-launching LDPlayer devices
    --no-web                Disable web server (CLI-only mode)
"""

import sys
import os
import argparse
import importlib
import threading
import time
import signal
import subprocess
import base64
import queue
from datetime import datetime
from typing import Dict, Optional, Callable, Any, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Core imports
from core.bot import BOT, BotStoppedException
from core.android import Android, AndroidStoppedException
from core.config_loader import load_config, load_master_config, get_serial
from core.ldplayer import LDPlayer, launch_devices_if_needed
from core.utils import build_function_map, build_command_map
from core.log_database import LogDatabase, get_available_devices, clear_all_devices_logs


def log_master(message: str):
    """Print timestamped log message for Master/WebServer"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}]{message}")


# =============================================================================
# HEADLESS BOT - GUI replacement for headless operation
# =============================================================================

class HeadlessVar:
    """Simple wrapper to mimic tk.BooleanVar/StringVar interface for headless mode"""

    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def __bool__(self):
        return bool(self._value)


class HeadlessBot:
    """GUI-less interface for bot_loop compatibility

    Provides the same interface that bot_loop.py expects from BotGUI,
    but operates entirely in memory without tkinter.
    """

    def __init__(self, device_name: str, config: dict, function_layout: list):
        """Initialize headless bot interface

        Args:
            device_name: Device identifier
            config: Merged configuration dictionary
            function_layout: List of function name rows from config
        """
        self.device_name = device_name
        self.config = config
        self.device = device_name  # Alias for compatibility

        # Get LDPlayer index for this device
        device_config = config.get('devices', {}).get(device_name, {})
        self.ld_index: Optional[int] = device_config.get('index')

        # Bot runtime state
        self.is_running = False
        self.bot: Optional[BOT] = None
        self.andy: Optional[Android] = None

        # Function states (replaces tkinter BooleanVars) - use HeadlessVar for .set()/.get() compatibility
        self.function_states: Dict[str, HeadlessVar] = {}
        for row in function_layout:
            for func_name in row:
                self.function_states[func_name] = HeadlessVar(False)

        # Settings (using HeadlessVar to mimic tk.BooleanVar/StringVar interface)
        self.fix_enabled = HeadlessVar(True)
        self.debug = HeadlessVar(False)  # Named 'debug' for compatibility with BotGUI
        self.sleep_time = HeadlessVar(1.0)
        self.studio_stop = HeadlessVar(6)

        # Command triggers
        self.command_triggers: Dict[str, bool] = {}
        for cmd in config.get('commands', []):
            cmd_id = cmd.get('id', '')
            if cmd_id and cmd_id != 'start_stop':
                self.command_triggers[cmd_id] = False

        # Cooldown tracking
        self.last_run_times: Dict[str, float] = {}
        self.cooldown_labels: Dict[str, Any] = {}  # Dummy for compatibility

        # Log buffer
        self.log_buffer: List[str] = []
        self.max_log_lines = 100

        # Direct screenshot storage (in-memory, no database needed)
        self.latest_screenshot: Any = None
        self.screenshot_timestamp: Optional[float] = None

        # Screenshot capture thread
        self._screenshot_thread: Optional[threading.Thread] = None
        self._screenshot_running = False

        # Debug log database (created lazily when debug mode is enabled)
        self.log_db: Optional[LogDatabase] = None

        # Bot timing and state tracking (in-memory)
        self.start_time: Optional[str] = None  # ISO format timestamp
        self.end_time: Optional[str] = None  # ISO format timestamp
        self.current_action: str = ""  # Current bot action/function

        # State manager (optional - for persistence/recovery, not for primary state)
        self.state_manager = None
        # Note: StateManager disabled by default for master_of_bots
        # All state is tracked in-memory for direct Flask access

        # Callbacks for external monitoring
        self.on_log: Optional[Callable[[str, str], None]] = None  # (device_name, entry)
        self.on_status_change: Optional[Callable[[str, str], None]] = None

        # Thread safety (RLock allows reentrant locking from same thread)
        self._lock = threading.RLock()

        # Debug state logging throttle
        self._last_state_log: float = 0.0

        # Root object stub for bot_loop compatibility
        self.root = _RootStub(self)

    def get_checkbox(self, func_name: str) -> bool:
        """Get function enabled state"""
        with self._lock:
            var = self.function_states.get(func_name)
            return bool(var.get()) if var else False

    def set_checkbox(self, func_name: str, enabled: bool):
        """Set function enabled state"""
        with self._lock:
            if func_name in self.function_states:
                self.function_states[func_name].set(enabled)
            else:
                # Only log warnings for unknown functions to console
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}][{self.device_name}] WARNING: Unknown function '{func_name}', available: {list(self.function_states.keys())}")

    def get_state_dict(self) -> dict:
        """Get current bot state as dictionary (thread-safe)

        This provides direct in-memory state access for Flask endpoints,
        eliminating the need for StateManager database queries.

        Returns:
            Dictionary with all bot state including checkboxes, settings,
            timing, logs, and current action
        """
        with self._lock:
            state = {
                'device_name': self.device_name,
                'is_running': self.is_running,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'current_action': self.current_action,
                'screenshot_timestamp': self.screenshot_timestamp,
            }

            # Add function checkboxes
            for func_name, var in self.function_states.items():
                state[func_name] = 1 if var.get() else 0

            # Add settings
            state['fix_enabled'] = 1 if self.fix_enabled.get() else 0
            state['debug_enabled'] = 1 if self.debug.get() else 0
            state['sleep_time'] = self.sleep_time.get()
            state['studio_stop'] = self.studio_stop.get()

            # Add recent logs
            state['current_log'] = '\n'.join(self.log_buffer[-10:]) if self.log_buffer else ''

            # Calculate uptime if running
            if self.start_time and self.is_running:
                try:
                    start_dt = datetime.fromisoformat(self.start_time)
                    uptime_seconds = (datetime.now() - start_dt).total_seconds()
                    state['uptime_seconds'] = uptime_seconds
                except Exception:
                    state['uptime_seconds'] = 0
            elif self.start_time and self.end_time:
                try:
                    start_dt = datetime.fromisoformat(self.start_time)
                    end_dt = datetime.fromisoformat(self.end_time)
                    uptime_seconds = (end_dt - start_dt).total_seconds()
                    state['uptime_seconds'] = uptime_seconds
                except Exception:
                    state['uptime_seconds'] = 0
            else:
                state['uptime_seconds'] = 0

            return state

    def get_screenshot_data(self) -> dict:
        """Get current screenshot data (thread-safe)

        Returns:
            Dictionary with screenshot and timestamp
        """
        with self._lock:
            return {
                'screenshot': self.latest_screenshot,
                'timestamp': self.screenshot_timestamp
            }

    def mark_running(self):
        """Mark bot as running and record start time"""
        with self._lock:
            self.is_running = True
            self.start_time = datetime.now().isoformat()
            self.end_time = None
            if self.state_manager:
                try:
                    self.state_manager.mark_running()
                except Exception:
                    pass

    def mark_stopped(self):
        """Mark bot as stopped and record end time"""
        with self._lock:
            self.is_running = False
            self.end_time = datetime.now().isoformat()
            if self.state_manager:
                try:
                    self.state_manager.mark_stopped()
                except Exception:
                    pass

    def log(self, message: str, screenshot=None, console: bool = False):
        """Add log message

        Args:
            message: Log message
            screenshot: Optional screenshot for debug logging to database
            console: If True, also print to console (for system/framework messages)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}][{self.device_name}] {message}"

        with self._lock:
            self.log_buffer.append(entry)
            if len(self.log_buffer) > self.max_log_lines:
                self.log_buffer = self.log_buffer[-self.max_log_lines:]

        # Print to console only for system/framework messages
        if console:
            print(entry)

        # External callback (for WebSocket streaming)
        if self.on_log:
            try:
                self.on_log(self.device_name, entry)
            except Exception:
                pass

        # Write to debug log database when debug mode is enabled
        if self.debug.get() and screenshot is not None:
            try:
                # Create log database if not already created
                if self.log_db is None:
                    self.log_db = LogDatabase(self.device_name)
                    print(f"[{timestamp}][{self.device_name}] Debug log DB created: {self.log_db.db_path}")
                # Add entry with screenshot
                self.log_db.add_log_entry(message, screenshot)
            except Exception as e:
                # Don't let database errors break logging
                print(f"[{timestamp}][{self.device_name}] Debug log DB error: {e}")

    def update_status(self, status: str, message: str = ""):
        """Update status display"""
        if self.on_status_change:
            try:
                self.on_status_change(status, message)
            except Exception:
                pass

    def update_action(self, action: str):
        """Update current action"""
        with self._lock:
            self.current_action = action
        if self.state_manager:
            try:
                self.state_manager.update_current_action(action)
            except Exception:
                pass

    def _update_full_state(self):
        """Update full state (no-op in headless mode - no state_manager)"""
        pass

    def start_screenshot_capture(self):
        """Start background screenshot capture thread"""
        if self._screenshot_running:
            return

        self._screenshot_running = True

        def capture_loop():
            loop_count = 0
            while self._screenshot_running and self.is_running:
                try:
                    if self.andy is not None:
                        # Skip screenshot if commands are queued to avoid ADB lock contention
                        # find_and_click calls will update screenshots anyway
                        if self.bot and not self.bot._command_queue.empty():
                            time.sleep(0.3)
                            continue

                        screenshot = self.andy.capture_screen()
                        if screenshot is not None:
                            with self._lock:
                                self.latest_screenshot = screenshot
                                self.screenshot_timestamp = time.time()

                    # Update command queue info every ~3 seconds (every 10 iterations) - optional
                    loop_count += 1
                    if loop_count >= 10 and self.state_manager and self.bot and hasattr(self.bot, 'get_command_queue_info'):
                        try:
                            queue_info = self.bot.get_command_queue_info()
                            self.state_manager.update_command_queue(queue_info)
                        except Exception:
                            pass
                        loop_count = 0
                except Exception:
                    pass
                time.sleep(0.3)  # ~3 FPS capture rate

        self._screenshot_thread = threading.Thread(
            target=capture_loop,
            daemon=True,
            name=f"Screenshot-{self.device_name}"
        )
        self._screenshot_thread.start()

    def stop_screenshot_capture(self):
        """Stop background screenshot capture thread"""
        self._screenshot_running = False
        if self._screenshot_thread:
            self._screenshot_thread.join(timeout=1.0)
            self._screenshot_thread = None

    def close_log_db(self):
        """Close the debug log database if open"""
        if self.log_db is not None:
            try:
                self.log_db.close_session()
                self.log_db.conn.close()
            except Exception:
                pass
            self.log_db = None


class _RootStub:
    """Stub for tkinter root window - provides after() method"""

    def __init__(self, headless_bot: HeadlessBot):
        self.headless_bot = headless_bot

    def after(self, delay_ms: int, callback: Optional[Callable] = None):
        """Execute callback (immediately in headless mode)"""
        if callback:
            try:
                callback()
            except Exception:
                pass


# =============================================================================
# MASTER BOT MANAGER - Manages all bot instances
# =============================================================================

class MasterBotManager:
    """Centralized manager for multiple headless bot instances"""

    def __init__(self, game_name: str, config: dict, function_map: dict,
                 command_handlers: dict, do_recover_func: Optional[Callable] = None,
                 findimg_path: Optional[str] = None, devices: Optional[List[str]] = None):
        """Initialize the master bot manager

        Args:
            game_name: Name of the game being run
            config: Merged configuration dictionary
            function_map: Map of function names to callables
            command_handlers: Map of command IDs to handlers
            do_recover_func: Recovery/fix function
            findimg_path: Path to template images
            devices: List of device names to manage (None = all from config)
        """
        self.game_name = game_name
        self.config = config
        self.function_map = function_map
        self.command_handlers = command_handlers
        self.do_recover_func = do_recover_func
        self.findimg_path = findimg_path

        # Pre-compute function signatures once at startup (avoid repeated inspect.signature calls)
        import inspect
        self._function_params: Dict[str, set] = {}
        for func_name, func in function_map.items():
            sig = inspect.signature(func)
            self._function_params[func_name] = set(sig.parameters.keys())

        # Get device list
        all_devices = list(config.get('devices', {}).keys())
        self.device_names = devices if devices else all_devices

        # Bot instances
        self.bots: Dict[str, HeadlessBot] = {}
        self.bot_threads: Dict[str, threading.Thread] = {}

        # Initialize bots for each device
        function_layout = config.get('function_layout', [])
        for device_name in self.device_names:
            self.bots[device_name] = HeadlessBot(device_name, config, function_layout)

        # LDPlayer controller
        try:
            self.ldplayer = LDPlayer.from_config()
        except Exception:
            self.ldplayer = None

        # Shutdown flag
        self._shutdown = False

        log_master(f"[Master] Initialized with {len(self.bots)} devices: {', '.join(self.device_names)}")

    def start_bot(self, device_name: str) -> bool:
        """Start a specific bot

        Args:
            device_name: Device to start

        Returns:
            bool: True if started successfully
        """
        if device_name not in self.bots:
            log_master(f"[Master] Unknown device: {device_name}")
            return False

        bot = self.bots[device_name]
        if bot.is_running:
            log_master(f"[Master] {device_name} already running")
            return False

        # Start bot thread
        thread = threading.Thread(
            target=self._run_bot_loop,
            args=(device_name,),
            daemon=True,
            name=f"Bot-{device_name}"
        )
        self.bot_threads[device_name] = thread
        thread.start()

        # Note: "Starting" not "Started" - actual connection happens in thread
        log_master(f"[Master] Starting {device_name}...")
        return True

    def stop_bot(self, device_name: str) -> bool:
        """Stop a specific bot

        Args:
            device_name: Device to stop

        Returns:
            bool: True if stop signal sent
        """
        if device_name not in self.bots:
            return False

        bot = self.bots[device_name]
        if not bot.is_running:
            return False

        bot.is_running = False

        # Signal stop to bot and android
        if bot.bot:
            bot.bot.should_stop = True
        if bot.andy:
            bot.andy.stop()

        # Close debug log database if open
        bot.close_log_db()

        log_master(f"[Master] Stop signal sent to {device_name}")
        return True

    def start_all(self):
        """Start all bots"""
        for device_name in self.device_names:
            self.start_bot(device_name)

    def stop_all(self):
        """Stop all bots"""
        for device_name in self.device_names:
            self.stop_bot(device_name)

    def shutdown(self):
        """Shutdown all bots and cleanup"""
        self._shutdown = True
        self.stop_all()

        # Quick wait for threads - they should exit fast with interruptible sleep
        deadline = time.time() + 1.0  # Max 1 second total for bot threads
        for thread in self.bot_threads.values():
            if thread.is_alive():
                remaining = max(0.05, deadline - time.time())
                thread.join(timeout=remaining)

        log_master("[Master] Shutdown complete")

    def get_bot(self, device_name: str) -> Optional[HeadlessBot]:
        """Get a bot instance by device name"""
        return self.bots.get(device_name)

    def get_all_states(self) -> List[dict]:
        """Get state of all bots"""
        states = []
        for device_name, bot in self.bots.items():
            state = {
                'device_name': device_name,
                'is_running': bot.is_running,
                'function_states': {k: v.get() for k, v in bot.function_states.items()},
                'settings': {
                    'fix_enabled': bot.fix_enabled.get(),
                    'debug_enabled': bot.debug.get(),
                    'sleep_time': bot.sleep_time.get(),
                },
                'log': bot.log_buffer[-10:] if bot.log_buffer else []
            }
            states.append(state)
        return states

    def _run_bot_loop(self, device_name: str):
        """Run the bot loop for a device (runs in thread)"""
        bot = self.bots[device_name]
        bot.is_running = True

        try:
            # Initialize Android connection
            serial = get_serial(device_name)
            bot.log(f"Looking for device with serial: {serial}", console=True)

            try:
                andy = Android(serial, device_name=device_name)
                andy.set_gui(bot)
                bot.andy = andy
            except AndroidStoppedException:
                # Error already logged by android.py
                raise
            except Exception as e:
                bot.log(f"Failed to connect to device: {device_name} (serial: {serial}) - {e}", console=True)
                raise

            # Initialize BOT
            botobj = BOT(andy, findimg_path=self.findimg_path)
            botobj.set_gui(bot)
            botobj.should_stop = False
            # Tell BOT that main loop handles command processing (not background thread)
            botobj._main_loop_processes_commands = True
            bot.bot = botobj

            bot.log("Bot initialized", console=True)

            # Mark as running (updates start_time and optional StateManager)
            bot.mark_running()

            # Start screenshot capture thread
            bot.start_screenshot_capture()

            # Get configuration
            auto_uncheck = set(self.config.get('auto_uncheck', []))
            function_cooldowns = self.config.get('cooldowns', {})
            bot.last_run_times = {func_name: 0.0 for func_name in self.function_map.keys()}

            # Main loop
            while bot.is_running and not self._shutdown:
                try:
                    # Process any pending commands immediately at loop start
                    self._process_pending_commands(botobj)

                    # Handle command triggers
                    if self.command_handlers:
                        self._handle_commands(bot, botobj)

                    # Execute enabled functions

                    for func_name, func in self.function_map.items():
                        if not bot.is_running:
                            break

                        # Process commands between each function for faster response
                        self._process_pending_commands(botobj)

                        # Check if enabled
                        func_var = bot.function_states.get(func_name)
                        if not func_var or not func_var.get():
                            continue

                        # Check cooldown
                        cooldown = function_cooldowns.get(func_name, 0)
                        if cooldown > 0:
                            current_time = time.time()
                            time_since = current_time - bot.last_run_times.get(func_name, 0)
                            if time_since < cooldown:
                                continue

                        bot.update_status("Running", func_name)
                        # Update current action
                        bot.update_action(func_name)

                        try:
                            result = self._execute_function(func, botobj, device_name, bot, func_name)

                            if result is not False:
                                bot.last_run_times[func_name] = time.time()

                            if result and (result is True or func_name in auto_uncheck):
                                bot.function_states[func_name].set(False)
                                bot.log(f"{func_name} completed - unchecked")

                        except BotStoppedException:
                            bot.log(f"Stopped during {func_name}")
                            raise
                        except AndroidStoppedException:
                            bot.log(f"Android connection lost during {func_name}")
                            raise
                        except Exception as e:
                            bot.log(f"ERROR in {func_name}: {e}")
                            time.sleep(1)

                    # Run fix/recover if enabled
                    if bot.fix_enabled.get() and self.do_recover_func:
                        # Process commands before recovery (recovery can be slow)
                        self._process_pending_commands(botobj)
                        try:
                            bot.update_status("Running", "Fix/Recover")
                            self.do_recover_func(botobj, device_name)
                        except BotStoppedException:
                            raise
                        except Exception as e:
                            bot.log(f"ERROR in Fix/Recover: {e}")

                    # Process any queued commands from web interface
                    # This ensures commands execute at a safe point between bot functions
                    self._process_pending_commands(botobj)

                    # Sleep (interruptible for faster shutdown)
                    sleep_val = bot.sleep_time.get() or 0
                    if sleep_val > 0:
                        # Update current action to idle/sleeping
                        bot.update_action("Idle")
                        bot.update_status("Running", f"Sleeping {sleep_val}s")
                        # Use small increments to check for stop signal
                        sleep_end = time.time() + sleep_val
                        while time.time() < sleep_end and bot.is_running and not self._shutdown:
                            # Process commands during sleep periods too
                            self._process_pending_commands(botobj)
                            time.sleep(0.1)

                except BotStoppedException:
                    bot.log("Bot stopped by user", console=True)
                    break
                except AndroidStoppedException:
                    # Error already logged by android.py
                    break
                except Exception as e:
                    if not bot.is_running:
                        break
                    bot.log(f"ERROR: {e}", console=True)
                    time.sleep(1)

        except AndroidStoppedException:
            # Error already logged by android.py with available serials
            pass
        except Exception as e:
            bot.log(f"Bot error: {e}", console=True)
        finally:
            # Cleanup
            bot.is_running = False
            bot.stop_screenshot_capture()
            # Stop command queue if running
            if bot.bot:
                bot.bot.stop_command_queue()
            bot.update_status("Stopped", "")
            # Mark as stopped (updates end_time and optional StateManager)
            bot.update_action("")  # Clear current action
            bot.mark_stopped()

    def _handle_commands(self, bot: HeadlessBot, botobj: BOT):
        """Handle triggered commands"""
        for command_id, handler in self.command_handlers.items():
            if bot.command_triggers.get(command_id):
                bot.command_triggers[command_id] = False
                bot.update_status("Running", f"{command_id} (command)")
                try:
                    handler(botobj, bot)
                except BotStoppedException:
                    bot.log(f"Stopped during {command_id} command")
                    raise
                except Exception as e:
                    bot.log(f"ERROR in {command_id} command: {e}")

    def _execute_function(self, func: Callable, botobj: BOT, device: str,
                          bot: HeadlessBot, func_name: str):
        """Execute a function with appropriate parameters"""
        # Use pre-computed parameter set instead of calling inspect.signature every time
        params = self._function_params.get(func_name, set())

        kwargs = {}
        if 'bot' in params:
            kwargs['bot'] = botobj
        if 'device' in params:
            kwargs['device'] = device
        if 'gui' in params:
            kwargs['gui'] = bot

        if 'stop' in params:
            kwargs['stop'] = bot.studio_stop.get()

        return func(**kwargs)

    def _process_pending_commands(self, botobj: BOT):
        """Process all pending commands from the queue synchronously

        This method drains the command queue and executes each command
        in order. Called from the main bot loop at safe points to ensure
        commands from the web interface don't conflict with bot operations.
        """
        if not botobj._command_queue:
            return

        # Process all pending commands (non-blocking)
        processed = 0
        while True:
            try:
                item = botobj._command_queue.get_nowait()

                if item is None:
                    # Sentinel value - put it back for the thread to handle
                    botobj._command_queue.put(None)
                    break

                command_func, description = item

                # Update current action for remote command
                if botobj.gui and hasattr(botobj.gui, 'state_manager'):
                    try:
                        botobj.gui.state_manager.update_current_action(f"Remote: {description}" if description else "Remote command")
                    except Exception:
                        pass

                try:
                    command_func()
                    if description and botobj.gui:
                        botobj.log(f"[CMD] {description}")
                    processed += 1
                except BotStoppedException:
                    raise
                except Exception as e:
                    if botobj.gui:
                        botobj.log(f"[CMD] Error: {e}")

                # Remove the completed command from timestamps list (FIFO - oldest first)
                if botobj._command_timestamps:
                    botobj._command_timestamps.pop(0)

                botobj._command_queue.task_done()

            except queue.Empty:
                # No more commands to process
                break

    # LDPlayer control methods
    def ld_launch(self, device_name: str) -> bool:
        """Launch LDPlayer instance for device"""
        if not self.ldplayer:
            return False
        try:
            device_config = self.config.get('devices', {}).get(device_name, {})
            index = device_config.get('index', 0)
            self.ldplayer.launch(index=index)
            return True
        except Exception as e:
            log_master(f"[Master] LD launch error: {e}")
            return False

    def ld_quit(self, device_name: str) -> bool:
        """Quit LDPlayer instance for device"""
        if not self.ldplayer:
            return False
        try:
            device_config = self.config.get('devices', {}).get(device_name, {})
            index = device_config.get('index', 0)
            self.ldplayer.quit(index=index)
            return True
        except Exception as e:
            log_master(f"[Master] LD quit error: {e}")
            return False

    def ld_reboot(self, device_name: str) -> bool:
        """Reboot LDPlayer instance for device"""
        if not self.ldplayer:
            return False
        try:
            device_config = self.config.get('devices', {}).get(device_name, {})
            index = device_config.get('index', 0)
            self.ldplayer.reboot(index=index)
            return True
        except Exception as e:
            log_master(f"[Master] LD reboot error: {e}")
            return False

    def app_start(self, device_name: str) -> bool:
        """Start app on device"""
        if not self.ldplayer:
            return False
        try:
            device_config = self.config.get('devices', {}).get(device_name, {})
            index = device_config.get('index', 0)
            app_package = self.config.get('app_package', '')
            if app_package:
                self.ldplayer.run_app(app_package, index=index)
                return True
            return False
        except Exception as e:
            log_master(f"[Master] App start error: {e}")
            return False

    def app_stop(self, device_name: str) -> bool:
        """Stop app on device"""
        if not self.ldplayer:
            return False
        try:
            device_config = self.config.get('devices', {}).get(device_name, {})
            index = device_config.get('index', 0)
            app_package = self.config.get('app_package', '')
            if app_package:
                self.ldplayer.kill_app(app_package, index=index)
                return True
            return False
        except Exception as e:
            log_master(f"[Master] App stop error: {e}")
            return False


# =============================================================================
# WEB SERVER - Direct control without database relay
# =============================================================================

def create_web_server(manager: MasterBotManager, config: dict):
    """Create Flask web server with direct bot control

    Args:
        manager: MasterBotManager instance
        config: Configuration dictionary

    Returns:
        tuple: (Flask app, SocketIO instance)
    """
    from flask import Flask, jsonify, request, send_from_directory
    from flask_cors import CORS
    from flask_socketio import SocketIO, emit
    import base64
    import cv2 as cv
    import numpy as np
    from PIL import Image
    import io
    import logging

    # Suppress Flask/Werkzeug request logging and startup messages (only show errors)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)

    # Suppress threading exception output for WebSocket connection reset errors
    # These occur when clients disconnect abruptly (browser closed, network issue)
    import sys
    original_excepthook = sys.excepthook
    def custom_excepthook(exc_type, exc_value, exc_tb):
        # Suppress ConnectionResetError from WebSocket threads
        if exc_type is ConnectionResetError:
            return
        original_excepthook(exc_type, exc_value, exc_tb)
    sys.excepthook = custom_excepthook

    # Also suppress in threading
    original_threading_excepthook = threading.excepthook
    def custom_threading_excepthook(args):
        # Suppress ConnectionResetError and BrokenPipeError from WebSocket threads
        if args.exc_type in (ConnectionResetError, BrokenPipeError, OSError):
            return
        original_threading_excepthook(args)
    threading.excepthook = custom_threading_excepthook

    # Suppress Flask CLI banner ("Serving Flask app...")
    import click
    def secho_noop(*args, **kwargs):  # noqa: ARG001
        pass
    def echo_noop(*args, **kwargs):  # noqa: ARG001
        pass
    click.secho = secho_noop
    click.echo = echo_noop

    # Use the web/static folder for static files
    static_folder = os.path.join(os.path.dirname(__file__), 'web', 'static')
    app = Flask(__name__, static_folder=static_folder, static_url_path='')
    CORS(app)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    # ==========================================================================
    # STATIC FILE ROUTES
    # ==========================================================================

    @app.route('/')
    def index():
        return send_from_directory(static_folder, 'index.html')

    @app.route('/<path:path>')
    def static_files(path):
        return send_from_directory(static_folder, path)

    # ==========================================================================
    # API ENDPOINTS
    # ==========================================================================

    @app.route('/api/ping', methods=['GET'])
    def ping():
        """Simple health check endpoint"""
        return jsonify({'success': True, 'message': 'pong', 'bots': len(manager.bots)})

    @app.route('/api/config', methods=['GET'])
    def get_config():
        try:
            return jsonify({'success': True, 'config': config})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        try:
            # Get stats directly from in-memory bot states
            stats = {
                'total_bots': len(manager.bots),
                'running_bots': sum(1 for b in manager.bots.values() if b.is_running),
                'stopped_bots': sum(1 for b in manager.bots.values() if not b.is_running),
                'db_size_mb': 0,  # StateManager database not used in direct access mode
            }
            return jsonify({'success': True, 'stats': stats})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # Cache LDPlayer status to avoid spawning subprocess for every bot on every request
    ld_status_cache = {'data': {}, 'timestamp': 0}
    ld_cache_ttl = 2.0  # Cache for 2 seconds

    # Background thread for LD status updates
    ld_status_thread_running = False

    def refresh_ld_status_background():
        """Background thread that periodically refreshes LD status"""
        nonlocal ld_status_thread_running
        first_run = True
        while ld_status_thread_running and not manager._shutdown:
            try:
                if manager.ldplayer:
                    try:
                        instances = manager.ldplayer.list_instances(timeout=5.0)
                        status = {}
                        for inst in instances:
                            status[inst['index']] = inst.get('android_started', False)
                        ld_status_cache['data'] = status
                        ld_status_cache['timestamp'] = time.time()
                        if first_run:
                            log_master(f"[LDStatus] Initial status retrieved: {len(status)} instances")
                            first_run = False

                        # Update StateManager database with LD status for each bot (if state_manager available)
                        try:
                            for device_name, bot in manager.bots.items():
                                if bot.ld_index is not None and bot.state_manager:
                                    is_running = status.get(bot.ld_index, False)
                                    bot.state_manager.update_ld_running(is_running)
                        except Exception as sm_err:
                            pass  # Don't let StateManager errors break the status thread

                    except subprocess.TimeoutExpired:
                        if first_run:
                            log_master("[LDStatus] Timeout on first status check, will retry")
                            first_run = False
                        pass  # Keep old cache
                    except Exception as e:
                        if first_run:
                            log_master(f"[LDStatus] Error on first status check: {e}")
                            first_run = False
            except Exception as e:
                if first_run:
                    log_master(f"[LDStatus] Unexpected error: {e}")
                    first_run = False
            # Refresh every 3 seconds
            time.sleep(3.0)

    def start_ld_status_thread():
        """Start the background LD status refresh thread"""
        nonlocal ld_status_thread_running
        if ld_status_thread_running:
            return
        ld_status_thread_running = True
        thread = threading.Thread(
            target=refresh_ld_status_background,
            daemon=True,
            name="LDStatusRefresh"
        )
        thread.start()
        log_master("[WebServer] Started LDPlayer status background thread")

    def get_ld_status_cached():
        """Get all LDPlayer instance statuses from cache (non-blocking)"""
        # Start background refresh thread if not running
        if not ld_status_thread_running:
            start_ld_status_thread()
        # Always return cached data immediately (never block)
        return ld_status_cache['data']

    def check_ld_running(bot) -> bool:
        """Check if LDPlayer is running for a bot (uses cache)"""
        if manager.ldplayer and bot.ld_index is not None:
            status = get_ld_status_cached()
            # Return True if index is in cache and marked as running
            is_running = status.get(bot.ld_index, False)
            # Debug log if cache is empty (only once per device)
            if not status and not hasattr(bot, '_ld_status_warning_logged'):
                log_master(f"[LDStatus] Warning: Status cache is empty for {bot.device_name} (index {bot.ld_index})")
                bot._ld_status_warning_logged = True
            return is_running
        return False

    @app.route('/api/bots', methods=['GET'])
    def get_all_bots():
        try:
            all_bots = []
            # Snapshot bot items to avoid iteration issues
            bot_items = list(manager.bots.items())
            for device_name, bot in bot_items:
                try:
                    # Get state directly from HeadlessBot in-memory
                    bot_state = bot.get_state_dict()

                    # Add additional fields
                    bot_state['ld_running'] = check_ld_running(bot)
                    bot_state['last_update'] = datetime.now().isoformat()
                    bot_state['elapsed_seconds'] = 0

                    # Only include last 5 log lines in list view for performance
                    # Full logs are fetched via /api/bots/<device_name> endpoint
                    bot_state['current_log'] = '\n'.join(bot.log_buffer[-5:]) if bot.log_buffer else ''

                    all_bots.append(bot_state)
                except Exception as bot_error:
                    log_master(f"[API] Error getting state for {device_name}: {bot_error}")

            all_bots.sort(key=lambda x: x['device_name'].lower())
            return jsonify({'success': True, 'bots': all_bots})
        except Exception as e:
            log_master(f"[API] Error in get_all_bots: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/bots/<device_name>', methods=['GET'])
    def get_device_state(device_name):
        try:
            bot = manager.get_bot(device_name)
            if not bot:
                return jsonify({'success': False, 'error': 'Device not found'}), 404

            # Get state directly from HeadlessBot in-memory
            state = bot.get_state_dict()

            # Add additional fields
            state['ld_running'] = check_ld_running(bot)
            state['last_update'] = datetime.now().isoformat()
            state['current_log'] = '\n'.join(bot.log_buffer)

            return jsonify({'success': True, 'state': state})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/bots/<device_name>/screenshot', methods=['GET'])
    def get_device_screenshot(device_name):
        # Get directly from bot memory for speed
        bot = manager.get_bot(device_name)
        if not bot:
            return jsonify({'success': False, 'error': 'Device not found'}), 404

        # Check if bot is running and has screenshot capability
        if not bot.is_running:
            return jsonify({'success': False, 'error': 'Bot not running'}), 404

        # Thread-safe access to screenshot
        with bot._lock:
            screenshot = bot.latest_screenshot
            timestamp = bot.screenshot_timestamp

            if screenshot is None:
                return jsonify({'success': False, 'error': 'No screenshot available'}), 404

            # Make a copy to avoid race conditions
            try:
                screenshot = screenshot.copy()
            except Exception:
                return jsonify({'success': False, 'error': 'Screenshot not ready'}), 404

        try:
            # Convert color space to RGB (JPEG doesn't support alpha)
            if len(screenshot.shape) == 3:
                if screenshot.shape[2] == 4:
                    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGB)
                elif screenshot.shape[2] == 3:
                    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

            size = request.args.get('size', 'full')
            img = Image.fromarray(screenshot)
            original_width, original_height = img.size

            if size == 'preview':
                img = img.resize((85, 150), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=60, optimize=True)
                buffer.seek(0)
                base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                mime_type = 'image/jpeg'
            else:
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                mime_type = 'image/png'

            return jsonify({
                'success': True,
                'screenshot': f'data:{mime_type};base64,{base64_data}',
                'timestamp': str(timestamp) if timestamp else None,
                'width': original_width,
                'height': original_height
            })
        except Exception as e:
            log_master(f"[API] Screenshot processing error for {device_name}: {e}")
            return jsonify({'success': False, 'error': f'Processing error: {e}'}), 500

    @app.route('/api/bots/<device_name>/details', methods=['GET'])
    def get_device_details(device_name):
        """Get detailed device information including command queue and current activity"""
        try:
            bot = manager.get_bot(device_name)
            if not bot:
                return jsonify({'success': False, 'error': 'Device not found'}), 404

            # Get command queue info
            command_queue = {'queue_size': 0, 'commands': []}
            if bot.bot and hasattr(bot.bot, 'get_command_queue_info'):
                try:
                    command_queue = bot.bot.get_command_queue_info()
                except Exception:
                    pass

            # Get current action directly from bot in-memory
            current_action = bot.current_action or 'Idle'

            details = {
                'device_name': device_name,
                'current_action': current_action,
                'is_running': bot.is_running,
                'command_queue': command_queue
            }

            return jsonify({'success': True, 'details': details})
        except Exception as e:
            log_master(f"[API] Error getting details for {device_name}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==========================================================================
    # DIRECT COMMAND ENDPOINTS (no database relay)
    # ==========================================================================

    @app.route('/api/command/checkbox', methods=['POST'])
    def send_checkbox_command():
        try:
            data = request.json
            log_master(f"[API] Checkbox command received: {data}")
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            apply_mode = data.get('apply_mode', 'current')
            checkbox_name = data.get('name')
            enabled = data.get('enabled')

            if not checkbox_name or enabled is None:
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400

            if apply_mode == 'all':
                # Snapshot bot list to avoid iteration issues
                bots = list(manager.bots.values())
                for bot in bots:
                    bot.set_checkbox(checkbox_name, enabled)
            else:
                if not device_name:
                    return jsonify({'success': False, 'error': 'device_name required'}), 400
                bot = manager.get_bot(device_name)
                if bot:
                    bot.set_checkbox(checkbox_name, enabled)
                else:
                    log_master(f"[API] Bot not found for device: {device_name}")

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/setting', methods=['POST'])
    def send_setting_command():
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            apply_mode = data.get('apply_mode', 'current')
            setting_name = data.get('name')
            value = data.get('value')

            if not setting_name or value is None:
                return jsonify({'success': False, 'error': 'Missing required fields'}), 400

            def apply_setting(bot):
                if setting_name == 'sleep_time':
                    bot.sleep_time.set(float(value))
                elif setting_name == 'debug_enabled':
                    bot.debug.set(bool(value))
                elif setting_name == 'fix_enabled':
                    bot.fix_enabled.set(bool(value))

            if apply_mode == 'all':
                # Snapshot bot list to avoid iteration issues
                bots = list(manager.bots.values())
                for bot in bots:
                    apply_setting(bot)
            else:
                if not device_name:
                    return jsonify({'success': False, 'error': 'device_name required'}), 400
                bot = manager.get_bot(device_name)
                if bot:
                    apply_setting(bot)

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/tap', methods=['POST'])
    def send_tap_command():
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            apply_mode = data.get('apply_mode', 'current')
            x, y = data.get('x'), data.get('y')

            if x is None or y is None:
                return jsonify({'success': False, 'error': 'Missing coordinates'}), 400

            # Queue taps for serialized execution per device
            if apply_mode == 'all':
                # Snapshot bot list to avoid iteration issues
                bots = list(manager.bots.values())
                for bot in bots:
                    if bot.is_running and bot.bot:
                        tap_x, tap_y = int(x), int(y)
                        bot.bot.queue_command(
                            lambda b=bot.bot, tx=tap_x, ty=tap_y: b.tap(tx, ty),
                            f"Tap at ({tap_x}, {tap_y})"
                        )
            else:
                if not device_name:
                    return jsonify({'success': False, 'error': 'device_name required'}), 400
                bot = manager.get_bot(device_name)
                if not bot:
                    return jsonify({'success': False, 'error': f'Bot not found: {device_name}'}), 404
                if not bot.is_running:
                    return jsonify({'success': False, 'error': f'Bot not running: {device_name}'}), 400
                if not bot.bot:
                    return jsonify({'success': False, 'error': f'Bot object not initialized: {device_name}'}), 400

                tap_x, tap_y = int(x), int(y)
                bot.bot.queue_command(
                    lambda b=bot.bot, tx=tap_x, ty=tap_y: b.tap(tx, ty),
                    f"Tap at ({tap_x}, {tap_y})"
                )

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/swipe', methods=['POST'])
    def send_swipe_command():
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            apply_mode = data.get('apply_mode', 'current')
            x1, y1, x2, y2 = data.get('x1'), data.get('y1'), data.get('x2'), data.get('y2')
            duration = data.get('duration', 500)

            if any(v is None for v in [x1, y1, x2, y2]):
                return jsonify({'success': False, 'error': 'Missing coordinates'}), 400

            # Queue swipes for serialized execution per device
            if apply_mode == 'all':
                # Snapshot bot list to avoid iteration issues
                bots = list(manager.bots.values())
                for bot in bots:
                    if bot.is_running and bot.bot:
                        sx1, sy1, sx2, sy2, sdur = int(x1), int(y1), int(x2), int(y2), int(duration)
                        bot.bot.queue_command(
                            lambda b=bot.bot, a=sx1, c=sy1, d=sx2, e=sy2, f=sdur: b.swipe(a, c, d, e, duration=f),
                            f"Swipe ({sx1},{sy1})->({sx2},{sy2})"
                        )
            else:
                if not device_name:
                    return jsonify({'success': False, 'error': 'device_name required'}), 400
                bot = manager.get_bot(device_name)
                if not bot:
                    return jsonify({'success': False, 'error': f'Bot not found: {device_name}'}), 404
                if not bot.is_running:
                    return jsonify({'success': False, 'error': f'Bot not running: {device_name}'}), 400
                if not bot.bot:
                    return jsonify({'success': False, 'error': f'Bot object not initialized: {device_name}'}), 400

                sx1, sy1, sx2, sy2, sdur = int(x1), int(y1), int(x2), int(y2), int(duration)
                bot.bot.queue_command(
                    lambda b=bot.bot, a=sx1, c=sy1, d=sx2, e=sy2, f=sdur: b.swipe(a, c, d, e, duration=f),
                    f"Swipe ({sx1},{sy1})->({sx2},{sy2})"
                )

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/bot', methods=['POST'])
    def send_bot_command():
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            action = data.get('action')

            if not device_name:
                return jsonify({'success': False, 'error': 'Missing device_name'}), 400
            if action not in ['start', 'stop']:
                return jsonify({'success': False, 'error': 'Invalid action'}), 400

            if action == 'start':
                manager.start_bot(device_name)
            else:
                manager.stop_bot(device_name)

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/trigger', methods=['POST'])
    def send_trigger_command():
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            apply_mode = data.get('apply_mode', 'current')
            command = data.get('command')

            if not command:
                return jsonify({'success': False, 'error': 'Missing command'}), 400

            if command == 'start_stop':
                if apply_mode == 'all':
                    # Snapshot bot items to avoid iteration issues
                    bot_items = list(manager.bots.items())
                    for dn, bot in bot_items:
                        if bot.is_running:
                            manager.stop_bot(dn)
                        else:
                            manager.start_bot(dn)
                else:
                    if not device_name:
                        return jsonify({'success': False, 'error': 'device_name required'}), 400
                    bot = manager.get_bot(device_name)
                    if bot:
                        if bot.is_running:
                            manager.stop_bot(device_name)
                        else:
                            manager.start_bot(device_name)
            else:
                # Trigger command
                def trigger(bot):
                    if command in bot.command_triggers:
                        bot.command_triggers[command] = True

                if apply_mode == 'all':
                    # Snapshot bot list to avoid iteration issues
                    bots = list(manager.bots.values())
                    for bot in bots:
                        trigger(bot)
                else:
                    if not device_name:
                        return jsonify({'success': False, 'error': 'device_name required'}), 400
                    bot = manager.get_bot(device_name)
                    if bot:
                        trigger(bot)

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/ldplayer', methods=['POST'])
    def send_ldplayer_command():
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            apply_mode = data.get('apply_mode', 'current')
            command = data.get('command')

            if not command:
                return jsonify({'success': False, 'error': 'Missing command'}), 400

            command_map = {
                'ld_start': manager.ld_launch,
                'ld_stop': manager.ld_quit,
                'ld_reboot': manager.ld_reboot,
                'app_start': manager.app_start,
                'app_stop': manager.app_stop
            }

            if command not in command_map:
                return jsonify({'success': False, 'error': f'Unknown command: {command}'}), 400

            handler = command_map[command]

            def run_handler(dn):
                """Execute LDPlayer command in background thread"""
                try:
                    handler(dn)
                except Exception as e:
                    log_master(f"[API] LDPlayer command error for {dn}: {e}")

            # Execute LDPlayer commands asynchronously to avoid blocking HTTP response
            if apply_mode == 'all':
                for dn in manager.device_names:
                    threading.Thread(target=run_handler, args=(dn,), daemon=True).start()
            else:
                if not device_name:
                    return jsonify({'success': False, 'error': 'device_name required'}), 400
                threading.Thread(target=run_handler, args=(device_name,), daemon=True).start()

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/command/screenshot', methods=['POST'])
    def take_screenshot_to_paint():
        """Take a screenshot and open it in MS Paint on the server"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data'}), 400

            device_name = data.get('device_name')
            if not device_name:
                return jsonify({'success': False, 'error': 'Missing device_name'}), 400

            bot = manager.get_bot(device_name)
            if not bot:
                return jsonify({'success': False, 'error': f'Bot not found: {device_name}'}), 404

            # Get screenshot from bot's Android connection
            if bot.andy is None:
                return jsonify({'success': False, 'error': 'No Android connection'}), 400

            screenshot = bot.andy.capture_screen()
            if screenshot is None:
                return jsonify({'success': False, 'error': 'Failed to capture screenshot'}), 500

            # Save to file
            screenshot_config = config.get('screenshot', {})
            output_file = screenshot_config.get('default_output', 'tempScreenShot.png')

            # Convert BGR to RGB for PIL
            if len(screenshot.shape) == 3:
                if screenshot.shape[2] == 4:
                    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGB)
                elif screenshot.shape[2] == 3:
                    screenshot = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

            img = Image.fromarray(screenshot)
            img.save(output_file)

            # Open in MS Paint
            abs_path = os.path.abspath(output_file)
            subprocess.Popen(['mspaint.exe', abs_path])

            bot.log(f"Screenshot opened in MS Paint: {output_file}")
            return jsonify({'success': True, 'file': output_file})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==========================================================================
    # LOG DATABASE API ENDPOINTS
    # ==========================================================================

    @app.route('/api/logs/devices')
    def api_logs_devices():
        """Get list of devices that have log databases"""
        try:
            devices = get_available_devices()
            return jsonify({'success': True, 'devices': devices})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/logs/<device_name>/sessions')
    def api_logs_sessions(device_name: str):
        """Get list of log sessions for a device"""
        try:
            db = LogDatabase(device_name, read_only=True)
            sessions = db.get_sessions()
            return jsonify({'success': True, 'sessions': sessions})
        except FileNotFoundError:
            return jsonify({'success': False, 'error': f'No log database found for device: {device_name}'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/logs/<device_name>/sessions/<session_id>/entries')
    def api_logs_entries(device_name: str, session_id: str):
        """Get log entries for a specific session"""
        try:
            include_screenshots = request.args.get('include_screenshots', 'false').lower() == 'true'
            db = LogDatabase(device_name, read_only=True)
            entries = db.get_log_entries(session_id, include_screenshots=include_screenshots)

            # Convert screenshots to base64 if included
            if include_screenshots:
                for entry in entries:
                    if entry.get('screenshot'):
                        screenshot_b64 = base64.b64encode(entry['screenshot']).decode('utf-8')
                        entry['screenshot'] = f'data:image/png;base64,{screenshot_b64}'

            return jsonify({'success': True, 'entries': entries})
        except FileNotFoundError:
            return jsonify({'success': False, 'error': f'No log database found for device: {device_name}'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/logs/<device_name>/sessions/<int:session_id>/clear', methods=['POST', 'DELETE'])
    def api_clear_session(device_name: str, session_id: int):
        """Clear all log entries for a specific session"""
        try:
            # Check if device has logs
            available_devices = get_available_devices()
            if device_name not in available_devices:
                return jsonify({'success': False, 'error': f'No log database found for device: {device_name}'}), 404

            db = LogDatabase(device_name, read_only=False)
            db.clear_session(session_id)
            db.conn.close()
            return jsonify({'success': True, 'message': f'Cleared session {session_id}'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/logs/<device_name>/clear', methods=['POST', 'DELETE'])
    def api_clear_device(device_name: str):
        """Clear all logs for a specific device"""
        try:
            # Check if device has logs
            available_devices = get_available_devices()
            if device_name not in available_devices:
                return jsonify({'success': False, 'error': f'No log database found for device: {device_name}'}), 404

            db = LogDatabase(device_name, read_only=False)
            db.clear_all_logs()
            db.conn.close()
            return jsonify({'success': True, 'message': f'Cleared all logs for device {device_name}'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/logs/clear-all', methods=['POST', 'DELETE'])
    def api_clear_all_logs():
        """Clear all logs from all devices"""
        try:
            cleared_count = clear_all_devices_logs()
            return jsonify({'success': True, 'message': f'Cleared logs from {cleared_count} device(s)', 'cleared_count': cleared_count})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ==========================================================================
    # WEBSOCKET HANDLERS
    # ==========================================================================

    @socketio.on('connect')
    def handle_connect():
        sid = getattr(request, 'sid', 'unknown')
        log_master(f'[WebSocket] Client connected: {sid}')
        emit('connection_status', {'status': 'connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        sid = getattr(request, 'sid', 'unknown')
        log_master(f'[WebSocket] Client disconnected: {sid}')

    # Screenshot monitor thread - optimized for adaptive quality and bandwidth
    def screenshot_monitor_thread():
        """Intelligent screenshot streaming with automatic optimizations

        Features:
        - Adaptive quality based on network performance
        - Motion detection to skip unchanged frames
        - WebP compression with JPEG fallback
        - Frame skipping under load
        - Automatic FPS adjustment
        """
        # Quality tiers - automatically adjust based on send performance
        quality_tiers = {
            'ultra_low': {'quality': 40, 'scale': 0.5, 'name': 'Ultra Low'},
            'low': {'quality': 50, 'scale': 0.67, 'name': 'Low'},
            'medium': {'quality': 65, 'scale': 0.75, 'name': 'Medium'},
            'normal': {'quality': 85, 'scale': 1.0, 'name': 'Normal'},
            'high': {'quality': 95, 'scale': 1.0, 'name': 'High'}
        }

        # State tracking per device
        last_screenshots = {}        # Last timestamp sent
        last_preview_send = {}       # Last preview send time
        last_frames = {}             # Last frame for motion detection
        send_times = {}              # Track send performance per device
        sending = {}                 # Track if send is in progress
        current_quality = {}         # Current quality tier per device

        preview_interval = 1.0
        base_fps = 10  # Target FPS (will auto-adjust down under load)

        # Detect WebP support
        webp_supported = False
        try:
            test_img = Image.new('RGB', (10, 10))
            test_buffer = io.BytesIO()
            test_img.save(test_buffer, format='WEBP', quality=80)
            webp_supported = True
            log_master("[WebSocket] WebP compression enabled")
        except Exception:
            log_master("[WebSocket] WebP not supported, using JPEG")

        # Reusable buffers to reduce memory allocations
        main_buffer = io.BytesIO()
        preview_buffer = io.BytesIO()

        while not manager._shutdown:
            try:
                sleep_interval = 1.0 / base_fps
                current_time = time.time()

                for device_name in manager.device_names:
                    try:
                        # Skip if previous send still in progress (frame skipping)
                        if sending.get(device_name, False):
                            continue

                        # Read directly from bot memory instead of database
                        bot = manager.get_bot(device_name)
                        if not bot:
                            continue

                        screenshot = bot.latest_screenshot
                        timestamp = bot.screenshot_timestamp

                        if screenshot is None or timestamp is None:
                            continue

                        # Skip if timestamp hasn't changed
                        if last_screenshots.get(device_name) == timestamp:
                            continue

                        # Initialize quality tier for new device
                        if device_name not in current_quality:
                            current_quality[device_name] = 'normal'

                        try:
                            # Make a copy to avoid race conditions
                            screenshot_copy = screenshot.copy()

                            # Motion detection - skip if scene hasn't changed significantly
                            if device_name in last_frames:
                                # Resize for fast comparison
                                small_current = cv.resize(screenshot_copy, (64, 64))
                                small_last = cv.resize(last_frames[device_name], (64, 64))

                                # Calculate difference
                                diff = cv.absdiff(small_current, small_last)
                                gray_diff = cv.cvtColor(diff, cv.COLOR_BGR2GRAY) if len(diff.shape) == 3 else diff
                                changed_pixels = np.count_nonzero(gray_diff > 25)
                                total_pixels = gray_diff.size
                                change_percentage = changed_pixels / total_pixels

                                # Skip if less than 0.5% changed (very static scene)
                                if change_percentage < 0.005:
                                    continue

                            # Store current frame for next motion detection
                            last_frames[device_name] = screenshot_copy.copy()
                            last_screenshots[device_name] = timestamp

                            # Convert color space
                            if len(screenshot_copy.shape) == 3:
                                if screenshot_copy.shape[2] == 4:
                                    screenshot_copy = cv.cvtColor(screenshot_copy, cv.COLOR_BGRA2RGB)
                                elif screenshot_copy.shape[2] == 3:
                                    screenshot_copy = cv.cvtColor(screenshot_copy, cv.COLOR_BGR2RGB)

                            img = Image.fromarray(screenshot_copy)
                            original_width, original_height = img.size

                            # Apply quality tier scaling and compression
                            tier = quality_tiers[current_quality[device_name]]
                            if tier['scale'] < 1.0:
                                scaled_width = int(original_width * tier['scale'])
                                scaled_height = int(original_height * tier['scale'])
                                img = img.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)

                            # Encode with WebP or JPEG
                            main_buffer.seek(0)
                            main_buffer.truncate(0)

                            if webp_supported:
                                img.save(main_buffer, format='WEBP', quality=tier['quality'], method=4)
                                mime_type = 'image/webp'
                            else:
                                img.save(main_buffer, format='JPEG', quality=tier['quality'], optimize=True)
                                mime_type = 'image/jpeg'

                            base64_data = base64.b64encode(main_buffer.getvalue()).decode('utf-8')
                            data_size_kb = len(main_buffer.getvalue()) / 1024

                            # Build message
                            message = {
                                'device_name': device_name,
                                'screenshot': f'data:{mime_type};base64,{base64_data}',
                                'timestamp': str(timestamp),
                                'width': original_width,
                                'height': original_height
                            }

                            # Include preview at reduced rate
                            last_preview = last_preview_send.get(device_name, 0)
                            include_preview = (current_time - last_preview) >= preview_interval

                            if include_preview:
                                preview_img = Image.fromarray(screenshot_copy) if tier['scale'] < 1.0 else img
                                preview_img = preview_img.resize((85, 150), Image.Resampling.LANCZOS)
                                preview_buffer.seek(0)
                                preview_buffer.truncate(0)

                                if webp_supported:
                                    preview_img.save(preview_buffer, format='WEBP', quality=50, method=4)
                                else:
                                    preview_img.save(preview_buffer, format='JPEG', quality=60, optimize=True)

                                preview_base64 = base64.b64encode(preview_buffer.getvalue()).decode('utf-8')
                                message['preview'] = f'data:{mime_type};base64,{preview_base64}'
                                last_preview_send[device_name] = current_time

                            # Track send performance for adaptive quality
                            sending[device_name] = True
                            send_start = time.time()

                            socketio.emit('screenshot_update', message)

                            send_duration = time.time() - send_start
                            sending[device_name] = False

                            # Update send time tracking
                            if device_name not in send_times:
                                send_times[device_name] = []
                            send_times[device_name].append(send_duration)
                            send_times[device_name] = send_times[device_name][-10:]  # Keep last 10

                            # Adaptive quality adjustment based on send performance
                            avg_send_time = sum(send_times[device_name]) / len(send_times[device_name])

                            # Adjust quality tier based on performance
                            tier_order = ['ultra_low', 'low', 'medium', 'normal', 'high']
                            current_idx = tier_order.index(current_quality[device_name])

                            if avg_send_time > 0.3:  # Taking >300ms to send - decrease quality
                                if current_idx > 0:
                                    new_tier = tier_order[current_idx - 1]
                                    if current_quality[device_name] != new_tier:
                                        current_quality[device_name] = new_tier
                                        log_master(f"[WebSocket] {device_name}: Reduced quality to {quality_tiers[new_tier]['name']} (send: {avg_send_time:.2f}s, size: {data_size_kb:.1f}KB)")
                            elif avg_send_time < 0.08 and data_size_kb < 100:  # Very fast - try increasing
                                if current_idx < len(tier_order) - 1:
                                    new_tier = tier_order[current_idx + 1]
                                    if current_quality[device_name] != new_tier:
                                        current_quality[device_name] = new_tier
                                        log_master(f"[WebSocket] {device_name}: Increased quality to {quality_tiers[new_tier]['name']} (send: {avg_send_time:.2f}s)")

                            # Explicitly delete large objects to help GC
                            del screenshot_copy
                            del img
                            if include_preview and 'preview_img' in locals():
                                del preview_img

                        except Exception as e:
                            sending[device_name] = False
                            log_master(f'[WebSocket] Error encoding screenshot for {device_name}: {e}')
                    except Exception:
                        sending[device_name] = False
                        pass

                time.sleep(sleep_interval)

            except Exception as e:
                log_master(f'[WebSocket] Screenshot monitor error: {e}')
                time.sleep(1)

    # Start screenshot monitor
    log_master("[WebSocket] Starting screenshot monitor thread...")
    monitor_thread = threading.Thread(
        target=screenshot_monitor_thread,
        daemon=True,
        name="ScreenshotMonitor"
    )
    monitor_thread.start()
    log_master("[WebSocket] Screenshot monitor thread started")

    # Set up log streaming callback for all bots
    def on_log_callback(device_name: str, entry: str):
        """Emit log entry to WebSocket clients"""
        try:
            socketio.emit('log_update', {
                'device_name': device_name,
                'entry': entry,
                'timestamp': time.time()
            })
        except Exception:
            pass

    # Register callback on all bots
    for bot in manager.bots.values():
        bot.on_log = on_log_callback

    return app, socketio


# =============================================================================
# GAME MODULE LOADING
# =============================================================================

def get_available_games():
    """Get list of available game modules"""
    games_dir = os.path.join(os.path.dirname(__file__), 'games')
    games = []

    if not os.path.exists(games_dir):
        return games

    for item in os.listdir(games_dir):
        item_path = os.path.join(games_dir, item)
        if os.path.isdir(item_path):
            functions_file = os.path.join(item_path, 'functions.py')
            if os.path.exists(functions_file):
                games.append(item)

    return sorted(games)


def load_game_modules(game_name):
    """Load game functions and commands modules"""
    functions_module = importlib.import_module(f'games.{game_name}.functions')

    try:
        commands_module = importlib.import_module(f'games.{game_name}.commands')
    except ImportError:
        import types
        commands_module = types.ModuleType(f'games.{game_name}.commands')

    findimg_path = os.path.join(os.path.dirname(__file__), 'games', game_name, 'findimg')

    return functions_module, commands_module, findimg_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Master of Bots - Centralized headless bot manager',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('game', nargs='?', type=str,
                        help='Game module name (folder in games/)')
    parser.add_argument('--port', type=int, default=5000,
                        help='Web server port (default: 5000)')
    parser.add_argument('--devices', type=str,
                        help='Comma-separated list of devices (default: all)')
    parser.add_argument('--no-auto-start-bot', action='store_true',
                        help='Disable auto-starting all bots on launch')
    parser.add_argument('--no-auto-start-device', action='store_true',
                        help='Disable auto-launching LDPlayer devices')
    parser.add_argument('--no-web', action='store_true',
                        help='Disable web server (CLI-only mode)')
    parser.add_argument('-l', '--list-games', action='store_true',
                        help='List available games and exit')

    args = parser.parse_args()

    # List games
    if args.list_games:
        games = get_available_games()
        if games:
            print("Available games:")
            for game in games:
                print(f"  - {game}")
        else:
            print("No games found in games/ directory")
        sys.exit(0)

    # Validate game argument
    if not args.game:
        print("ERROR: Game name required")
        print("Usage: python master_of_bots.py <game_name> [options]")
        print("Use --list-games to see available games")
        sys.exit(1)

    game_name = args.game
    available_games = get_available_games()
    if game_name not in available_games:
        print(f"ERROR: Game '{game_name}' not found")
        print(f"Available games: {', '.join(available_games)}")
        sys.exit(1)

    # Load configuration
    config = load_config(game_name)

    # Parse device list
    all_devices = list(config.get('devices', {}).keys())
    devices = None
    if args.devices:
        devices = [d.strip() for d in args.devices.split(',')]
        for d in devices:
            if d not in all_devices:
                print(f"ERROR: Device '{d}' not found in config")
                print(f"Available devices: {', '.join(all_devices)}")
                sys.exit(1)

    # Auto-launch LDPlayer devices (default behavior, disabled with --no-auto-start-device)
    if not args.no_auto_start_device:
        # Use specified devices or all devices
        devices_to_launch = devices if devices else all_devices
        log_master(f"[Master] Checking if devices need to be launched: {', '.join(devices_to_launch)}")
        launch_devices_if_needed(
            device_names=devices_to_launch,
            master_config=config,
            stagger_delay=5.0,
            boot_wait=45.0,
            log_func=lambda msg: log_master(f"[Master] {msg}")
        )

    # Load game modules
    try:
        game_functions, game_commands, findimg_path = load_game_modules(game_name)
    except ImportError as e:
        print(f"ERROR: Failed to load game modules for '{game_name}': {e}")
        sys.exit(1)

    # Build function and command maps
    function_map = build_function_map(config, game_functions)
    command_handlers = build_command_map(config, game_commands)

    # Get do_recover function
    do_recover_func = getattr(game_functions, 'do_recover', None)

    # Print banner
    app_name = config.get('app_name', 'Bot')
    log_master(f"[Master] Starting {app_name}")
    log_master(f"[Master] Game: {game_name}, Devices: {devices or 'all'}, Auto-start bots: {not args.no_auto_start_bot}")

    # Create bot manager
    manager = MasterBotManager(
        game_name=game_name,
        config=config,
        function_map=function_map,
        command_handlers=command_handlers,
        do_recover_func=do_recover_func,
        findimg_path=findimg_path,
        devices=devices
    )

    # Track socketio instance for clean shutdown
    socketio_instance = None
    shutdown_count = 0

    # Setup signal handlers
    def signal_handler(sig, frame):
        nonlocal shutdown_count
        shutdown_count += 1

        if shutdown_count == 1:
            log_master("[Master] Shutdown signal received, cleaning up...")
            manager.shutdown()
            log_master("[Master] Shutdown complete. Exiting...")
            # Use os._exit() to force immediate termination
            # socketio.stop() requires request context which isn't available in signal handlers
            os._exit(0)
        elif shutdown_count >= 2:
            # Force exit on second Ctrl+C (shouldn't reach here normally)
            log_master("\n[Master] Force exit...")
            os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run web server or CLI mode
    if args.no_web:
        # Auto-start bots in CLI mode (no web callbacks needed)
        if not args.no_auto_start_bot:
            log_master("[Master] Auto-starting all bots...")
            manager.start_all()

        log_master("[Master] Running in CLI-only mode. Press Ctrl+C to exit.")
        try:
            while not manager._shutdown:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    else:
        app, socketio = create_web_server(manager, config)
        socketio_instance = socketio

        # Auto-start bots AFTER web server is created (so log callbacks are registered)
        if not args.no_auto_start_bot:
            log_master("[Master] Auto-starting all bots...")
            manager.start_all()

        log_master(f"[WebServer] Server accessible at: http://localhost:{args.port}")
        log_master("[WebServer] Press Ctrl+C to stop")

        try:
            socketio.run(app, host='0.0.0.0', port=args.port, debug=False,
                        allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            pass

    manager.shutdown()


if __name__ == '__main__':
    main()
