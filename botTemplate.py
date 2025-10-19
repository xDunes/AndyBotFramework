"""
Bot Template - Minimal bot framework for easy customization

Provides core bot functionality including:
- Configuration loading from config.json
- GUI with logging, start/stop, and screenshot
- Bot execution loop with cooldown system
- Example do_helloworld function

Usage:
    python botTemplate.py <username>

Example:
    python botTemplate.py Device1
"""

from android import Android
from bot import BOT, BotStoppedException
import time
import sys
import random
import json
import os
import tkinter as tk
from tkinter import ttk
import threading
import cv2 as cv
from datetime import datetime

# ============================================================================
# GLOBAL STATE
# ============================================================================
andy = None
bot = None
bot_running = False
gui_root = None
gui_instance = None

# Cached configuration to avoid repeated file I/O
_cached_config = None


# ============================================================================
# LOGGING HELPER
# ============================================================================

def log(message):
    """Log message to GUI if available, otherwise print to console

    Args:
        message: Message string to log

    Note:
        Uses global gui_instance if available, falls back to console print
    """
    global gui_instance
    if gui_instance:
        gui_instance.log(message)
    else:
        print(message)


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def load_config():
    """Load configuration from config.json (with caching)

    Returns:
        dict: Configuration dictionary

    Note:
        Caches config to avoid repeated file reads
    """
    global _cached_config
    if _cached_config is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            _cached_config = json.load(f)
    return _cached_config


def get_device_config(user):
    """Get device configuration for a specific user

    Args:
        user: Username key from config.json

    Returns:
        dict: Device configuration

    Raises:
        KeyError: If user not found in config
    """
    config = load_config()
    devices = config.get('devices', {})
    if user not in devices:
        raise KeyError(f"Unknown user: {user}")
    return devices[user]


def get_serial(user):
    """Get device serial for a user

    Args:
        user: Username from config

    Returns:
        str: Device serial number
    """
    return get_device_config(user)["serial"]


def format_cooldown_time(seconds):
    """Format cooldown time in condensed format

    Args:
        seconds: Remaining seconds

    Returns:
        str: Formatted time - rounded to nearest minute until < 60s (e.g., "5m", "3m", "45s")
    """
    if seconds < 60:
        # Less than 1 minute - show seconds only
        return f"{seconds}s"
    else:
        # 1 minute or more - round to nearest minute for space saving
        minutes = round(seconds / 60)
        return f"{minutes}m"


# ============================================================================
# BOT FUNCTIONS
# ============================================================================

def do_helloworld(bot, user):
    """Example function - prints Hello World to log

    This is a template function showing the basic structure.
    Replace with your own bot functions.

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Simple example - just logs a message
    """
    _ = bot, user  # Unused in this example
    log("Hello World!")
    time.sleep(1)  # Simulate some work


# ============================================================================
# GUI CLASS
# ============================================================================

