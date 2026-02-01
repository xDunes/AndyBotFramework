"""
List Available ADB Serials

Standalone tool to list all currently available ADB device serial numbers.
This is useful for debugging connection issues and identifying which devices
are currently connected to the ADB server.

Usage:
    python listAvailableSerials.py
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ppadb.client import Client
except ImportError as e:
    print(f"ERROR: Required library not found: {e}")
    print("\nPlease install required dependency:")
    print("  pip install pure-python-adb")
    sys.exit(1)


def log(message: str):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def get_available_serials():
    """Get list of all available ADB device serial numbers

    Returns:
        list: List of serial numbers for all connected devices in 'device' state
    """
    try:
        # Connect to local ADB server
        adb = Client(host='127.0.0.1', port=5037)

        # Get list of connected devices
        devices = adb.devices()

        if len(devices) == 0:
            log("No devices attached to ADB server")
            return []

        log(f"Found {len(devices)} device(s) connected to ADB server")

        available_serials = []

        for dev in devices:
            try:
                # Check device state - only list fully online devices
                dev_state = dev.get_state()

                if dev_state != 'device':
                    # Device is not fully online (could be 'offline', 'unauthorized', etc.)
                    log(f"  Skipping device in state: {dev_state}")
                    continue

                # Get the device serial number
                dev_serial = dev.shell('getprop ro.boot.serialno')

                if dev_serial is None:
                    log("  Found device but could not retrieve serial number")
                    continue

                dev_serial = dev_serial.strip()
                available_serials.append(dev_serial)

            except Exception as e:
                log(f"  Error reading device info: {e}")
                continue

        return available_serials

    except Exception as e:
        log(f"ERROR: Failed to connect to ADB server - {e}")
        log("\nMake sure:")
        log("  1. ADB server is running")
        log("  2. Devices are connected and authorized")
        log("  3. Run 'adb devices' in terminal to verify")
        return []


def main():
    """Main entry point"""
    print("=" * 60)
    print("ADB Available Serials - Device Serial Number Lister")
    print("=" * 60)
    print()

    log("Connecting to ADB server...")
    serials = get_available_serials()

    print()
    print("=" * 60)

    if serials:
        log(f"Found {len(serials)} available device(s):")
        print()
        for i, serial in enumerate(serials, 1):
            print(f"  {i}. {serial}")
    else:
        log("No available devices found")
        log("\nTroubleshooting:")
        log("  - Check that devices are powered on and connected")
        log("  - Run 'adb devices' to see if ADB can detect them")
        log("  - Check USB cables and connections")
        log("  - For emulators (LDPlayer), ensure they are fully started")

    print()
    print("=" * 60)

    # Return exit code based on whether devices were found
    return 0 if serials else 1


if __name__ == '__main__':
    sys.exit(main())
