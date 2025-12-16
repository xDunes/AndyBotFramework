"""
Android Device Control Module

Provides ADB-based communication and control for Android devices via ppadb library.
Handles device connection, screen capture, touch input, and text input with
automatic reconnection on errors.
"""

from ppadb.client import Client
from ppadb.device import Device
import cv2 as cv
import numpy as np
import time
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import wraps
from typing import Optional


# Default value if not specified in config
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10
DEFAULT_ADB_TIMEOUT = 30  # seconds - timeout for ADB operations


def _load_max_reconnect_attempts():
    """Load max_reconnect_attempts from master.conf"""
    try:
        # Config is at project root, not inside core/
        project_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(project_root, 'master.conf')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get('max_reconnect_attempts', DEFAULT_MAX_RECONNECT_ATTEMPTS)
    except Exception:
        return DEFAULT_MAX_RECONNECT_ATTEMPTS


def _load_adb_timeout():
    """Load adb_timeout from master.conf"""
    try:
        project_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(project_root, 'master.conf')
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get('adb_timeout', DEFAULT_ADB_TIMEOUT)
    except Exception:
        return DEFAULT_ADB_TIMEOUT


class ADBTimeoutError(Exception):
    """Exception raised when an ADB operation times out"""
    pass


# Thread pool for running ADB operations with timeout
_adb_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="adb_timeout")


