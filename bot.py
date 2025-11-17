"""
Bot Framework Module

Provides high-level bot automation framework for Android devices with image recognition,
OCR support, and gesture control. Abstracts android.py for easier bot development.
"""

from android import Android
import cv2 as cv
import numpy as np
import os
import os.path


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

    def __init__(self, android_device):
        """Initialize bot with Android device connection

        Args:
            android_device: Android instance for device control

        Raises:
            Exception: If android_device is not an Android instance
        """
        if not isinstance(android_device, Android):
            raise Exception("Initializing not with Android Class")

        self.andy = android_device
        self.needle = {}
        self.gui = None
        self.should_stop = False
        self._template_cache = {}  # Cache for template matching results
        self._cache_max_size = 50  # Limit cache size to prevent memory bloat
        self._load_all_needles()

    # ============================================================================
    # GUI & LOGGING
    # ============================================================================

    def check_should_stop(self):
        """Check if bot should stop execution and raise exception if needed

        Raises:
            BotStoppedException: If bot has been signaled to stop
        """
        if self.should_stop:
            raise BotStoppedException("Bot execution stopped by user")

    def set_gui(self, gui_instance):
        """Set GUI instance for logging

        Args:
            gui_instance: GUI object with log() method
        """
        self.gui = gui_instance

    def log(self, message, screenshot=None):
        """Log message to GUI if available, otherwise print to console

        Args:
            message: Message string to log
            screenshot: Optional screenshot to associate with log entry (for debug mode)
        """
        if self.gui:
            self.gui.log(message, screenshot=screenshot)
        else:
            print(message)

    # ============================================================================
    # NEEDLE LOADING (Images to Find)
    # ============================================================================

    def _load_needle_set(self, subfolder):
        """Load all needle images from a subfolder

        Args:
            subfolder: Folder name containing needle images

        Note:
            Images are stored in self.needle[subfolder][filename_without_extension]
            Needles are the images we search for in the screenshot (haystack)
        """
        self.log(f'Loading {subfolder} assets')
        self.needle[subfolder] = {}

        folder_path = os.path.join(os.path.dirname(__file__), subfolder)
        files = os.listdir(folder_path)

        for file in files:
            filename_parts = file.split(".")
            needle_name = filename_parts[0]
            needle_path = os.path.join(subfolder, file)
            self.needle[subfolder][needle_name] = cv.imread(
                needle_path, cv.IMREAD_UNCHANGED
            )

    def _load_all_needles(self):
        """Load all needle image sets from configured folders

        Note:
            Currently loads from 'findimg' folder. Modify this method to load
            additional needle sets from other folders.
        """
        self._load_needle_set('findimg')

    # ============================================================================
    # IMAGE RECOGNITION & NEEDLE MATCHING
    # ============================================================================

    def find_and_click(self, needle_name, offset_x=0, offset_y=0, accuracy=0.9,
                       tap=True, screenshot=None, click_delay=10, show_screenshot=False,
                       search_region=None, use_cache=False):
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

        # Cache debug mode check (avoid repeated hasattr calls)
        debug_mode = self.gui and hasattr(self.gui, 'debug') and self.gui.debug.get()

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
                annotated_screenshot = screenshot.copy()
                # Draw rectangle around found needle
                top_left = (max_loc[0] + roi_offset_x, max_loc[1] + roi_offset_y)
                bottom_right = (top_left[0] + needle_w, top_left[1] + needle_h)
                cv.rectangle(annotated_screenshot, top_left, bottom_right, (0, 0, 255, 255), 3)

                # Draw crosshair at tap position if tapping
                if tap:
                    self._draw_crosshair(annotated_screenshot, final_x, final_y, (0, 0, 255, 255), size=25, thickness=3)

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
                # In debug mode, include screenshot with the log
                self.log(log_msg, screenshot=screenshot if debug_mode else None)
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
        debug_mode = self.gui and hasattr(self.gui, 'debug') and self.gui.debug.get()
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
        debug_mode = self.gui and hasattr(self.gui, 'debug') and self.gui.debug.get()
        if debug_mode:
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
        debug_mode = self.gui and hasattr(self.gui, 'debug') and self.gui.debug.get()
        if debug_mode:
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

        Note:
            Automatically updates state manager with screenshot periodically
            for remote monitoring (every 20th screenshot to avoid overhead)
        """
        sc = self.andy.capture_screen()

        # Update state manager with screenshot periodically (every 20 screenshots)
        # This allows remote monitoring without adding significant overhead
        if self.gui and hasattr(self.gui, 'state_manager'):
            if not hasattr(self, '_screenshot_update_counter'):
                self._screenshot_update_counter = 0

            self._screenshot_update_counter += 1

            if self._screenshot_update_counter >= 20:  # Every 20th screenshot
                self._screenshot_update_counter = 0
                try:
                    # Update in background to avoid blocking bot execution
                    self.gui.state_manager.update_screenshot(sc)
                except Exception:
                    # Silently ignore errors to not break bot execution
                    pass

        return sc

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
