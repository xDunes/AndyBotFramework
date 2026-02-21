"""
Bot Framework Module

Provides high-level bot automation framework for Android devices with image recognition,
OCR support, and gesture control. Abstracts android.py for easier bot development.
"""

from .android import Android
import cv2 as cv
import numpy as np
import os
import threading
import queue
from datetime import datetime
from typing import Callable, Any, Optional


def _log_framework(message: str):
    """Print timestamped framework log message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}][BOT] {message}")


class BotStoppedException(Exception):
    """Exception raised when bot execution is stopped by user

    This exception is raised by check_should_stop() when the user
    clicks the Stop button, allowing immediate termination of
    bot operations mid-execution.
    """
    pass


class BOT:
    """Bot automation framework for Android devices

    Provides template matching, OCR preparation, screen interaction, and logging
    capabilities. Wraps Android device control with high-level automation methods.

    Attributes:
        andy: Android device instance for device control
        needle: Dictionary of loaded needle images to find in screenshots (haystack)
        gui: Optional GUI instance for logging
        should_stop: Flag to signal immediate stop of bot operations

    Note:
        The 'needle in haystack' metaphor: needles are small template images
        we search for within the larger screenshot (haystack) using OpenCV
        template matching.
    """

    # Class-level shared needle cache - all BOT instances share the same images
    # Key: findimg_path, Value: dict of loaded needle images
    _shared_needles: dict = {}
    _shared_needles_lock = threading.Lock()

    def __init__(self, android_device, findimg_path=None):
        """Initialize bot with Android device connection

        Args:
            android_device: Android instance for device control
            findimg_path: Path to findimg folder containing needle images.
                         If None, needles won't be loaded automatically.
                         Use set_findimg_path() to set later.

        Raises:
            Exception: If android_device is not an Android instance
        """
        if not isinstance(android_device, Android):
            raise Exception("Initializing not with Android Class")

        self.andy = android_device
        self.needle = {}  # Points to shared cache after loading
        self.gui = None
        self.should_stop = False
        self._template_cache = {}  # Cache for template matching results
        self._cache_max_size = 50  # Limit cache size to prevent memory bloat
        self._findimg_path = findimg_path

        # Command queue for serialized execution of remote commands
        self._command_queue: queue.Queue = queue.Queue()
        self._command_thread: Optional[threading.Thread] = None
        self._command_thread_running = False
        # When True, commands are processed by main loop instead of background thread
        self._main_loop_processes_commands = False
        # Track command timestamps for queue display
        self._command_timestamps = []  # List of (description, timestamp) tuples

        if findimg_path:
            self._load_all_needles()

    # ============================================================================
    # GUI & LOGGING
    # ============================================================================

    def check_should_stop(self):
        """Check if bot should stop execution and raise exception if needed.

        Also drains any pending remote commands (tap/swipe from web interface)
        when main loop command processing is enabled. This ensures web commands
        execute within milliseconds even during long-running bot functions.

        Raises:
            BotStoppedException: If bot has been signaled to stop
        """
        if self.should_stop:
            raise BotStoppedException("Bot execution stopped by user")
        # Drain any pending remote commands (tap/swipe from web)
        if self._main_loop_processes_commands and not self._command_queue.empty():
            self._drain_commands()

    def set_gui(self, gui_instance):
        """Set GUI instance for logging

        Args:
            gui_instance: GUI object with log() method
        """
        self.gui = gui_instance

    @property
    def is_debug_mode(self):
        """Check if debug mode is enabled in GUI

        Returns:
            bool: True if debug mode enabled, False otherwise
        """
        return self.gui and hasattr(self.gui, 'debug') and self.gui.debug.get()

    def log(self, message, screenshot=None):
        """Log message through the GUI or central logging system

        Args:
            message: Message string to log
            screenshot: Optional screenshot to associate with log entry (for debug mode)
        """
        # Use GUI directly if available (enables per-bot logging in headless mode)
        if self.gui and hasattr(self.gui, 'log') and callable(self.gui.log):
            self.gui.log(message, screenshot)
        else:
            # Fallback to central logging
            from .utils import log as central_log
            central_log(message, screenshot=screenshot)

    # ============================================================================
    # COMMAND QUEUE (Remote Command Serialization)
    # ============================================================================

    def start_command_queue(self):
        """Start the command queue processing thread

        Commands queued via queue_command() will be executed in order,
        one at a time. This ensures commands from the web interface don't
        interfere with each other or with the main bot loop.
        """
        if self._command_thread_running:
            return

        self._command_thread_running = True
        self._command_thread = threading.Thread(
            target=self._process_command_queue,
            daemon=True,
            name=f"CommandQueue-{id(self)}"
        )
        self._command_thread.start()

    def stop_command_queue(self):
        """Stop the command queue processing thread"""
        self._command_thread_running = False
        # Put a None sentinel to unblock the queue
        self._command_queue.put(None)
        if self._command_thread:
            self._command_thread.join(timeout=2.0)
            self._command_thread = None

    def get_command_queue_info(self):
        """Get current command queue status

        Returns:
            dict: Queue information with commands and timestamps
                {
                    'queue_size': int,
                    'commands': [
                        {'description': str, 'queued_at': str, 'delay_seconds': float},
                        ...
                    ]
                }
        """
        now = datetime.now()
        commands = []
        for desc, timestamp in self._command_timestamps:
            delay = (now - timestamp).total_seconds()
            commands.append({
                'description': desc,
                'queued_at': timestamp.strftime("%H:%M:%S"),
                'delay_seconds': delay
            })

        return {
            'queue_size': self._command_queue.qsize(),
            'commands': commands
        }

    def queue_command(self, command_func: Callable[[], Any], description: str = ""):
        """Queue a command for serialized execution

        Args:
            command_func: A callable (typically a lambda) that executes the command
            description: Optional description for logging

        Example:
            bot.queue_command(lambda: bot.tap(100, 200), "Tap at 100,200")
            bot.queue_command(lambda: bot.swipe(0, 500, 0, 100, 300), "Swipe up")
        """
        # Auto-start the queue thread if not running and not being processed by main loop
        if not self._command_thread_running and not self._main_loop_processes_commands:
            self.start_command_queue()

        # Track timestamp when command was queued
        timestamp = datetime.now()
        self._command_timestamps.append((description or "Unknown command", timestamp))
        # Keep only last 50 commands in history
        if len(self._command_timestamps) > 50:
            self._command_timestamps.pop(0)

        self._command_queue.put((command_func, description))

    def _process_command_queue(self):
        """Background thread that processes queued commands in order"""
        while self._command_thread_running:
            try:
                item = self._command_queue.get(timeout=0.5)

                if item is None:
                    # Sentinel value - exit thread
                    break

                command_func, description = item

                try:
                    command_func()
                    if description and self.gui:
                        self.log(description)
                except Exception as e:
                    if self.gui:
                        self.log(f"Command error: {e}")

                # Remove the completed command from timestamps list (FIFO - oldest first)
                if self._command_timestamps:
                    self._command_timestamps.pop(0)

                self._command_queue.task_done()

            except queue.Empty:
                # Timeout - continue loop to check _command_thread_running
                continue
            except Exception:
                # Unexpected error - continue processing
                continue

    def _drain_commands(self):
        """Process all pending commands from the queue synchronously.

        Called from check_should_stop() to ensure web commands (tap/swipe)
        execute promptly even during long-running bot functions. Since
        check_should_stop() is called at the start of every find_and_click(),
        tap(), swipe(), and find_all() call, commands execute within milliseconds.
        """
        while not self._command_queue.empty():
            try:
                item = self._command_queue.get_nowait()

                if item is None:
                    # Sentinel value - put it back for the thread to handle
                    self._command_queue.put(None)
                    break

                command_func, description = item

                try:
                    command_func()
                    if description and self.gui:
                        self.log(f"[CMD] {description}")
                except BotStoppedException:
                    raise
                except Exception as e:
                    if self.gui:
                        self.log(f"[CMD] Error: {e}")

                # Remove the completed command from timestamps list (FIFO)
                if self._command_timestamps:
                    self._command_timestamps.pop(0)

                self._command_queue.task_done()

            except queue.Empty:
                break

    # ============================================================================
    # NEEDLE LOADING (Images to Find)
    # ============================================================================

    def set_findimg_path(self, path):
        """Set the findimg path and load needles

        Args:
            path: Absolute or relative path to findimg folder

        Note:
            Call this after initialization if findimg_path was not provided
            to the constructor.
        """
        self._findimg_path = path
        self._load_all_needles()

    @classmethod
    def _load_needle_set_shared(cls, folder_path):
        """Load needle images into shared class-level cache

        Args:
            folder_path: Full path to folder containing needle images

        Returns:
            dict: The loaded needle dictionary from shared cache
        """
        # Normalize path for consistent cache key
        cache_key = os.path.normpath(os.path.abspath(folder_path))

        # Double-checked locking: quick check without lock first
        if cache_key in cls._shared_needles:
            return cls._shared_needles[cache_key]

        with cls._shared_needles_lock:
            # Re-check after acquiring lock (another thread may have loaded it)
            if cache_key in cls._shared_needles:
                return cls._shared_needles[cache_key]

            # Load needles into shared cache
            needles = {'findimg': {}}

            if not os.path.exists(folder_path):
                _log_framework(f'WARNING: findimg folder not found: {folder_path}')
                cls._shared_needles[cache_key] = needles
                return needles

            _log_framework(f'Loading shared assets from {folder_path}')
            files = os.listdir(folder_path)

            for file in files:
                if file.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    filename_parts = file.split(".")
                    needle_name = filename_parts[0]
                    needle_path = os.path.join(folder_path, file)
                    needles['findimg'][needle_name] = cv.imread(
                        needle_path, cv.IMREAD_UNCHANGED
                    )

            _log_framework(f'Loaded {len(needles["findimg"])} needle images (shared)')
            cls._shared_needles[cache_key] = needles
            return needles

    def _load_all_needles(self):
        """Load all needle image sets from configured findimg path

        Uses shared class-level cache so multiple BOT instances
        share the same needle images in memory.
        """
        if self._findimg_path:
            # Use shared cache - all bots with same path share needles
            self.needle = self._load_needle_set_shared(self._findimg_path)

    # ============================================================================
    # IMAGE RECOGNITION & NEEDLE MATCHING
    # ============================================================================

    def find_and_click(self, needle_name, offset_x=0, offset_y=0, accuracy=0.9,
                       tap=True, screenshot=None, click_delay=10, show_screenshot=False,
                       search_region=None, use_cache=False, sqdiff=False):
        """Find needle image on screen and optionally tap it

        Uses OpenCV template matching to locate a needle image in the screenshot
        (haystack). If found above accuracy threshold, optionally taps the location.

        Args:
            needle_name: Name of the needle image to find (without path/extension)
            offset_x: X offset from found location (default: 0)
            offset_y: Y offset from found location (default: 0)
            accuracy: Match accuracy 0.0-1.0, higher is stricter (default: 0.9)
            tap: Whether to tap if found (default: True)
            screenshot: Pre-captured screenshot, or None to capture new (default: None)
            click_delay: Touch delay parameter in ms (default: 10)
            show_screenshot: Display screenshot for debugging (default: False)
            search_region: Optional tuple (x, y, w, h) to limit search area for 2-4x speedup (default: None)
            use_cache: Use cached template matching results for repeated searches (default: False)
            sqdiff: Use TM_SQDIFF_NORMED matching which is sensitive to brightness differences (default: False)

        Returns:
            bool: True if needle found (and tapped if tap=True), False otherwise

        Example:
            # Find and tap a button
            if bot.find_and_click('play_button'):
                print("Tapped play button")

            # Just check if image exists without tapping
            if bot.find_and_click('error_dialog', tap=False):
                print("Error detected")

            # Search only in top-right corner for faster matching
            if bot.find_and_click('settings', search_region=(800, 0, 400, 200)):
                print("Found settings button")
        """
        self.check_should_stop()

        if screenshot is None:
            screenshot = self.screenshot()

        if show_screenshot:
            cv.imshow("test", screenshot)
            cv.waitKey()

        # Cache debug mode check for this method call
        debug_mode = self.is_debug_mode

        # Handle ROI (Region of Interest) for faster searching
        search_area = screenshot
        roi_offset_x, roi_offset_y = 0, 0

        if search_region:
            x, y, w, h = search_region
            search_area = screenshot[y:y+h, x:x+w]
            roi_offset_x, roi_offset_y = x, y

        # Get needle and check cache
        needle = self.get_needle(needle_name)
        needle_h, needle_w = needle.shape[:2]  # Get dimensions once

        # Create cache key based on screenshot id and needle
        cache_key = (needle_name, id(screenshot), search_region)

        # Try to use cached result
        if use_cache and cache_key in self._template_cache:
            max_val, max_loc = self._template_cache[cache_key]
        else:
            # Use TM_SQDIFF_NORMED if explicitly requested or for small templates
            # (both dimensions under 10 pixels) to avoid false positives from normalization artifacts
            use_sqdiff = sqdiff or (needle_h < 10 and needle_w < 10)

            if use_sqdiff:
                # TM_SQDIFF_NORMED: lower values = better match (0 is perfect)
                result = cv.matchTemplate(search_area, needle, cv.TM_SQDIFF_NORMED)
                min_val, _, min_loc, _ = cv.minMaxLoc(result)
                # Convert to same scale as CCOEFF_NORMED (higher = better match)
                max_val = 1.0 - min_val
                max_loc = min_loc
            else:
                # Match needle using OpenCV template matching
                result = cv.matchTemplate(search_area, needle, cv.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv.minMaxLoc(result)

            # Cache the result (with size limit to prevent memory bloat)
            if use_cache:
                if len(self._template_cache) >= self._cache_max_size:
                    # Remove oldest entry (simple FIFO strategy)
                    self._template_cache.pop(next(iter(self._template_cache)))
                self._template_cache[cache_key] = (max_val, max_loc)

        # Check if match found
        if max_val > accuracy:
            accuracy_percent = round(max_val * 100, 2)

            # Calculate final tap position (adjust for ROI offset)
            final_x = max_loc[0] + roi_offset_x + offset_x
            final_y = max_loc[1] + roi_offset_y + offset_y

            # Create annotated screenshot once if debug mode is on
            annotated_screenshot = None
            if debug_mode:
                # If search_region is set, log the cropped region instead of full screenshot
                if search_region:
                    annotated_screenshot = search_area.copy()
                    # Draw rectangle around found needle (coordinates relative to cropped region)
                    top_left = (max_loc[0], max_loc[1])
                    bottom_right = (top_left[0] + needle_w, top_left[1] + needle_h)
                    cv.rectangle(annotated_screenshot, top_left, bottom_right, (0, 0, 255, 255), 3)

                    # Draw crosshair at detection position (relative to cropped region)
                    crosshair_color = (0, 0, 255, 255) if tap else (0, 255, 0, 255)
                    crosshair_x = max_loc[0] + offset_x
                    crosshair_y = max_loc[1] + offset_y
                    self._draw_crosshair(annotated_screenshot, crosshair_x, crosshair_y, crosshair_color, size=25, thickness=3)
                else:
                    annotated_screenshot = screenshot.copy()
                    # Draw rectangle around found needle
                    top_left = (max_loc[0] + roi_offset_x, max_loc[1] + roi_offset_y)
                    bottom_right = (top_left[0] + needle_w, top_left[1] + needle_h)
                    cv.rectangle(annotated_screenshot, top_left, bottom_right, (0, 0, 255, 255), 3)

                    # Draw crosshair at detection/tap position
                    # Red crosshair for tap, green crosshair for detection-only (no tap)
                    crosshair_color = (0, 0, 255, 255) if tap else (0, 255, 0, 255)
                    self._draw_crosshair(annotated_screenshot, final_x, final_y, crosshair_color, size=25, thickness=3)

            # Log and perform action
            if tap:
                log_msg = f"TAP {needle_name} at ({final_x}, {final_y}) acc:{accuracy_percent}%"
                self.log(log_msg, screenshot=annotated_screenshot)
                self.andy.touch(final_x, final_y, delay=click_delay, suppress_log=True)
            else:
                log_msg = f"FOUND {needle_name} acc:{accuracy_percent}%"
                self.log(log_msg, screenshot=annotated_screenshot)

            return True
        else:
            # Log NO TAP events when debug mode is enabled or no GUI (console mode)
            if debug_mode or not self.gui:
                accuracy_percent = round(max_val * 100, 2)
                log_msg = f"NO TAP {needle_name} acc:{accuracy_percent}%"
                # In debug mode, include screenshot with the log (cropped if search_region set)
                log_screenshot = search_area if (debug_mode and search_region) else (screenshot if debug_mode else None)
                self.log(log_msg, screenshot=log_screenshot)
            return False

    def find_all(self, needle_name, accuracy=0.9, screenshot=None, search_region=None, debug=False):
        """Find all occurrences of needle image on screen

        Uses OpenCV template matching to locate all instances of a needle image
        in the screenshot (haystack) that meet the accuracy threshold.

        Args:
            needle_name: Name of the needle image to find (without path/extension)
            accuracy: Match accuracy 0.0-1.0, higher is stricter (default: 0.9)
            screenshot: Pre-captured screenshot, or None to capture new (default: None)
            search_region: Optional tuple (x, y, w, h) to limit search area (default: None)
            debug: Display annotated screenshot with detected needles (default: False)

        Returns:
            dict: Dictionary containing:
                - 'count': Number of matches found
                - 'coordinates': List of tuples (x, y, confidence) for each match,
                                sorted by confidence (highest first)

        Example:
            # Find all instances of a button
            result = bot.find_all('coin_icon')
            print(f"Found {result['count']} coins")
            for x, y, conf in result['coordinates']:
                print(f"Coin at ({x}, {y}) with {conf*100:.1f}% confidence")

            # Search only in a specific region
            result = bot.find_all('enemy', search_region=(0, 0, 500, 500))
            if result['count'] > 0:
                print(f"Found {result['count']} enemies")

            # Debug mode to visualize detections
            result = bot.find_all('coin_icon', debug=True)
        """
        self.check_should_stop()

        if screenshot is None:
            screenshot = self.screenshot()

        # Handle ROI (Region of Interest) for faster searching
        search_area = screenshot
        roi_offset_x, roi_offset_y = 0, 0

        if search_region:
            x, y, w, h = search_region
            search_area = screenshot[y:y+h, x:x+w]
            roi_offset_x, roi_offset_y = x, y

        # Get needle dimensions
        needle = self.get_needle(needle_name)
        needle_h, needle_w = needle.shape[:2]

        # Match needle using OpenCV template matching
        result = cv.matchTemplate(search_area, needle, cv.TM_CCOEFF_NORMED)

        # Find all locations where match exceeds accuracy threshold
        locations = np.where(result >= accuracy)

        # Combine x, y coordinates with their confidence values
        all_matches = []
        for pt_y, pt_x in zip(*locations):
            confidence = result[pt_y, pt_x]
            # Adjust coordinates for ROI offset
            final_x = pt_x + roi_offset_x
            final_y = pt_y + roi_offset_y
            all_matches.append((final_x, final_y, confidence))

        # Apply Non-Maximum Suppression to remove overlapping detections
        # Group nearby matches (within needle dimensions) and keep only the highest confidence one
        coordinates = []
        if all_matches:
            # Sort by confidence (highest first)
            all_matches.sort(key=lambda m: m[2], reverse=True)

            # Process each match, skipping those too close to already accepted matches
            for x, y, conf in all_matches:
                # Check if this match is too close to any already accepted match
                is_duplicate = False
                for accepted_x, accepted_y, _ in coordinates:
                    # Calculate distance between matches
                    distance = np.sqrt((x - accepted_x)**2 + (y - accepted_y)**2)

                    # If distance is less than half the needle diagonal, consider it a duplicate
                    # This ensures we don't count slightly shifted versions of the same match
                    threshold_distance = np.sqrt(needle_w**2 + needle_h**2) / 2
                    if distance < threshold_distance:
                        is_duplicate = True
                        break

                # Only add if not a duplicate
                if not is_duplicate:
                    coordinates.append((x, y, conf))

        # Create result dictionary
        result_dict = {
            'count': len(coordinates),
            'coordinates': coordinates
        }

        # Log result
        debug_mode = self.is_debug_mode
        if debug_mode or not self.gui:
            if result_dict['count'] > 0:
                log_msg = f"FIND_ALL found {result_dict['count']} instances of {needle_name}"

                # Create annotated screenshot in debug mode
                annotated_screenshot = None
                if debug_mode:
                    annotated_screenshot = screenshot.copy()
                    for x, y, _ in coordinates:
                        # Draw rectangle around each found needle
                        top_left = (x, y)
                        bottom_right = (x + needle_w, y + needle_h)
                        cv.rectangle(annotated_screenshot, top_left, bottom_right, (0, 255, 0, 255), 2)
                        # Draw crosshair at center
                        self._draw_crosshair(annotated_screenshot, x, y, (0, 255, 0, 255), size=15, thickness=2)

                self.log(log_msg, screenshot=annotated_screenshot)
            else:
                log_msg = f"FIND_ALL found 0 instances of {needle_name}"
                self.log(log_msg, screenshot=screenshot if debug_mode else None)

        # Display debug visualization if requested
        if debug:
            debug_screenshot = screenshot.copy()

            # Draw red rectangle around search region if specified
            if search_region:
                region_x, region_y, region_w, region_h = search_region
                region_top_left = (region_x, region_y)
                region_bottom_right = (region_x + region_w, region_y + region_h)
                cv.rectangle(debug_screenshot, region_top_left, region_bottom_right, (0, 0, 255, 255), 3)

                # Add label for search region
                region_label = "Search Region"
                cv.putText(debug_screenshot, region_label, (region_x, region_y - 10),
                          cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255, 255), 2)

            # Draw rectangles and crosshairs for all detected needles
            for x, y, conf in coordinates:
                # Draw green rectangle around each found needle
                top_left = (x, y)
                bottom_right = (x + needle_w, y + needle_h)
                cv.rectangle(debug_screenshot, top_left, bottom_right, (0, 255, 0, 255), 3)

                # Draw crosshair at center
                self._draw_crosshair(debug_screenshot, x, y, (0, 255, 0, 255), size=20, thickness=3)

                # Add confidence text above the rectangle
                conf_text = f"{conf*100:.1f}%"
                cv.putText(debug_screenshot, conf_text, (x, y - 10),
                          cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0, 255), 2)

            # Add summary text at the top
            summary_text = f"Found {result_dict['count']} instances of '{needle_name}'"
            cv.putText(debug_screenshot, summary_text, (10, 30),
                      cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0, 255), 2)

            # Display the annotated screenshot and wait for key press
            cv.imshow(f"find_all Debug: {needle_name}", debug_screenshot)
            cv.waitKey(0)  # Wait until user closes the window
            cv.destroyAllWindows()

        return result_dict

    def get_needle(self, needle_name):
        """Get loaded needle image by name

        Args:
            needle_name: Name of the needle (without path/extension)

        Returns:
            numpy.ndarray: Needle image array

        Raises:
            KeyError: If needle name not found in loaded needles
        """
        if 'findimg' not in self.needle:
            raise KeyError(f"Needles not loaded - findimg_path was: {self._findimg_path}")
        if needle_name not in self.needle['findimg']:
            raise KeyError(f"Needle '{needle_name}' not found. Available: {list(self.needle['findimg'].keys())[:10]}...")
        return self.needle['findimg'][needle_name]

    def clear_template_cache(self):
        """Clear the template matching cache

        Useful when switching between different game screens or activities
        to prevent using stale cached results.

        Example:
            bot.clear_template_cache()  # Clear cache before new activity
        """
        self._template_cache.clear()

    def _draw_crosshair(self, image, x, y, color, size=20, thickness=2):
        """Draw a crosshair on the image at specified coordinates

        Args:
            image: Image to draw on (modified in place)
            x: X coordinate
            y: Y coordinate
            color: BGRA color tuple (e.g., (0, 0, 255, 255) for red with alpha)
            size: Length of crosshair arms in pixels (default: 20)
            thickness: Line thickness (default: 2)
        """
        # Horizontal line
        cv.line(image, (x - size, y), (x + size, y), color, thickness)
        # Vertical line
        cv.line(image, (x, y - size), (x, y + size), color, thickness)
        # Circle at center
        cv.circle(image, (x, y), 5, color, -1)

    # ============================================================================
    # SCREEN INTERACTION - Touch & Gestures
    # ============================================================================

    def tap(self, x, y):
        """Tap at specific screen coordinates

        Args:
            x: X coordinate
            y: Y coordinate

        Example:
            bot.tap(270, 480)  # Tap center of 540x960 screen
        """
        self.check_should_stop()

        # Enhanced debug logging
        if self.is_debug_mode:
            screenshot = self.screenshot()
            # Draw red crosshair at tap position
            annotated_screenshot = screenshot.copy()
            self._draw_crosshair(annotated_screenshot, x, y, (0, 0, 255, 255), size=25, thickness=3)  # Red crosshair with alpha
            self.log(f"TAP COORDINATES at ({x}, {y})", screenshot=annotated_screenshot)

        self.andy.touch(x, y)

    def swipe(self, x1, y1, x2, y2, duration=500):
        """Swipe from one point to another

        Args:
            x1: Starting X coordinate
            y1: Starting Y coordinate
            x2: Ending X coordinate
            y2: Ending Y coordinate
            duration: Swipe duration in milliseconds (default: 500)

        Example:
            bot.swipe(270, 800, 270, 200, duration=300)  # Swipe up
        """
        self.check_should_stop()

        # Enhanced debug logging
        if self.is_debug_mode:
            screenshot = self.screenshot()
            # Draw line from start to finish with arrow
            annotated_screenshot = screenshot.copy()
            # Draw arrow line from start to finish
            cv.arrowedLine(annotated_screenshot, (x1, y1), (x2, y2), (0, 0, 255, 255), 4, tipLength=0.05)  # Red arrow with alpha
            # Draw circles at start and end
            cv.circle(annotated_screenshot, (x1, y1), 10, (0, 0, 255, 255), -1)  # Red start with alpha
            cv.circle(annotated_screenshot, (x2, y2), 10, (0, 0, 255, 255), 3)  # Red hollow end with alpha
            self.log(f"SWIPE from ({x1}, {y1}) to ({x2}, {y2}) duration:{duration}ms", screenshot=annotated_screenshot)

        self.andy.touch(x1, y1, x2, y2, delay=duration)

    # ============================================================================
    # SCREEN CAPTURE
    # ============================================================================

    def screenshot(self):
        """Capture current device screen

        Returns:
            numpy.ndarray: Screenshot in BGRA format (OpenCV compatible)

        Example:
            sc = bot.screenshot()
            color = bot.get_pixel_color(sc, 100, 100)
        """
        return self.andy.capture_screen()

    # ============================================================================
    # TEXT INPUT & KEYBOARD
    # ============================================================================

    def type_text(self, text):
        """Type text on the device followed by Enter

        Args:
            text: Text string to type

        Note:
            Automatically presses Enter after typing text

        Example:
            bot.type_text("Hello World")
        """
        self.andy.send_text(text)

    def press_enter(self):
        """Press the Enter/Return key

        Example:
            bot.press_enter()
        """
        self.andy.press_enter()

    def press_backspace(self, count=1):
        """Press the Backspace key one or more times

        Args:
            count: Number of times to press backspace (default: 1)

        Example:
            bot.press_backspace(5)  # Delete 5 characters
        """
        self.andy.press_backspace(count)

    # ============================================================================
    # IMAGE ANALYSIS & OCR
    # ============================================================================

    def get_pixel_color(self, screenshot, x, y):
        """Get RGB color of a pixel from screenshot

        Args:
            screenshot: Screenshot array in BGR/BGRA format (from screenshot())
            x: X coordinate
            y: Y coordinate

        Returns:
            tuple: (R, G, B) values in RGB order (0-255 each)

        Example:
            sc = bot.screenshot()
            r, g, b = bot.get_pixel_color(sc, 270, 480)
            if r > 200 and g < 50 and b < 50:
                print("Red pixel detected")
        """
        # Returns in RGB order (converts from BGR/BGRA)
        return (screenshot[y][x][2], screenshot[y][x][1], screenshot[y][x][0])

    def prepare_image_for_ocr(self, image, gaussian=True, adaptive=False, morph=True, scale=5, invert=True):
        """Prepare image for OCR text recognition

        Preprocesses image with resizing, optional blur, grayscale conversion,
        thresholding, morphological operations, and color inversion to optimize
        for OCR accuracy.

        Args:
            image: Input image (BGR/BGRA format)
            gaussian: Apply Gaussian blur to reduce noise (default: True)
            adaptive: Use adaptive thresholding instead of binary (default: False)
            morph: Apply morphological operations to clean up text (default: True)
            scale: Resize multiplier for better OCR (default: 5)
            invert: Invert colors - use True for dark text on light bg, False for white text on dark bg (default: True)

        Returns:
            numpy.ndarray: Processed black and white image optimized for OCR

        Example:
            sc = bot.screenshot()
            cropped = sc[100:200, 50:250]  # Crop region

            # For dark text on light background:
            processed = bot.prepare_image_for_ocr(cropped)

            # For white text on dark background:
            processed = bot.prepare_image_for_ocr(cropped, invert=False)

            # For difficult text, use adaptive thresholding:
            processed = bot.prepare_image_for_ocr(cropped, adaptive=True)
        """
        # Resize image for better OCR accuracy
        image = cv.resize(image, None, fx=scale, fy=scale, interpolation=cv.INTER_CUBIC)

        # Apply Gaussian blur to reduce noise
        if gaussian:
            image = cv.GaussianBlur(image, (5, 5), 0)

        # Convert to grayscale
        gray_image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

        # Apply thresholding
        if adaptive:
            # Adaptive thresholding works better for varying lighting conditions
            bw_image = cv.adaptiveThreshold(
                gray_image, 255,
                cv.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv.THRESH_BINARY,
                11, 2
            )
        else:
            # Simple binary threshold with Otsu's method for automatic threshold value
            _, bw_image = cv.threshold(gray_image, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)

        # Apply morphological operations to clean up the image
        if morph:
            # Remove small noise with opening (erosion followed by dilation)
            kernel = np.ones((2, 2), np.uint8)
            bw_image = cv.morphologyEx(bw_image, cv.MORPH_OPEN, kernel, iterations=1)

            # Close small gaps in text with closing (dilation followed by erosion)
            bw_image = cv.morphologyEx(bw_image, cv.MORPH_CLOSE, kernel, iterations=1)

        # Invert colors if needed (Tesseract works best with black text on white background)
        if invert:
            bw_image = cv.bitwise_not(bw_image)

        return bw_image
