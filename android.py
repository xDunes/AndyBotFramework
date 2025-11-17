"""
Android Device Control Module

Provides ADB-based communication and control for Android devices via ppadb library.
Handles device connection, screen capture, touch input, and text input with
automatic reconnection on errors.
"""

from ppadb.client import Client
import cv2 as cv
import numpy as np
import time
from functools import wraps


def auto_reconnect(func):
    """Decorator to automatically reconnect on device communication errors

    Wraps device communication methods to handle disconnections gracefully.
    On error, attempts reconnection in a loop until successful, then retries
    the original operation.

    Args:
        func: Function to wrap with auto-reconnect behavior

    Returns:
        Wrapped function with reconnection logic

    Note:
        Uses infinite retry loop - will block until reconnection succeeds
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self.log(f"{func.__name__} failed: {e} - Reconnecting...")
            while not self._connect_to_device():
                self.log("Reconnection failed, retrying...")
            return func(self, *args, **kwargs)
    return wrapper


class Android:
    """Android device controller via ADB

    Provides high-level interface for controlling Android devices through ADB,
    including screen capture, touch input, and text input. Automatically handles
    device disconnections and reconnections.

    Attributes:
        devices: List of available ADB devices
        device: Currently connected device instance
        serial_number: Target device serial number
        gui: Optional GUI instance for logging
    """

    def __init__(self, serial):
        """Initialize Android controller and connect to device

        Args:
            serial: Device serial number to connect to (e.g., "emulator-5554")

        Note:
            Automatically connects to ADB server at 127.0.0.1:5037
            and attempts connection to specified device
        """
        self.devices = None
        self.device = None
        self.serial_number = serial
        self.gui = None
        self._initialize_connection()

    # ============================================================================
    # GUI & LOGGING
    # ============================================================================

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
    # DEVICE CONNECTION & MANAGEMENT
    # ============================================================================

    def _initialize_connection(self):
        """Initialize ADB connection and connect to target device

        Connects to local ADB server, discovers devices, and connects to
        the device matching self.serial_number. Exits if ADB server not
        running or no devices attached. Retries connection until successful.
        """
        adb = Client(host='127.0.0.1', port=5037)

        try:
            self.devices = adb.devices()
        except Exception as e:
            self.log(f"ADB ERROR: ADB server not running - {e}")
            exit()

        if len(self.devices) == 0:
            self.log('ADB ERROR: No devices attached')
            exit()

        while not self._connect_to_device(initialize=False):
            self.log("Connection failed, retrying...")

    def _connect_to_device(self, initialize=True):
        """Connect to device matching serial number

        Args:
            initialize: Whether to reinitialize device list (default: True)

        Returns:
            bool: True if connection successful, False otherwise
        """
        if initialize:
            self._initialize_connection()

        for dev in self.devices:
            try:
                dev_serial = dev.shell('getprop ro.boot.serialno')
                self.log(f"Detected serial: {dev_serial.strip()}")

                if self.serial_number in dev_serial:
                    self.log(f"Connected to device: {dev_serial.strip()}")
                    self.device = dev
                    return True

            except Exception as e:
                self.log(f"Device connection error: {e}")
                continue

        time.sleep(1)
        return False

    # ============================================================================
    # SCREEN CAPTURE
    # ============================================================================

    @auto_reconnect
    def capture_screen(self):
        """Capture current device screen as numpy array

        Returns:
            numpy.ndarray: Screenshot in BGRA format (OpenCV compatible)

        Note:
            - Automatically reconnects on error and retries capture
            - Uses OpenCV for fast decoding (50-60% faster than PIL)
            - cv.imdecode automatically decodes PNG to BGR/BGRA format
        """
        screenshot_bytes = self.device.screencap()

        # Decode screenshot with OpenCV (faster than PIL)
        # cv.imdecode automatically handles PNG and returns BGR(A) format
        # which is what OpenCV expects - no additional conversion needed
        np_img = cv.imdecode(
            np.frombuffer(screenshot_bytes, dtype=np.uint8),
            cv.IMREAD_UNCHANGED
        )

        return np_img

    # ============================================================================
    # TOUCH INPUT & GESTURES
    # ============================================================================

    @auto_reconnect
    def touch(self, x1, y1, x2=-1, y2=-1, delay=500, suppress_log=False):
        """Execute touch, tap, or swipe gesture on device

        Args:
            x1: Starting/tap X coordinate
            y1: Starting/tap Y coordinate
            x2: Ending X coordinate for swipe (default: -1 = same as x1)
            y2: Ending Y coordinate for swipe (default: -1 = same as y1)
            delay: Swipe duration in milliseconds (default: 500)
            suppress_log: If True, don't log this action (default: False)

        Note:
            If x2 == x1 and y2 == y1, executes a tap.
            Otherwise, executes a swipe gesture.
        """
        # Default to tap coordinates if swipe not specified
        if x2 == -1:
            x2 = x1
        if y2 == -1:
            y2 = y1

        # Execute tap or swipe
        if x2 == x1 and y2 == y1:
            if not suppress_log:
                self.log(f"Touch: ({x1}, {y1})")
            self.device.shell(f'input tap {x1} {y1}')
        else:
            if not suppress_log:
                self.log(f'Swipe: ({x1}, {y1}) -> ({x2}, {y2}) [{delay}ms]')
            self.device.shell(f'input swipe {x1} {y1} {x2} {y2} {delay}')

    def tap(self, x, y):
        """Tap at specific coordinates

        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.touch(x, y)

    def swipe(self, x1, y1, x2, y2, duration=500):
        """Swipe from one point to another

        Args:
            x1: Starting X coordinate
            y1: Starting Y coordinate
            x2: Ending X coordinate
            y2: Ending Y coordinate
            duration: Swipe duration in milliseconds (default: 500)
        """
        self.touch(x1, y1, x2, y2, delay=duration)

    # ============================================================================
    # TEXT INPUT & KEYBOARD
    # ============================================================================

    @auto_reconnect
    def send_text(self, text):
        """Send text input to device followed by Enter key

        Args:
            text: Text string to send to device

        Note:
            Automatically presses Enter after sending text
        """
        self.log(f'Text input: "{text}"')
        self.device.shell(f"input text '{text}'")
        self.press_enter()

    @auto_reconnect
    def press_enter(self):
        """Press the Enter/Return key (keycode 66)

        See: http://www.temblast.com/ref/akeyscode.htm
        """
        self.device.shell("input keyevent 66")

    @auto_reconnect
    def press_backspace(self, count=1):
        """Press the Backspace key one or more times (keycode 67)

        Args:
            count: Number of times to press backspace (default: 1)
        """
        for _ in range(count):
            self.device.shell("input keyevent 67")
