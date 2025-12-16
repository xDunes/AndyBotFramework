"""
Bot Controller - Manages bot lifecycle independent of GUI

This module provides a controller that can run the bot with or without a GUI.
It handles starting, stopping, and monitoring the bot thread.

Usage:
    # With GUI
    controller = BotController(config, function_map, ...)
    controller.set_gui(gui)
    controller.start()

    # Headless
    controller = BotController(config, function_map, ...)
    controller.start()
    controller.wait()  # Block until stopped
"""

import threading
import time
from typing import Optional, Callable, Dict, Any

from .bot import BOT, BotStoppedException
from .android import Android, AndroidStoppedException
from .config_loader import get_serial


class BotController:
    """Controls bot lifecycle - can run with or without GUI"""

    def __init__(
        self,
        device_name: str,
        config: Dict[str, Any],
        function_map: Dict[str, Callable],
        command_handlers: Optional[Dict[str, Callable]] = None,
        do_recover_func: Optional[Callable] = None,
        findimg_path: Optional[str] = None
    ):
        """Initialize bot controller

        Args:
            device_name: Device name from config
            config: Configuration dictionary
            function_map: Dict mapping function names to callables
            command_handlers: Optional dict mapping command IDs to handlers
            do_recover_func: Optional function for fix/recover operations
            findimg_path: Path to findimg folder containing needle images
        """
        self.device_name = device_name
        self.config = config
        self.function_map = function_map
        self.command_handlers = command_handlers or {}
        self.do_recover_func = do_recover_func
        self.findimg_path = findimg_path

        # State
        self.is_running = False
        self.bot_thread: Optional[threading.Thread] = None
        self.bot: Optional[BOT] = None
        self.andy: Optional[Android] = None

        # Optional GUI reference
        self.gui = None

        # Callbacks for state changes (GUI can register these)
        self.on_started: Optional[Callable] = None
        self.on_stopped: Optional[Callable] = None
        self.on_log: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def set_gui(self, gui):
        """Set GUI reference for logging and state updates

        Args:
            gui: BotGUI instance (optional)
        """
        self.gui = gui

    def log(self, message: str):
        """Log a message through GUI or callback"""
        if self.gui and hasattr(self.gui, 'log'):
            self.gui.log(message)
        elif self.on_log:
            self.on_log(message)
        else:
            print(f"[Bot] {message}")

    def start(self):
        """Start the bot in a background thread"""
        if self.is_running:
            return

        self.is_running = True

        self.bot_thread = threading.Thread(
            target=self._run_bot_loop,
            daemon=True,
            name=f"BotLoop-{self.device_name}"
        )
        self.bot_thread.start()

        if self.on_started:
            self.on_started()

    def stop(self):
        """Stop the bot"""
        self.is_running = False

        # Bot and andy references are set on GUI by bot_loop
        if self.gui:
            if hasattr(self.gui, 'bot') and self.gui.bot is not None:
                self.gui.bot.should_stop = True
            if hasattr(self.gui, 'andy') and self.gui.andy is not None:
                self.gui.andy.stop()

        if self.on_stopped:
            self.on_stopped()

    def wait(self, timeout: Optional[float] = None):
        """Wait for bot thread to finish

        Args:
            timeout: Optional timeout in seconds
        """
        if self.bot_thread and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=timeout)

    def _run_bot_loop(self):
        """Main bot execution loop - runs in background thread"""
        from .bot_loop import run_bot_loop

        # Pass GUI if available, otherwise use self as a minimal interface
        gui_or_self = self.gui if self.gui else self

        try:
            run_bot_loop(
                gui_or_self,
                self.function_map,
                self.config,
                self.command_handlers,
                self.do_recover_func,
                self.findimg_path
            )
        except BotStoppedException:
            self.log("Bot stopped")
        except AndroidStoppedException as e:
            self.log(f"Android connection stopped: {e}")
        except Exception as e:
            self.log(f"Bot error: {e}")
            if self.on_error:
                self.on_error(str(e))
        finally:
            self.is_running = False
            if self.on_stopped:
                self.on_stopped()

    # Minimal interface for headless operation (bot_loop expects these)
    def get_checkbox(self, func_name: str) -> bool:
        """Get function enabled state - for headless, check config or return True"""
        if self.gui:
            return self.gui.get_checkbox(func_name)
        # Headless: could read from config or default to enabled
        return True

    def update_status(self, status: str, message: str = ""):
        """Update status display"""
        if self.gui:
            self.gui.update_status(status, message)
        else:
            self.log(f"Status: {status} {message}")

    def update_action(self, action: str):
        """Update current action display"""
        if self.gui:
            self.gui.update_action(action)