class BotGUI:
    """Main GUI class for the bot interface

    Provides:
    - Function checkboxes for enabling/disabling bot actions
    - Settings panel (sleep time, screenshot interval, etc.)
    - Start/Stop button
    - Screenshot button
    - Log window with auto-scroll
    - Status indicators
    """

    def __init__(self, root, username):
        """Initialize BotGUI with window and widgets

        Args:
            root: tkinter.Tk root window
            username: Device username from config

        Note:
            Window position is calculated based on device order in config
            to arrange multiple bot windows horizontally on screen
        """
        self.root = root
        self.username = username
        self.root.title(f"Bot Template - {username}")

        # Calculate window position based on device order in config.json
        # This arranges multiple bot windows horizontally across the screen
        config = load_config()
        device_list = list(config.get('devices', {}).keys())
        try:
            position = device_list.index(username) + 1
        except ValueError:
            position = 1

        # Position windows side-by-side: 573px wide each, at y=1030
        x_pos = (position - 1) * 573
        y_pos = 1030

        self.root.geometry(f"573x330+{x_pos}+{y_pos}")
        self.root.resizable(False, False)

        # Function enable/disable states - all start unchecked
        self.function_states = {
            'doHelloWorld': tk.BooleanVar(value=False),
        }

        # Settings
        self.sleep_time = tk.StringVar(value="1")
        self.screenshot_interval = tk.StringVar(value="0")
        self.show_no_click = tk.BooleanVar(value=False)

        # Bot state
        self.is_running = False
        self.bot_thread = None

        # Screenshot state
        self.screenshot_running = False
        self.screenshot_thread = None

        # Log buffer
        self.log_buffer = []

        # Cooldown display labels (for functions with cooldowns)
        self.cooldown_labels = {}
        self.max_log_lines = 300
        self.user_scrolling = False

        # Track last run times for cooldown system
        self.last_run_times = {}

        self.create_widgets()

    def create_widgets(self):
        """Create all GUI widgets

        Layout:
        - Top: Username and status
        - Middle: Functions (left) and Settings/Controls (right)
        - Bottom: Log window
        """
        # Top bar with username and status
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=3, pady=1)

        ttk.Label(top_frame, text=f"User: {self.username}",
                 font=("Arial", 9, "bold")).pack(side="left")

        self.status_label = ttk.Label(top_frame, text="Stopped",
                                       foreground="red", font=("Arial", 8))
        self.status_label.pack(side="right")

        # Current action label
        self.current_action_label = ttk.Label(self.root, text="", font=("Arial", 7))
        self.current_action_label.pack(pady=0)

        # Top content frame - Functions and Settings side by side
        top_content_frame = ttk.Frame(self.root)
        top_content_frame.pack(fill="x", padx=3, pady=1)

        # Left side - Functions (4 columns)
        self._create_functions_section(top_content_frame)

        # Right side - Settings and controls
        self._create_controls_section(top_content_frame)

        # Bottom - Log window
        self._create_log_section()

    def _create_functions_section(self, parent):
        """Create the functions checkboxes section

        Args:
            parent: Parent frame widget
        """
        functions_frame = ttk.LabelFrame(parent, text="Functions", padding=1)
        functions_frame.pack(side="left", fill="both", expand=True, padx=1)

        # Define custom row layout
        row_layout = [
            ['doHelloWorld'],
        ]

        # Create rows
        for row_items in row_layout:
            row_frame = ttk.Frame(functions_frame)
            row_frame.pack(fill="x", padx=1, pady=1)

            for func_name in row_items:
                if func_name in self.function_states:
                    var = self.function_states[func_name]

                    # Create display label by removing "do" prefix
                    if func_name.startswith('do'):
                        display_name = func_name[2:]  # Remove "do" prefix
                    else:
                        display_name = func_name

                    # Create frame to hold checkbox and cooldown label together
                    item_frame = ttk.Frame(row_frame)
                    item_frame.pack(side="left", padx=2, pady=0)

                    cb = ttk.Checkbutton(item_frame, text=display_name, variable=var)
                    cb.pack(side="left")

                    # Add cooldown label for functions that have cooldowns
                    cooldown_label = ttk.Label(item_frame, text="", foreground="gray")
                    cooldown_label.pack(side="left", padx=(2, 0))
                    self.cooldown_labels[func_name] = cooldown_label

    def _create_controls_section(self, parent):
        """Create the settings and control buttons section

        Args:
            parent: Parent frame widget
        """
        right_frame = ttk.Frame(parent)
        right_frame.pack(side="right", fill="y", padx=1)

        # Settings
        settings_frame = ttk.LabelFrame(right_frame, text="Settings", padding=2)
        settings_frame.pack(fill="x", pady=1)

        # Sleep time
        sleep_frame = ttk.Frame(settings_frame)
        sleep_frame.pack(fill="x", pady=1)
        ttk.Label(sleep_frame, text="Sleep:", font=("Arial", 7)).pack(anchor="w")
        ttk.Entry(sleep_frame, textvariable=self.sleep_time, width=8).pack(fill="x")

        # Screenshot interval
        screenshot_frame = ttk.Frame(settings_frame)
        screenshot_frame.pack(fill="x", pady=1)
        ttk.Label(screenshot_frame, text="Seconds:", font=("Arial", 7)).pack(anchor="w")
        ttk.Entry(screenshot_frame, textvariable=self.screenshot_interval, width=8).pack(fill="x")

        # Show NO CLICK logs checkbox
        no_click_frame = ttk.Frame(settings_frame)
        no_click_frame.pack(fill="x", pady=1)
        ttk.Checkbutton(no_click_frame, text="Show NO CLICK",
                       variable=self.show_no_click).pack(anchor="w")

        # Control buttons
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill="x", pady=3)

        self.toggle_button = ttk.Button(button_frame, text="Start", command=self.toggle_bot)
        self.toggle_button.pack(fill="x", pady=1)

        # Screenshot button
        self.screenshot_button = ttk.Button(button_frame, text="Screenshot",
                                            command=self.toggle_screenshot)
        self.screenshot_button.pack(fill="x", pady=1)

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
        self.log_text.bind("<MouseWheel>", self.on_user_scroll)
        self.log_text.bind("<Button-4>", self.on_user_scroll)
        self.log_text.bind("<Button-5>", self.on_user_scroll)

    def on_user_scroll(self, _event):
        """Track when user manually scrolls

        Args:
            _event: Scroll event (unused)
        """
        self.root.after(100, self.check_scroll_position)
        return

    def check_scroll_position(self):
        """Check if log is scrolled to bottom

        Updates user_scrolling flag for auto-scroll behavior
        """
        try:
            pos = self.log_text.yview()
            # If at bottom (within small threshold), enable auto-scroll
            self.user_scrolling = pos[1] < 0.99
        except:
            pass

    def log(self, message):
        """Add message to log window with 300 line buffer

        Args:
            message: Message string to log

        Note:
            - Adds timestamp to each message
            - Maintains 300 line buffer (FIFO)
            - Auto-scrolls only if user hasn't manually scrolled up
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"

        self.log_buffer.append(log_msg)

        # Keep only last 300 lines (FIFO buffer)
        if len(self.log_buffer) > self.max_log_lines:
            self.log_buffer = self.log_buffer[-self.max_log_lines:]

        # Update text widget
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "\n".join(self.log_buffer))

        # Auto-scroll only if user is at bottom (not manually scrolled up)
        if not self.user_scrolling:
            self.log_text.see(tk.END)

        self.log_text.config(state=tk.DISABLED)

    def update_status(self, status_text, action_text=""):
        """Update status and action labels

        Args:
            status_text: Status text to display (e.g., "Running", "Stopped")
            action_text: Current action description (optional)
        """
        self.status_label.config(text=f"{status_text}")
        if action_text:
            self.current_action_label.config(text=f"Action: {action_text}")

    def toggle_bot(self):
        """Toggle bot on/off

        Starts or stops the bot execution thread. When stopping,
        immediately signals the bot instance to halt execution.

        Note:
            - Sets bot.should_stop flag for immediate stopping
            - Runs bot in daemon thread
            - Updates GUI status indicators
        """
        if self.is_running:
            # Stop the bot immediately
            global bot_running, bot
            self.is_running = False
            bot_running = False

            # Signal the bot instance to stop immediately
            if bot is not None:
                bot.should_stop = True

            self.toggle_button.config(text="Start")
            self.status_label.config(text="Stopped", foreground="red")
            self.current_action_label.config(text="Action: None")
            self.log("Stop button pressed - halting execution")
        else:
            # Start the bot
            self.is_running = True
            self.toggle_button.config(text="Stop")
            self.status_label.config(text="Running", foreground="green")
            self.bot_thread = threading.Thread(target=run_bot_loop, args=(self,), daemon=True)
            self.bot_thread.start()

    def toggle_screenshot(self):
        """Toggle screenshot capture on/off

        Two modes:
        - Single (interval=0): Captures one screenshot and opens in MS Paint
        - Continuous (interval>0): Captures screenshots at specified interval
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
            self.screenshot_thread = threading.Thread(target=self.capture_screenshots, daemon=True)
            self.screenshot_thread.start()
            self.log("Screenshot capture started")

    def capture_screenshots(self):
        """Capture screenshots in a separate thread

        Two modes:
        1. Single capture (interval=0): Takes one screenshot and opens in MS Paint
        2. Continuous capture (interval>0): Takes screenshots at specified interval

        Note:
            - Runs in daemon thread
            - Creates screenshots/ directory automatically
            - Filenames include username and timestamp
        """
        try:
            # Get interval
            try:
                interval = float(self.screenshot_interval.get())
            except ValueError:
                interval = 0

            # Create screenshots directory
            screenshot_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            # Get device serial
            user = sys.argv[1] if len(sys.argv) > 1 else "unknown"
            serial = get_serial(user) if len(sys.argv) > 1 else None

            if not serial:
                self.log("ERROR: Cannot get device serial for screenshots")
                self.screenshot_running = False
                self.screenshot_button.config(text="Screenshot")
                return

            # Connect to device
            screenshot_andy = Android(serial)

            # Single or continuous capture
            if interval == 0:
                # Single capture - save and open in mspaint
                filepath = self._save_screenshot(screenshot_andy, user, screenshot_dir)
                if filepath:
                    # Open the screenshot in MS Paint
                    import subprocess
                    subprocess.Popen(['mspaint', filepath])
                    self.log(f"Opened in MS Paint: {os.path.basename(filepath)}")
                self.screenshot_running = False
                self.screenshot_button.config(text="Screenshot")
            else:
                # Continuous capture
                while self.screenshot_running:
                    self._save_screenshot(screenshot_andy, user, screenshot_dir)
                    if self.screenshot_running:  # Check again before sleeping
                        time.sleep(interval)

        except Exception as e:
            self.log(f"Screenshot ERROR: {e}")
            self.screenshot_running = False
            self.screenshot_button.config(text="Screenshot")

    def _save_screenshot(self, andy, user, screenshot_dir):
        """Save a single screenshot with timestamp

        Args:
            andy: Android instance
            user: Username for filename
            screenshot_dir: Directory to save screenshots

        Returns:
            str: Filepath of saved screenshot, or None if error occurred
        """
        try:
            # Capture screenshot
            screenshot = andy.capture_screen()

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{user}_{timestamp}.png"
            filepath = os.path.join(screenshot_dir, filename)

            # Save screenshot
            cv.imwrite(filepath, screenshot)

            self.log(f"Screenshot saved: {filename}")
            return filepath
        except Exception as e:
            self.log(f"Error saving screenshot: {e}")
            return None


