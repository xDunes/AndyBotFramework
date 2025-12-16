"""
BotGUI - Generic config-driven GUI for game bots

This module provides a tkinter-based GUI that reads all configuration
from master.conf and game-specific .conf files, making it reusable for any game.

Key features:
- Function checkboxes built from game.conf function_layout
- Commands built from game.conf commands
- Bot settings built from game.conf bot_settings
- Device list from master.conf devices
"""

import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime

from core.config_loader import load_config, get_serial
from core.state_manager import StateManager
from core.log_database import LogDatabase
from core.ldplayer import LDPlayer


class BotGUI:
    """Generic GUI class for bot interface - config-driven"""

    def __init__(self, root, device_name, config=None):
        """Initialize BotGUI with window and widgets

        Args:
            root: tkinter.Tk root window
            device_name: Device name from config
            config: Optional config dict (loads from file if not provided)
        """
        self.root = root
        self.device_name = device_name
        self.config = config or load_config()

        # Bot controller reference (set via set_controller)
        self.controller = None

        # Set window title from config
        app_name = self.config.get('app_name', 'Bot')
        self.root.title(f"{app_name} - {device_name}")

        # Calculate window position based on device order
        self._setup_window_position()

        # Initialize function states from config
        self.function_states = {}
        self._init_function_states()

        # Special function states
        self.fix_enabled = tk.BooleanVar(value=True)

        # Settings (can be made config-driven)
        self.sleep_time = tk.StringVar(value="1")
        self.studio_stop = tk.StringVar(value="6")
        self.screenshot_interval = tk.StringVar(value="0")
        self.debug = tk.BooleanVar(value=False)

        # Bot state
        self.is_running = False
        self.bot_thread = None
        self.bot = None
        self.andy = None
        self.device = device_name

        # Screenshot state
        self.screenshot_running = False
        self.screenshot_thread = None
        self.live_screenshot_running = False
        self.live_screenshot_thread = None

        # Remote monitoring
        self.remote_monitoring_running = False
        self.remote_monitoring_thread = None

        # Log buffer
        self.log_buffer = []
        self.detailed_log_buffer = []
        self.cooldown_labels = {}
        self.max_log_lines = 300
        self.user_scrolling = False

        # Cooldown tracking
        self.last_run_times = {}

        # Command triggers
        self.command_triggers = self._init_command_triggers()

        # Debug logging
        self.log_db = None
        if self.debug.get():
            self.log_db = LogDatabase(self.device_name)

        # State manager
        self.state_manager = StateManager(self.device_name)
        self._state_update_counter = 0

        self.create_widgets()

        # Check LD status on startup
        self._check_ld_status()
        self._update_status_label()

    def _setup_window_position(self):
        """Calculate and set window position based on device order"""
        device_list = list(self.config.get('devices', {}).keys())
        try:
            position = device_list.index(self.device_name) + 1
        except ValueError:
            position = 1

        x_pos = (position - 1) * 573
        y_pos = 1030
        win_width = 573
        win_height = 330

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        if x_pos + win_width > screen_width or y_pos + win_height > screen_height or x_pos < 0 or y_pos < 0:
            self.root.geometry(f"{win_width}x{win_height}")
        else:
            self.root.geometry(f"{win_width}x{win_height}+{x_pos}+{y_pos}")
        self.root.resizable(False, False)

    def _init_function_states(self):
        """Initialize function states from config function_layout"""
        function_layout = self.config.get('function_layout', [])
        for row in function_layout:
            for func_name in row:
                var = tk.BooleanVar(value=False)
                # Add trace to update state manager when checkbox changes
                var.trace_add('write', lambda *args, name=func_name: self._on_checkbox_change(name))
                self.function_states[func_name] = var

    def _on_checkbox_change(self, func_name):
        """Called when a function checkbox is toggled"""
        try:
            self._update_full_state()
        except Exception:
            pass

    def _init_command_triggers(self):
        """Initialize command triggers from config"""
        triggers = {}
        commands = self.config.get('commands', [])
        for command in commands:
            command_id = command.get('id', '')
            if command_id and command_id != 'start_stop':
                triggers[command_id] = False
        return triggers

    def _get_timestamp(self, detailed=False):
        """Get formatted timestamp for logs"""
        now = datetime.now()
        if detailed:
            return now.strftime("%H:%M:%S.%f")[:-3]
        return now.strftime("%H:%M:%S")

    def create_widgets(self):
        """Create all GUI widgets and layout the interface"""
        # Top bar with device name and status
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=3, pady=1)

        ttk.Label(top_frame, text=f"Device: {self.device_name}",
                  font=("Arial", 9, "bold")).pack(side="left")

        # Settings button
        self.settings_button = ttk.Button(top_frame, text="...", width=3,
                                          command=self.show_settings_dialog)
        self.settings_button.pack(side="right", padx=(0, 2))

        # Status labels
        status_frame = ttk.Frame(top_frame)
        status_frame.pack(side="right")

        ttk.Label(status_frame, text="LD: ", font=("Arial", 8)).pack(side="left")
        self.status_ld_label = ttk.Label(status_frame, text="?", foreground="red", font=("Arial", 8))
        self.status_ld_label.pack(side="left")

        ttk.Label(status_frame, text=" Bot: ", font=("Arial", 8)).pack(side="left")
        self.status_bot_label = ttk.Label(status_frame, text="Stopped", foreground="red", font=("Arial", 8))
        self.status_bot_label.pack(side="left")

        self.ld_running_state = False

        # Current action label
        self.current_action_label = ttk.Label(self.root, text="", font=("Arial", 7))
        self.current_action_label.pack(pady=0)

        # Top content frame
        top_content_frame = ttk.Frame(self.root)
        top_content_frame.pack(fill="x", padx=3, pady=1)

        # Left side - Functions
        left_column = ttk.Frame(top_content_frame)
        left_column.pack(side="left", fill="both", expand=True)

        self._create_functions_section(left_column)
        self._create_commands_section(left_column)

        # Right side - Controls
        self._create_controls_section(top_content_frame)

        # Bottom - Log window
        self._create_log_section()

    def _create_functions_section(self, parent):
        """Create the functions checkboxes section from config"""
        functions_frame = ttk.LabelFrame(parent, text="Functions", padding=1)
        functions_frame.pack(fill="x", padx=1)

        row_layout = self.config.get('function_layout', [])

        for row_items in row_layout:
            row_frame = ttk.Frame(functions_frame)
            row_frame.pack(fill="x", padx=1, pady=1)

            for func_name in row_items:
                if func_name in self.function_states:
                    var = self.function_states[func_name]

                    # Create display label by removing "do" prefix
                    if func_name.startswith('do'):
                        display_name = func_name[2:]
                    else:
                        display_name = func_name

                    item_frame = ttk.Frame(row_frame)
                    item_frame.pack(side="left", padx=2, pady=0)

                    cb = ttk.Checkbutton(item_frame, text=display_name, variable=var)
                    cb.pack(side="left")

                    cooldown_label = ttk.Label(item_frame, text="", foreground="gray")
                    cooldown_label.pack(side="left", padx=(2, 0))
                    self.cooldown_labels[func_name] = cooldown_label

    def _create_controls_section(self, parent):
        """Create the control buttons section"""
        right_frame = ttk.Frame(parent)
        right_frame.pack(side="right", fill="y", padx=1)

        controls_frame = ttk.LabelFrame(right_frame, text="Controls", padding=2)
        controls_frame.pack(fill="x", pady=1)

        # Debug and Fix checkboxes
        debug_fix_frame = ttk.Frame(controls_frame)
        debug_fix_frame.pack(fill="x", pady=1)
        ttk.Checkbutton(debug_fix_frame, text="Debug",
                        variable=self.debug).pack(side="left")
        ttk.Checkbutton(debug_fix_frame, text="Fix",
                        variable=self.fix_enabled).pack(side="left", padx=(10, 0))

        # Screenshot button
        screenshot_button_frame = ttk.Frame(controls_frame)
        screenshot_button_frame.pack(fill="x", pady=(4, 1))
        self.screenshot_button = ttk.Button(screenshot_button_frame, text="Screenshot",
                                            command=self.toggle_screenshot)
        self.screenshot_button.pack(fill="x")

        # LDPlayer button
        ldplayer_button_frame = ttk.Frame(controls_frame)
        ldplayer_button_frame.pack(fill="x", pady=(1, 1))
        self.ldplayer_button = ttk.Button(ldplayer_button_frame, text="LDPlayer",
                                          command=self.show_ldplayer_dialog)
        self.ldplayer_button.pack(fill="x")

        # Logs button
        open_log_button_frame = ttk.Frame(controls_frame)
        open_log_button_frame.pack(fill="x", pady=(1, 1))
        self.open_log_button = ttk.Button(open_log_button_frame, text="Logs",
                                          command=self.open_log_viewer)
        self.open_log_button.pack(fill="x")

        # Start/Stop button
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill="x", pady=(1, 2))
        self.toggle_button = ttk.Button(button_frame, text="Start", command=self.toggle_bot)
        self.toggle_button.pack(fill="x")

    def _create_commands_section(self, parent):
        """Create commands section from config"""
        commands_frame = ttk.LabelFrame(parent, text="Commands", padding=2)
        commands_frame.pack(fill="x", padx=1, pady=(2, 0))

        button_row = ttk.Frame(commands_frame)
        button_row.pack(fill="x")

        commands = self.config.get('commands', [])
        for command in commands:
            command_id = command.get('id', '')
            label = command.get('label', command_id)

            if command_id == 'start_stop':
                continue  # Skip start/stop, it's handled separately

            # Create button for this command
            btn = ttk.Button(button_row, text=label,
                             command=lambda cid=command_id: self._trigger_command(cid))
            btn.pack(side="left", padx=2, pady=1)

    def _trigger_command(self, command_id):
        """Trigger a command by ID"""
        if command_id in self.command_triggers:
            self.command_triggers[command_id] = True
            self.log(f"{command_id} command triggered")

    def _create_log_section(self):
        """Create the log window section"""
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=1)
        log_frame.pack(fill="both", expand=True, padx=3, pady=1)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_container, height=1, width=1, wrap=tk.WORD,
                                font=("Courier", 8), state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_container, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Track user scrolling
        self.log_text.bind("<MouseWheel>", self._on_user_scroll)
        self.log_text.bind("<Button-4>", self._on_user_scroll)
        self.log_text.bind("<Button-5>", self._on_user_scroll)

    def _on_user_scroll(self, _event):
        """Track when user manually scrolls the log window"""
        self.root.after(100, self._check_scroll_position)

    def _check_scroll_position(self):
        """Check if user has scrolled away from bottom"""
        try:
            yview = self.log_text.yview()
            self.user_scrolling = yview[1] < 0.99
        except:
            pass

    def log(self, message, screenshot=None):
        """Add a log message to the log window

        This handles the actual GUI logging. External code should call
        core.utils.log() which will delegate here for GUI updates.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"

        self.log_buffer.append(formatted_message)

        # Maintain buffer size
        while len(self.log_buffer) > self.max_log_lines:
            self.log_buffer.pop(0)

        # Update log widget (thread-safe)
        self.root.after(0, self._update_log_widget)

        # Log to state manager for web interface
        if self.state_manager:
            self.state_manager.add_log(message, screenshot)

        # Log to database if debug enabled
        if self.log_db and self.debug.get():
            self.log_db.add_log_entry(message, screenshot)

    def _update_log_widget(self):
        """Update the log text widget with current buffer"""
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, "\n".join(self.log_buffer))
            self.log_text.config(state=tk.DISABLED)

            # Auto-scroll to bottom unless user is scrolling
            if not self.user_scrolling:
                self.log_text.see(tk.END)
        except:
            pass

    def update_status(self, status, action=""):
        """Update status labels and current action"""
        def _update():
            if status == "Running":
                self.status_bot_label.config(text="Running", foreground="green")
            elif status == "Stopped":
                self.status_bot_label.config(text="Stopped", foreground="red")
            elif status == "Error":
                self.status_bot_label.config(text="Error", foreground="orange")

            self.current_action_label.config(text=action)

        self.root.after(0, _update)

    def set_controller(self, controller):
        """Set the bot controller reference

        Args:
            controller: BotController instance
        """
        self.controller = controller

    def toggle_bot(self):
        """Toggle bot running state"""
        if self.is_running:
            self.stop_bot()
        else:
            self.start_bot()

    def start_bot(self):
        """Start the bot via controller"""
        if self.is_running or not self.controller:
            return

        self.is_running = True
        self.toggle_button.config(text="Stop")
        self._check_ld_status()
        self._update_status_label()

        # Start via controller
        self.controller.start()

        # Start live screenshot updater for remote monitoring
        self.start_live_screenshot_updater()

        # Update state
        self._update_full_state()

    def stop_bot(self):
        """Stop the bot via controller"""
        self.is_running = False

        if self.controller:
            self.controller.stop()

        # Stop command queue if running
        if self.bot:
            self.bot.stop_command_queue()

        self.stop_live_screenshot_updater()
        self.toggle_button.config(text="Start")
        self._update_status_label()
        self.current_action_label.config(text="Action: None")
        self.log("Stop button pressed - halting execution")
        self._update_full_state()

    def get_checkbox(self, func_name):
        """Get checkbox state for a function"""
        if func_name in self.function_states:
            return self.function_states[func_name].get()
        return False

    def toggle_screenshot(self):
        """Toggle screenshot capture on/off

        Two modes based on screenshot_interval setting:
        - Interval = 0: Takes single screenshot and opens in MS Paint
        - Interval > 0: Continuously captures screenshots at specified interval
        """
        if self.screenshot_running:
            # Stop screenshot capture
            self.screenshot_running = False
            self.screenshot_button.config(text="Screenshot")
            self.log("Screenshot capture stopped")
        else:
            # Start screenshot capture
            self.screenshot_running = True
            self.screenshot_button.config(text="Stop Screenshot")
            self.screenshot_thread = threading.Thread(target=self._capture_screenshots, daemon=True)
            self.screenshot_thread.start()
            self.log("Screenshot capture started")

    def _capture_screenshots(self):
        """Capture screenshots in a separate thread"""
        import os
        import time
        import subprocess
        from core.android import Android
        try:
            # Get interval
            try:
                interval = float(self.screenshot_interval.get())
            except ValueError:
                interval = 0

            # Create screenshots directory
            screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            # Get device serial
            device = self.device_name
            serial = get_serial(device)

            if not serial:
                self.log("ERROR: Cannot get device serial for screenshots")
                self.screenshot_running = False
                self.root.after(0, lambda: self.screenshot_button.config(text="Screenshot"))
                return

            # Connect to device
            screenshot_andy = Android(serial)

            # Single or continuous capture
            if interval == 0:
                # Single capture - save and open in mspaint
                filepath = self._save_screenshot(screenshot_andy, device, screenshot_dir)
                if filepath:
                    # Open the screenshot in MS Paint
                    subprocess.Popen(['mspaint', filepath])
                    self.log(f"Opened in MS Paint: {os.path.basename(filepath)}")
                self.screenshot_running = False
                self.root.after(0, lambda: self.screenshot_button.config(text="Screenshot"))
            else:
                # Continuous capture
                while self.screenshot_running:
                    self._save_screenshot(screenshot_andy, device, screenshot_dir)
                    if self.screenshot_running:  # Check again before sleeping
                        time.sleep(interval)

        except Exception as e:
            self.log(f"Screenshot ERROR: {e}")
            self.screenshot_running = False
            self.root.after(0, lambda: self.screenshot_button.config(text="Screenshot"))

    def _save_screenshot(self, andy, device, screenshot_dir):
        """Save a single screenshot with timestamp

        Args:
            andy: Android instance
            device: Device name for filename
            screenshot_dir: Directory to save screenshots

        Returns:
            str: Filepath of saved screenshot, or None if error
        """
        import os
        import cv2 as cv

        try:
            screenshot = andy.capture_screen()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{device}_{timestamp}.png"
            filepath = os.path.join(screenshot_dir, filename)
            cv.imwrite(filepath, screenshot)
            self.log(f"Screenshot saved: {filename}")
            return filepath
        except Exception as e:
            self.log(f"Error saving screenshot: {e}")
            return None

    def show_settings_dialog(self):
        """Show settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("250x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        # Sleep time
        sleep_frame = ttk.Frame(frame)
        sleep_frame.pack(fill="x", pady=5)
        ttk.Label(sleep_frame, text="Bot loop sleep (s):").pack(side="left")
        ttk.Entry(sleep_frame, textvariable=self.sleep_time, width=8).pack(side="right")

        # Screenshot interval
        screenshot_frame = ttk.Frame(frame)
        screenshot_frame.pack(fill="x", pady=5)
        ttk.Label(screenshot_frame, text="Screenshot interval (s):").pack(side="left")
        ttk.Entry(screenshot_frame, textvariable=self.screenshot_interval, width=8).pack(side="right")

        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=10)
        dialog.focus_set()

    def show_ldplayer_dialog(self):
        """Show LDPlayer controls dialog"""
        device_config = self.config.get('devices', {}).get(self.device_name, {})
        index = device_config.get('index', 0)
        app_package = self.config.get('app_package', '')

        dialog = tk.Toplevel(self.root)
        dialog.title("LDPlayer Controls")
        dialog.geometry("300x320")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill="both", expand=True)

        status_var = tk.StringVar(value=f"Device: {self.device_name}")
        ttk.Label(main_frame, textvariable=status_var, font=("Arial", 8)).pack(fill="x", pady=(0, 10))

        device_frame = ttk.LabelFrame(main_frame, text="Device", padding=5)
        device_frame.pack(fill="x", pady=5)

        device_buttons = ttk.Frame(device_frame)
        device_buttons.pack(fill="x")

        def on_start():
            try:
                ld = LDPlayer.from_config()
                ld.launch(index=index)
                status_var.set(f"Started {self.device_name}")
            except Exception as e:
                status_var.set(f"Error: {e}")

        def on_stop():
            try:
                ld = LDPlayer.from_config()
                ld.quit(index=index)
                status_var.set(f"Stopped {self.device_name}")
            except Exception as e:
                status_var.set(f"Error: {e}")

        def on_reboot():
            try:
                ld = LDPlayer.from_config()
                ld.reboot(index=index)
                status_var.set(f"Rebooting {self.device_name}")
            except Exception as e:
                status_var.set(f"Error: {e}")

        ttk.Button(device_buttons, text="Start", command=on_start, width=8).pack(side="left", padx=2)
        ttk.Button(device_buttons, text="Stop", command=on_stop, width=8).pack(side="left", padx=2)
        ttk.Button(device_buttons, text="Reboot", command=on_reboot, width=8).pack(side="left", padx=2)

        app_frame = ttk.LabelFrame(main_frame, text="App", padding=5)
        app_frame.pack(fill="x", pady=5)

        ttk.Label(app_frame, text=f"Package: {app_package}", font=("Arial", 7)).pack(anchor="w")

        app_buttons = ttk.Frame(app_frame)
        app_buttons.pack(fill="x", pady=(5, 0))

        def on_start_app():
            if not app_package:
                status_var.set("No app_package in config")
                return
            try:
                ld = LDPlayer.from_config()
                ld.run_app(app_package, index=index)
                status_var.set(f"Started app")
            except Exception as e:
                status_var.set(f"Error: {e}")

        def on_stop_app():
            if not app_package:
                status_var.set("No app_package in config")
                return
            try:
                ld = LDPlayer.from_config()
                ld.kill_app(app_package, index=index)
                status_var.set(f"Stopped app")
            except Exception as e:
                status_var.set(f"Error: {e}")

        ttk.Button(app_buttons, text="Start App", command=on_start_app, width=12).pack(side="left", padx=2)
        ttk.Button(app_buttons, text="Stop App", command=on_stop_app, width=12).pack(side="left", padx=2)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        dialog.focus_set()

    def open_log_viewer(self):
        """Open LogViewer.py with current device and session selected

        Launches the LogViewer application in a separate process, automatically
        selecting the current device and session (if debug mode is active).
        """
        import subprocess
        import sys
        import os

        # Get the path to LogViewer.py (in tools/ directory)
        log_viewer_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools', 'LogViewer.py')

        if not os.path.exists(log_viewer_path):
            self.log("ERROR: LogViewer.py not found")
            return

        # Get current session from database
        current_session = None
        if self.log_db:
            current_session = self.log_db.session_id

        # Build command
        cmd = [sys.executable, log_viewer_path, self.device_name]
        if current_session:
            cmd.append(str(current_session))

        # Launch as separate process
        subprocess.Popen(cmd)
        self.log(f"Opening Log Viewer for {self.device_name}...")

    def _on_settings_change(self, *args):
        """Called when settings change"""
        self._update_full_state()

    def _check_ld_status(self):
        """Check LDPlayer running status"""
        try:
            device_config = self.config.get('devices', {}).get(self.device_name, {})
            index = device_config.get('index', 0)
            ld = LDPlayer.from_config()
            self.ld_running_state = ld.is_running(index=index)
            if hasattr(self, 'state_manager'):
                self.state_manager.update_ld_running(self.ld_running_state)
        except Exception:
            pass

    def _update_status_label(self):
        """Update the LD and Bot status labels"""
        ld_text = "Running" if self.ld_running_state else "Stopped"
        ld_color = "green" if self.ld_running_state else "red"
        self.status_ld_label.config(text=ld_text, foreground=ld_color)

        bot_text = "Running" if self.is_running else "Stopped"
        bot_color = "green" if self.is_running else "red"
        self.status_bot_label.config(text=bot_text, foreground=bot_color)

    def _update_full_state(self):
        """Update full state to state manager"""
        try:
            state = {
                'is_running': self.is_running,
                'debug_enabled': self.debug.get(),
                'fix_enabled': self.fix_enabled.get(),
                'sleep_time': float(self.sleep_time.get()) if self.sleep_time.get() else 1.0,
            }

            # Add all function states
            for func_name, var in self.function_states.items():
                state[func_name] = var.get()

            self.state_manager.update_state(state)
        except Exception:
            pass

    def start_live_screenshot_updater(self):
        """Start background thread to update screenshots for remote monitoring"""
        if self.live_screenshot_running:
            return

        self.live_screenshot_running = True
        import time

        def screenshot_update_loop():
            ld_check_counter = 0
            while self.live_screenshot_running:
                try:
                    if self.is_running and self.andy is not None and hasattr(self, 'state_manager'):
                        screenshot = self.andy.capture_screen()
                        if screenshot is not None:
                            self.state_manager.update_screenshot(screenshot)
                except Exception as e:
                    # Log screenshot errors periodically (not every loop)
                    if ld_check_counter == 0:
                        print(f"[Screenshot] Error: {e}")

                ld_check_counter += 1
                if ld_check_counter >= 20:
                    ld_check_counter = 0
                    try:
                        self._check_ld_status()
                        self.root.after(0, self._update_status_label)
                    except Exception:
                        pass

                time.sleep(0.5)

        self.live_screenshot_thread = threading.Thread(
            target=screenshot_update_loop,
            daemon=True,
            name=f"LiveScreenshot-{self.device_name}"
        )
        self.live_screenshot_thread.start()

    def stop_live_screenshot_updater(self):
        """Stop the live screenshot updater"""
        self.live_screenshot_running = False
        if self.live_screenshot_thread:
            self.live_screenshot_thread.join(timeout=1.0)

    def start_remote_monitoring(self):
        """Start background thread to monitor remote commands"""
        if self.remote_monitoring_running:
            return

        self.remote_monitoring_running = True
        import time

        def remote_monitor_loop():
            while self.remote_monitoring_running:
                try:
                    if hasattr(self, 'state_manager'):
                        commands = self.state_manager.get_pending_commands()
                        for cmd in commands:
                            try:
                                self._process_remote_command(cmd)
                            except Exception:
                                pass
                            finally:
                                try:
                                    self.state_manager.mark_command_processed(cmd['id'])
                                except Exception:
                                    pass
                except Exception:
                    pass
                time.sleep(0.25)

        self.remote_monitoring_thread = threading.Thread(
            target=remote_monitor_loop,
            daemon=True,
            name=f"RemoteMonitor-{self.device_name}"
        )
        self.remote_monitoring_thread.start()

    def stop_remote_monitoring(self):
        """Stop the remote monitoring thread"""
        self.remote_monitoring_running = False
        if self.remote_monitoring_thread:
            self.remote_monitoring_thread.join(timeout=1.0)

    def _set_checkbox(self, name, enabled):
        """Set a checkbox value and update state (called from main thread)"""
        if name in self.function_states:
            self.function_states[name].set(enabled)
            self.log(f"Remote: {name} set to {enabled}")
            self._update_full_state()

    def _set_setting(self, name, value):
        """Set a setting value and update state (called from main thread)"""
        if name == 'sleep_time':
            self.sleep_time.set(str(value))
        elif name == 'debug_enabled':
            self.debug.set(bool(value))
        elif name == 'fix_enabled':
            self.fix_enabled.set(bool(value))
        self._update_full_state()

    def _execute_remote_tap(self, x, y):
        """Execute a remote tap command via queue for serialized execution"""
        if self.bot:
            self.bot.queue_command(
                lambda b=self.bot, tx=x, ty=y: b.tap(tx, ty),
                f"Remote: Tap at ({x}, {y})"
            )

    def _execute_remote_swipe(self, x1, y1, x2, y2, duration=500):
        """Execute a remote swipe command via queue for serialized execution"""
        if self.bot:
            self.bot.queue_command(
                lambda b=self.bot, a=x1, c=y1, d=x2, e=y2, f=duration: b.swipe(a, c, d, e, duration=f),
                f"Remote: Swipe ({x1},{y1})->({x2},{y2})"
            )

    def _process_remote_command(self, cmd):
        """Process a single remote command"""
        cmd_type = cmd.get('command_type')
        cmd_data = cmd.get('command_data', {})

        if cmd_type == 'checkbox' and cmd_data:
            checkbox_name = cmd_data.get('name')
            enabled = cmd_data.get('enabled')
            if checkbox_name in self.function_states:
                # Use root.after for thread-safe tkinter update
                self.root.after(0, lambda n=checkbox_name, e=enabled: self._set_checkbox(n, e))

        elif cmd_type == 'setting' and cmd_data:
            setting_name = cmd_data.get('name')
            value = cmd_data.get('value')
            # Use root.after for thread-safe tkinter update
            self.root.after(0, lambda s=setting_name, v=value: self._set_setting(s, v))

        elif cmd_type == 'tap' and cmd_data and self.is_running and self.bot:
            x, y = cmd_data.get('x'), cmd_data.get('y')
            if x is not None and y is not None:
                # Queue tap for serialized execution
                self._execute_remote_tap(x, y)

        elif cmd_type == 'swipe' and cmd_data and self.is_running and self.bot:
            x1, y1 = cmd_data.get('x1'), cmd_data.get('y1')
            x2, y2 = cmd_data.get('x2'), cmd_data.get('y2')
            duration = cmd_data.get('duration', 500)  # Default 500ms if not provided
            if all(v is not None for v in [x1, y1, x2, y2]):
                # Queue swipe for serialized execution
                self._execute_remote_swipe(x1, y1, x2, y2, duration)

        elif cmd_type == 'stop_bot' and self.is_running:
            self.root.after(0, self.toggle_bot)

        elif cmd_type == 'start_bot' and not self.is_running:
            self.root.after(0, self.toggle_bot)

        elif cmd_type == 'assist_command' and cmd_data:
            command_name = cmd_data.get('name')
            if command_name in self.command_triggers:
                self.command_triggers[command_name] = True

        elif cmd_type in ('ld_start', 'ld_stop', 'ld_reboot', 'app_start', 'app_stop'):
            self._handle_ld_command(cmd_type)

    def _handle_ld_command(self, cmd_type):
        """Handle LDPlayer commands"""
        try:
            device_config = self.config.get('devices', {}).get(self.device_name, {})
            index = device_config.get('index', 0)
            ld = LDPlayer.from_config()
            app_package = self.config.get('app_package', '')

            if cmd_type == 'ld_start':
                ld.launch(index=index)
            elif cmd_type == 'ld_stop':
                ld.quit(index=index)
            elif cmd_type == 'ld_reboot':
                ld.reboot(index=index)
            elif cmd_type == 'app_start' and app_package:
                ld.run_app(app_package, index=index)
            elif cmd_type == 'app_stop' and app_package:
                ld.kill_app(app_package, index=index)
        except Exception as e:
            self.log(f"LD command error: {e}")

    def run(self):
        """Start the GUI main loop"""
        self.start_remote_monitoring()
        self.root.mainloop()
