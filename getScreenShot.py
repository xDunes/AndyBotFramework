#!/usr/bin/env python3
"""
Screenshot utility for Android devices via ADB.
Captures screenshots from connected Android devices and saves them to file.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import cv2 as cv
import numpy as np

from android import Android

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_NO_DEVICE = 1
EXIT_CONNECTION_ERROR = 2
EXIT_CAPTURE_ERROR = 3
EXIT_SAVE_ERROR = 4
EXIT_INVALID_ARGS = 5


def load_config(config_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config file. If None, tries default locations.

    Returns:
        Configuration dictionary or None if not found
    """
    if config_path:
        paths = [Path(config_path)]
    else:
        # Try default config locations
        paths = [
            Path('config.json'),
            Path('config.example.json'),
            Path.home() / '.apex-girl' / 'config.json',
        ]

    for path in paths:
        if path.exists():
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                    logger.debug(f"Loaded configuration from: {path}")
                    return config
            except Exception as e:
                logger.warning(f"Failed to load config from {path}: {e}")
                continue

    logger.debug("No configuration file found, using defaults")
    return None


def get_serial_from_config(config: Optional[Dict[str, Any]], user: str) -> Optional[str]:
    """
    Get device serial from configuration file.

    Args:
        config: Configuration dictionary
        user: User/device name

    Returns:
        Serial number or None if not found
    """
    if not config:
        return None

    devices = config.get('devices', {})
    device_info = devices.get(user)

    if device_info:
        return device_info.get('serial')

    return None


