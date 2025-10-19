"""
Bot Framework Module

Provides high-level bot automation framework for Android devices with image recognition,
OCR support, and gesture control. Abstracts android.py for easier bot development.
"""

from android import Android
import cv2 as cv
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
        andy: Android device instance (friendly name for Android controller)
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

    def log(self, message):
        """Log message to GUI if available, otherwise print to console

        Args:
            message: Message string to log
        """
        if self.gui:
            self.gui.log(message)
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
                       tap=True, screenshot=None, click_delay=10, show_screenshot=False):
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

        Returns:
            bool: True if needle found (and tapped if tap=True), False otherwise

        Example:
            # Find and tap a button
            if bot.find_and_click('play_button'):
                print("Tapped play button")

            # Just check if image exists without tapping
            if bot.find_and_click('error_dialog', tap=False):
                print("Error detected")
        """
        self.check_should_stop()

        if screenshot is None:
            screenshot = self.screenshot()

        if show_screenshot:
            cv.imshow("test",screenshot)
            cv.waitKey()
            
        # Match needle using OpenCV template matching
        needle = self.get_needle(needle_name)
        result = cv.matchTemplate(screenshot, needle, cv.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)

        if max_val > accuracy:
            accuracy_percent = round(max_val * 100, 2)

            if tap:
                final_x = max_loc[0] + offset_x
                final_y = max_loc[1] + offset_y
                self.log(f"TAP {needle_name} at ({final_x}, {final_y}) acc:{accuracy_percent}%")
                self.andy.touch(final_x, final_y, delay=click_delay, suppress_log=True)
            else:
                self.log(f"FOUND {needle_name} acc:{accuracy_percent}%")
            return True
        else:
            # Only log if NO TAP logging is enabled
            if self.gui and hasattr(self.gui, 'show_no_click') and self.gui.show_no_click.get():
                accuracy_percent = round(max_val * 100, 2)
                self.log(f"NO TAP {needle_name} acc:{accuracy_percent}%")
            elif not self.gui:
                # If no GUI, always log (console mode)
                accuracy_percent = round(max_val * 100, 2)
                self.log(f"NO TAP {needle_name} acc:{accuracy_percent}%")
            return False

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

    def prepare_image_for_ocr(self, image, gaussian=True):
        """Prepare image for OCR text recognition

        Preprocesses image with resizing, optional blur, grayscale conversion,
        thresholding, and color inversion to optimize for OCR accuracy.

        Args:
            image: Input image (BGR/BGRA format)
            gaussian: Apply Gaussian blur to reduce noise (default: True)

        Returns:
            numpy.ndarray: Processed black and white image optimized for OCR

        Example:
            sc = bot.screenshot()
            cropped = sc[100:200, 50:250]  # Crop region
            processed = bot.prepare_image_for_ocr(cropped)
            text = pytesseract.image_to_string(processed)
        """
        # Resize image 5x for better OCR accuracy
        image = cv.resize(image, None, fx=5, fy=5, interpolation=cv.INTER_CUBIC)

        # Apply Gaussian blur to reduce noise
        if gaussian:
            image = cv.GaussianBlur(image, (5, 5), 0)

        # Convert to grayscale
        gray_image = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

        # Apply binary threshold
        _, bw_image = cv.threshold(gray_image, 127, 255, cv.THRESH_BINARY)

        # Invert colors for better OCR
        bw_image = cv.bitwise_not(bw_image)

        return bw_image