# ============================================================================
# BOT EXECUTION LOOP
# ============================================================================

def run_bot_loop(gui):
    """Main bot execution loop with GUI integration

    Args:
        gui: BotGUI instance

    Note:
        - Loads configuration and connects to device
        - Executes enabled functions in loop
        - Handles cooldowns
        - Catches BotStoppedException for immediate stopping
    """
    global andy, bot, bot_running, gui_instance

    gui_instance = gui

    try:
        user = sys.argv[1]
        andy = Android(get_serial(user))
        andy.set_gui(gui)  # Set GUI for Android logging
        gui.log(f"Connected to device: {user}")
    except Exception as error:
        gui.update_status("Error", f"Error: {error}")
        gui.log(f"ERROR: {error}")
        return

    bot = BOT(andy)
    bot.set_gui(gui)
    bot.should_stop = False  # Reset stop flag when starting
    bot_running = True

    # Function mapping - add your functions here
    function_map = {
        'doHelloWorld': do_helloworld,
    }

    # Functions that should be unchecked after completion
    auto_uncheck = set()

    # Cooldown system - configure cooldowns for functions (in seconds)
    # Set to 0 or omit to disable cooldown for a function
    function_cooldowns = {
        'doHelloWorld': 0,  # No cooldown
    }

    # Track last run time for each function (store in GUI instance)
    gui.last_run_times = {func_name: 0 for func_name in function_map.keys()}

    while gui.is_running and bot_running:
        try:
            # Get settings
            try:
                sleep_time = float(gui.sleep_time.get())
            except ValueError:
                sleep_time = 0

            # Execute enabled functions
            for func_name, func in function_map.items():
                # Update cooldown display for this function (if it has a cooldown)
                cooldown = function_cooldowns.get(func_name, 0)
                if cooldown > 0 and func_name in gui.cooldown_labels:
                    current_time = time.time()
                    time_since_last_run = current_time - gui.last_run_times[func_name]
                    remaining = int(cooldown - time_since_last_run)

                    if remaining > 0:
                        # Show cooldown time
                        gui.cooldown_labels[func_name].config(text=f"({format_cooldown_time(remaining)})")
                    else:
                        # Cooldown expired - clear the label
                        gui.cooldown_labels[func_name].config(text="")

                if gui.function_states[func_name].get():
                    # Check cooldown for this function
                    if cooldown > 0:
                        # Cooldown is enabled for this function
                        current_time = time.time()
                        time_since_last_run = current_time - gui.last_run_times[func_name]

                        if time_since_last_run < cooldown:
                            # Still on cooldown - skip this run
                            continue

                    gui.update_status("Running", func_name)

                    try:
                        # Call function
                        func(bot, user)

                        # Auto-uncheck if in auto_uncheck set
                        if func_name in auto_uncheck:
                            gui.function_states[func_name].set(False)
                            log(f"{func_name} completed - unchecked")

                    except BotStoppedException:
                        # Bot was stopped by user - exit immediately
                        gui.log(f"Stopped during {func_name}")
                        raise

            # Sleep if configured
            if sleep_time > 0:
                gui.update_status("Running", f"Sleeping {sleep_time}s")
                time.sleep(sleep_time)

        except BotStoppedException:
            # User clicked stop button - exit gracefully
            gui.log("Bot stopped by user")
            break
        except Exception as e:
            gui.update_status("Error", str(e))
            gui.log(f"ERROR: {e}")
            time.sleep(1)

    gui.update_status("Stopped", "")
    gui.is_running = False
    gui.toggle_button.config(text="Start")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main function - launches the GUI

    Usage:
        python botTemplate.py <username>

    Note:
        Username must exist in config.json devices section
    """
    global gui_root, gui_instance

    # Check for user argument
    if len(sys.argv) < 2:
        print("ERROR: Please provide a user argument")
        print("Usage: python botTemplate.py <username>")
        sys.exit(1)

    username = sys.argv[1]

    # Create and run GUI
    gui_root = tk.Tk()
    gui = BotGUI(gui_root, username)
    gui_instance = gui

    gui.log(f"Bot Template started for user: {username}")
    gui.log("Use checkboxes to enable functions, then click Start")

    gui_root.mainloop()


if __name__ == "__main__":
    main()