class ScreenshotCapture:
    """Handles screenshot capture from Android devices."""

    def __init__(self, device_serial: str):
        """
        Initialize screenshot capture for a device.

        Args:
            device_serial: Serial number of the Android device
        """
        self.device_serial = device_serial
        self.android = None

    def connect(self) -> bool:
        """
        Connect to the Android device.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to device: {self.device_serial}")
            self.android = Android(self.device_serial)
            logger.info("Successfully connected to device")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to device: {e}")
            return False

    def capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """
        Capture screenshot from the device.

        Args:
            region: Optional tuple of (x1, y1, x2, y2) to crop the screenshot

        Returns:
            Screenshot as numpy array, or None if capture failed
        """
        if not self.android:
            logger.error("Not connected to device. Call connect() first.")
            return None

        try:
            logger.info("Capturing screenshot...")
            if region:
                # Note: Region cropping is deprecated - capture_screen() ignores crop parameters
                logger.warning(f"Region parameter {region} is deprecated and will be ignored")
            screenshot = self.android.capture_screen()
            logger.info("Captured full screenshot")
            return screenshot
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    def save(self, screenshot: np.ndarray, output_path: str, format: str = 'png') -> Optional[str]:
        """
        Save screenshot to file.

        Args:
            screenshot: Screenshot as numpy array (already in BGR/BGRA format from Android class)
            output_path: Path where to save the screenshot
            format: Image format (png, jpg, bmp)

        Returns:
            Path to saved file if successful, None otherwise
        """
        try:
            # Ensure the output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Add extension if not present
            if not output_file.suffix:
                output_file = output_file.with_suffix(f'.{format}')

            logger.info(f"Saving screenshot to: {output_file}")

            # The Android.capture_screen() already returns image in BGR/BGRA format (OpenCV format)
            # So we can save it directly without color conversion
            success = cv.imwrite(str(output_file), screenshot)

            if success:
                logger.info(f"Screenshot saved successfully: {output_file}")
                return str(output_file)
            else:
                logger.error("Failed to save screenshot")
                return None

        except Exception as e:
            logger.error(f"Error saving screenshot: {e}")
            return None


def parse_region(region_str: str) -> Tuple[int, int, int, int]:
    """
    Parse region string into coordinates.

    Args:
        region_str: Region in format "x1,y1,x2,y2"

    Returns:
        Tuple of (x1, y1, x2, y2)

    Raises:
        ValueError: If region format is invalid
    """
    try:
        coords = [int(x.strip()) for x in region_str.split(',')]
        if len(coords) != 4:
            raise ValueError("Region must have exactly 4 coordinates")
        return tuple(coords)
    except Exception as e:
        raise ValueError(f"Invalid region format. Expected 'x1,y1,x2,y2': {e}")


def open_in_mspaint(file_path: str) -> bool:
    """
    Open a file in MS Paint (Windows only).

    Args:
        file_path: Path to the image file to open

    Returns:
        True if successfully opened, False otherwise
    """
    try:
        # Convert to absolute path
        abs_path = str(Path(file_path).resolve())

        logger.debug(f"Opening {abs_path} in MS Paint")

        # Explicitly call mspaint.exe to avoid default image viewer
        if sys.platform == 'win32':
            # Use subprocess.Popen to avoid blocking
            subprocess.Popen(['mspaint.exe', abs_path])
            logger.info("Opened screenshot in MS Paint")
            return True
        else:
            # For non-Windows, try using mspaint.exe via subprocess
            try:
                subprocess.Popen(['mspaint.exe', abs_path])
                logger.info("Opened screenshot in MS Paint")
                return True
            except FileNotFoundError:
                logger.warning("MS Paint not available on this platform")
                return False
    except Exception as e:
        logger.error(f"Failed to open in MS Paint: {e}")
        return False


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Capture screenshots from Android devices via ADB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s Device1                              # Capture from Device1
  %(prog)s Device1 -o screenshot.png            # Save to specific file
  %(prog)s Device1 -r 100,100,500,500           # Capture region
  %(prog)s Device1 -f jpg -v                    # Save as JPEG with verbose output
  %(prog)s Device1 -s emulator-5554             # Use serial directly
        """
    )

    parser.add_argument(
        'user',
        nargs='?',
        help='User/device name from Toons configuration'
    )

    parser.add_argument(
        '-s', '--serial',
        help='Device serial number (overrides user lookup)'
    )

    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file (JSON)'
    )

    parser.add_argument(
        '-o', '--output',
        default='tempScreenShot.png',
        help='Output file path (default: tempScreenShot.png)'
    )

    parser.add_argument(
        '-r', '--region',
        help='Capture region as "x1,y1,x2,y2"'
    )

    parser.add_argument(
        '-f', '--format',
        choices=['png', 'jpg', 'bmp'],
        default='png',
        help='Output image format (default: png)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress all output except errors'
    )

    parser.add_argument(
        '-p', '--paint',
        action='store_true',
        help='Open screenshot in MS Paint after capture (Windows)'
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the screenshot utility.

    Returns:
        Exit code
    """
    args = parse_arguments()

    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)

    # Load configuration file if specified
    config = load_config(args.config)

    # Get screenshot config settings with defaults
    screenshot_config = config.get('screenshot', {}) if config else {}
    default_open_in_paint = screenshot_config.get('open_in_paint', False)

    # Get default device from config if user not specified
    default_device = config.get('default_device') if config else None
    user = args.user if args.user else default_device

    # Determine device serial (priority: CLI --serial > config file)
    device_serial = None

    if args.serial:
        device_serial = args.serial
        logger.debug(f"Using serial from command line: {device_serial}")
    elif user:
        # Get serial from config file
        if config:
            device_serial = get_serial_from_config(config, user)
            if device_serial:
                logger.debug(f"Resolved user '{user}' to serial from config: {device_serial}")
            else:
                logger.error(f"Unknown user: {user}")
                available_users = list(config.get('devices', {}).keys())
                if available_users:
                    logger.error(f"Available users: {', '.join(available_users)}")
                return EXIT_INVALID_ARGS
        else:
            logger.error("Configuration file not found. Please create config.json")
            return EXIT_INVALID_ARGS
    else:
        logger.error("Either --serial, user argument, or default_device in config is required")
        return EXIT_INVALID_ARGS

    # Parse region if provided
    region = None
    if args.region:
        try:
            region = parse_region(args.region)
            logger.debug(f"Using region: {region}")
        except ValueError as e:
            logger.error(f"Invalid region: {e}")
            return EXIT_INVALID_ARGS

    # Create screenshot capture instance
    capturer = ScreenshotCapture(device_serial)

    # Connect to device
    if not capturer.connect():
        logger.error("Failed to connect to device")
        return EXIT_CONNECTION_ERROR

    # Capture screenshot
    screenshot = capturer.capture(region)
    if screenshot is None:
        logger.error("Failed to capture screenshot")
        return EXIT_CAPTURE_ERROR

    # Save screenshot
    saved_path = capturer.save(screenshot, args.output, args.format)
    if not saved_path:
        logger.error("Failed to save screenshot")
        return EXIT_SAVE_ERROR

    logger.info("Screenshot capture completed successfully")

    # Open in MS Paint if requested via CLI arg or config default
    should_open_paint = args.paint or default_open_in_paint
    if should_open_paint:
        open_in_mspaint(saved_path)

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