def auto_reconnect(func):
    """Decorator to automatically reconnect on device communication errors

    Wraps device communication methods to handle disconnections gracefully.
    On error, attempts reconnection up to max_reconnect_attempts times,
    then retries the original operation.

    Args:
        func: Function to wrap with auto-reconnect behavior

    Returns:
        Wrapped function with reconnection logic

    Note:
        Retries up to max_reconnect_attempts (from config.json) times before giving up.
        Raises AndroidStoppedException if stopped by user or max attempts reached.
        Uses a lock to prevent multiple threads from reconnecting simultaneously.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except AndroidStoppedException:
            # Don't catch AndroidStoppedException - let it propagate
            raise
        except Exception as e:
            # Get the shared lock state for this device
            reconnect_state = self._reconnect_state
            lock = reconnect_state['lock']

            # Acquire lock first - this ensures only one thread handles reconnection
            # Use blocking acquire so threads wait their turn
            lock.acquire()

            try:
                # Check if reconnection has permanently failed (another thread may have set this)
                if reconnect_state.get('permanent_failure'):
                    raise AndroidStoppedException("Device connection permanently failed")

                # Check if another thread already successfully reconnected
                if reconnect_state.get('just_reconnected'):
                    reconnect_state['just_reconnected'] = False
                    # Try the original function again
                    lock.release()
                    return func(self, *args, **kwargs)

                # We have the lock and no one else has reconnected - do it ourselves
                reconnect_state['failed'] = False
                self.log(f"{func.__name__} failed: {e} - Reconnecting...")
                max_attempts = _load_max_reconnect_attempts()
                attempts = 0

                # Refresh device list before retry loop
                try:
                    adb = Client(host='127.0.0.1', port=5037)
                    self.devices = adb.devices()
                    if len(self.devices) == 0:
                        reconnect_state['failed'] = True
                        reconnect_state['permanent_failure'] = True
                        raise AndroidStoppedException("No devices attached during reconnection")
                except AndroidStoppedException:
                    raise
                except Exception as adb_error:
                    reconnect_state['failed'] = True
                    reconnect_state['permanent_failure'] = True
                    raise AndroidStoppedException(f"ADB error during reconnection: {adb_error}")

                while not self._connect_to_device(initialize=False):
                    attempts += 1
                    if self.should_stop:
                        self.log("Reconnection stopped by user")
                        reconnect_state['failed'] = True
                        reconnect_state['permanent_failure'] = True
                        raise AndroidStoppedException("Reconnection stopped by user")
                    if attempts >= max_attempts:
                        self.log(f"Reconnection failed after {max_attempts} attempts")
                        reconnect_state['failed'] = True
                        reconnect_state['permanent_failure'] = True
                        raise AndroidStoppedException(f"Reconnection failed after {max_attempts} attempts")
                    self.log(f"Reconnection failed, retrying... ({attempts}/{max_attempts})")

                # Success - mark that we just reconnected so waiting threads know
                reconnect_state['just_reconnected'] = True
                reconnect_state['permanent_failure'] = False

                # Release lock before retrying the function
                lock.release()
                return func(self, *args, **kwargs)

            except AndroidStoppedException:
                # Make sure lock is released on exception
                if lock.locked():
                    lock.release()
                raise
            except:
                # Make sure lock is released on any other exception
                if lock.locked():
                    lock.release()
                raise
    return wrapper


class AndroidStoppedException(Exception):
    """Exception raised when Android connection is stopped by user"""
    pass


# Class-level lock shared across all Android instances for the same device
# Key: serial_number, Value: {'lock': Lock, 'failed': bool}
_reconnect_locks = {}
_reconnect_locks_mutex = threading.Lock()

# ADB command locks - one per device serial to prevent concurrent ADB commands
# This prevents screenshot threads from blocking tap commands
_adb_locks = {}
_adb_locks_mutex = threading.Lock()


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
        should_stop: Flag to signal connection attempts should stop
    """

    def __init__(self, serial: str, device_name: Optional[str] = None):
        """Initialize Android controller and connect to device

        Args:
            serial: Device serial number to connect to (e.g., "emulator-5554")
            device_name: Optional friendly device name for logging (e.g., "Gelvil")

        Note:
            Automatically connects to ADB server at 127.0.0.1:5037
            and attempts connection to specified device
        """
        self.devices: list[Device] = []
        self.device: Optional[Device] = None
        self.serial_number = serial
        self.device_name = device_name or serial  # Use serial as fallback
        self.gui = None
        self.should_stop = False
        self._setup_reconnect_lock()
        self._initialize_connection()

    def _setup_reconnect_lock(self):
        """Setup or get the shared reconnect lock for this device serial"""
        global _reconnect_locks, _reconnect_locks_mutex
        with _reconnect_locks_mutex:
            if self.serial_number not in _reconnect_locks:
                _reconnect_locks[self.serial_number] = {
                    'lock': threading.Lock(),
                    'failed': False
                }
            self._reconnect_state = _reconnect_locks[self.serial_number]

    def _get_adb_lock(self):
        """Get or create the ADB command lock for this device serial

        Returns a lock that should be used to serialize ADB commands to this device.
        This prevents multiple threads (bot loop, screenshot updater, remote commands)
        from sending ADB commands simultaneously, which can cause delays and hangs.
        """
        global _adb_locks, _adb_locks_mutex
        with _adb_locks_mutex:
            if self.serial_number not in _adb_locks:
                _adb_locks[self.serial_number] = threading.Lock()
            return _adb_locks[self.serial_number]

    def _run_with_timeout(self, func, *args, timeout=None, operation_name="ADB operation"):
        """Run a function with a timeout to prevent indefinite hangs

        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            timeout: Timeout in seconds (default: loads from config or DEFAULT_ADB_TIMEOUT)
            operation_name: Name of operation for error messages

        Returns:
            Result of the function call

        Raises:
            ADBTimeoutError: If operation times out
        """
        if timeout is None:
            timeout = _load_adb_timeout()

        future = _adb_executor.submit(func, *args)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            self.log(f"[Warning] {operation_name} timed out after {timeout}s")
            # Note: We can't actually cancel the underlying ADB operation,
            # but we can raise an error to trigger reconnection
            raise ADBTimeoutError(f"{operation_name} timed out after {timeout} seconds")

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
        """Log message through the central logging system

        Args:
            message: Message string to log
        """
        from .utils import log as central_log
        central_log(message)

    # ============================================================================
    # DEVICE CONNECTION & MANAGEMENT
    # ============================================================================

    def stop(self):
        """Signal the Android controller to stop connection attempts

        Sets should_stop flag to True, which causes retry loops to exit
        and raise AndroidStoppedException.
        """
        self.should_stop = True

    def _initialize_connection(self):
        """Initialize ADB connection and connect to target device

        Connects to local ADB server, discovers devices, and connects to
        the device matching self.serial_number. Retries connection up to
        max_reconnect_attempts (from config.json) times before giving up.

        Raises:
            AndroidStoppedException: If should_stop is set, max attempts reached,
                                    or ADB server not running
        """
        adb = Client(host='127.0.0.1', port=5037)

        try:
            self.devices = adb.devices()
        except Exception as e:
            self.log(f"ADB ERROR: ADB server not running - {e}")
            raise AndroidStoppedException(f"ADB server not running: {e}")

        if len(self.devices) == 0:
            self.log('ADB ERROR: No devices attached')
            raise AndroidStoppedException("No devices attached")

        max_attempts = _load_max_reconnect_attempts()
        attempts = 0
        while not self._connect_to_device(initialize=False):
            attempts += 1
            if self.should_stop:
                self.log("Connection stopped by user")
                raise AndroidStoppedException("Connection stopped by user")
            if attempts >= max_attempts:
                self.log(f"Connection failed after {max_attempts} attempts")
                raise AndroidStoppedException(f"Connection failed after {max_attempts} attempts")
            self.log(f"Connection failed, retrying... ({attempts}/{max_attempts})")

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
                if dev_serial is None:
                    continue
                self.log(f"Detected serial: {dev_serial.strip()}")

                if self.serial_number in dev_serial:
                    self.log(f"Connected to device: {self.device_name} (serial: {dev_serial.strip()})")
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
            - Uses ADB lock to prevent concurrent commands from blocking each other
            - Has timeout protection to prevent indefinite hangs
        """
        assert self.device is not None, "Device not connected"

        # Use lock to prevent concurrent ADB commands, with timeout
        lock = self._get_adb_lock()
        if not lock.acquire(timeout=10):
            raise ADBTimeoutError("Could not acquire ADB lock for screencap (timeout)")

        try:
            # Run screencap with timeout protection
            screenshot_bytes = self._run_with_timeout(
                self.device.screencap,
                operation_name="screencap"
            )
        finally:
            lock.release()

        # Validate screenshot data before decoding
        if screenshot_bytes is None or len(screenshot_bytes) < 100:
            self.log(f"[Warning] Screenshot data incomplete ({len(screenshot_bytes) if screenshot_bytes else 0} bytes)")
            raise Exception("Screenshot data incomplete - will retry")

        # Check PNG signature (first 8 bytes)
        png_signature = b'\x89PNG\r\n\x1a\n'
        if not screenshot_bytes.startswith(png_signature):
            self.log("[Warning] Screenshot data is not valid PNG format")
            raise Exception("Invalid PNG data - will retry")

        # Check for PNG end marker (IEND chunk) to ensure complete data
        # This prevents libpng errors from incomplete buffers
        png_end_marker = b'IEND\xaeB`\x82'
        if not screenshot_bytes.endswith(png_end_marker):
            # Also check if IEND is near the end (within last 20 bytes) in case of trailing data
            if png_end_marker not in screenshot_bytes[-20:]:
                raise Exception("PNG data truncated (missing IEND) - will retry")

        # Decode screenshot with OpenCV (faster than PIL)
        # cv.imdecode automatically handles PNG and returns BGR(A) format
        # which is what OpenCV expects - no additional conversion needed
        np_img = cv.imdecode(
            np.frombuffer(screenshot_bytes, dtype=np.uint8),
            cv.IMREAD_UNCHANGED
        )

        # Validate decoded image
        if np_img is None:
            self.log("[Warning] Failed to decode screenshot PNG")
            raise Exception("PNG decode failed - will retry")

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
            Uses ADB lock to prevent concurrent commands from blocking each other.
            Has timeout protection to prevent indefinite hangs.
        """
        # Default to tap coordinates if swipe not specified
        if x2 == -1:
            x2 = x1
        if y2 == -1:
            y2 = y1

        # Execute tap or swipe
        assert self.device is not None, "Device not connected"

        # Use lock to prevent concurrent ADB commands, with timeout
        lock = self._get_adb_lock()
        if not lock.acquire(timeout=10):
            raise ADBTimeoutError("Could not acquire ADB lock for touch (timeout)")

        try:
            if x2 == x1 and y2 == y1:
                if not suppress_log:
                    self.log(f"Touch: ({x1}, {y1})")
                self._run_with_timeout(
                    self.device.shell,
                    f'input tap {x1} {y1}',
                    operation_name="tap"
                )
            else:
                if not suppress_log:
                    self.log(f'Swipe: ({x1}, {y1}) -> ({x2}, {y2}) [{delay}ms]')
                # Swipe timeout should account for the swipe duration
                swipe_timeout = max(_load_adb_timeout(), (delay / 1000) + 10)
                self._run_with_timeout(
                    self.device.shell,
                    f'input swipe {x1} {y1} {x2} {y2} {delay}',
                    timeout=swipe_timeout,
                    operation_name="swipe"
                )
        finally:
            lock.release()

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
            Uses ADB lock to prevent concurrent commands from blocking each other.
            Has timeout protection to prevent indefinite hangs.
        """
        assert self.device is not None, "Device not connected"
        self.log(f'Text input: "{text}"')

        lock = self._get_adb_lock()
        if not lock.acquire(timeout=10):
            raise ADBTimeoutError("Could not acquire ADB lock for send_text (timeout)")

        try:
            self._run_with_timeout(
                self.device.shell,
                f"input text '{text}'",
                operation_name="send_text"
            )
        finally:
            lock.release()

        self.press_enter()

    @auto_reconnect
    def press_enter(self):
        """Press the Enter/Return key (keycode 66)

        See: http://www.temblast.com/ref/akeyscode.htm
        Has timeout protection to prevent indefinite hangs.
        """
        assert self.device is not None, "Device not connected"

        lock = self._get_adb_lock()
        if not lock.acquire(timeout=10):
            raise ADBTimeoutError("Could not acquire ADB lock for press_enter (timeout)")

        try:
            self._run_with_timeout(
                self.device.shell,
                "input keyevent 66",
                operation_name="press_enter"
            )
        finally:
            lock.release()

    @auto_reconnect
    def press_backspace(self, count=1):
        """Press the Backspace key one or more times (keycode 67)

        Args:
            count: Number of times to press backspace (default: 1)

        Has timeout protection to prevent indefinite hangs.
        """
        assert self.device is not None, "Device not connected"

        lock = self._get_adb_lock()
        if not lock.acquire(timeout=10):
            raise ADBTimeoutError("Could not acquire ADB lock for press_backspace (timeout)")

        try:
            for _ in range(count):
                self._run_with_timeout(
                    self.device.shell,
                    "input keyevent 67",
                    operation_name="press_backspace"
                )
        finally:
            lock.release()
