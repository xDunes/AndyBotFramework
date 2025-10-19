# Apex-Girl Bot Framework

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Python-based automation framework for Android games with GUI interface, featuring template-based bot creation, OCR support, and multi-device management.

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Install Python Dependencies](#2-install-python-dependencies)
  - [3. Install and Configure Tesseract OCR](#3-install-and-configure-tesseract-ocr)
  - [4. Setup Android Emulator (LDPlayer)](#4-setup-android-emulator-ldplayer)
  - [5. Configure Devices](#5-configure-devices)
- [Primary Files](#-primary-files)
- [Utility Scripts](#-utility-scripts)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Creating Your Own Bot](#-creating-your-own-bot)
- [Troubleshooting](#-troubleshooting)
- [Version Tracking](#-version-tracking)
- [Contributing](#-contributing)

---

## ✨ Features

- 🎮 **Template-based bot creation** - Easy framework for building game automation
- 🖥️ **Multi-device support** - Manage multiple Android emulators simultaneously
- 🎯 **Image recognition** - OpenCV-based template matching for game elements
- 📝 **OCR support** - Tesseract integration for reading in-game text
- 🎨 **GUI interface** - Tkinter-based control panel with real-time logging
- 🔧 **Utility tools** - Screenshot capture, window arrangement, and more
- 📊 **Configurable logging** - Toggle verbose output and debug information

---

## 📦 Requirements

### System Requirements
- **Operating System:** Windows 10/11 (for LDPlayer and MS Paint integration)
- **Python:** 3.6 or higher
- **Android Emulator:** LDPlayer (recommended)
- **ADB:** Android Debug Bridge (included with LDPlayer)

### Python Packages
- `ppadb` - Pure Python ADB client
- `opencv-python` - Computer vision and image processing
- `numpy` - Array operations
- `Pillow` (PIL) - Image handling
- `pytesseract` - Python wrapper for Tesseract OCR
- `keyboard` - Keyboard event handling
- `tkinter` - GUI framework (usually included with Python)

---

## 🚀 Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd Apex-Girl
```

### 2. Install Python Dependencies

```bash
pip install ppadb opencv-python numpy Pillow pytesseract keyboard
```

**Note:** `tkinter` is usually included with Python on Windows. If not available, reinstall Python and ensure the tkinter option is enabled during installation.

### 3. Install and Configure Tesseract OCR

Tesseract is required for reading in-game text (numbers, levels, etc.).

#### Windows Installation

1. **Download Tesseract:**
   - Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
   - Use the latest version (e.g., `tesseract-ocr-w64-setup-5.3.x.exe`)

2. **Install Tesseract:**
   - Run the installer
   - **Important:** Note the installation path (default: `C:\Program Files\Tesseract-OCR`)
   - Ensure "Add to PATH" is checked during installation

3. **Configure Python to use Tesseract:**

   Add Tesseract to your system PATH, or configure it in your code:

   ```python
   # Add this to your bot script if needed
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

4. **Verify Installation:**

   ```bash
   tesseract --version
   ```

   You should see output like:
   ```
   tesseract 5.3.x
   ```

### 4. Setup Android Emulator (LDPlayer)

#### Download and Install LDPlayer

1. Download LDPlayer from: https://www.ldplayer.net/
2. Install LDPlayer
3. Launch LDPlayer

#### Configure LDPlayer Settings

1. **Set Resolution:**
   - Open LDPlayer settings
   - Navigate to **Display** settings
   - Set resolution to: **Phone 540x960**
   - Apply and restart emulator

2. **Enable ADB Debugging:**
   - Open LDPlayer settings
   - Navigate to **Other** settings
   - Find **ADB debugging**
   - Set to: **Enable local connection**
   - Note: You may see the ADB port (default: 5037)

3. **Start ADB Server:**

   ```bash
   adb start-server
   ```

4. **Verify Connection:**

   ```bash
   adb devices
   ```

   You should see output like:
   ```
   List of devices attached
   emulator-5554   device
   ```

### 5. Configure Devices

#### Get Device Serial Number

To configure your devices, you need to find each device's **hardware serial number** (not the ADB device ID).

**Important:**
- ✅ Use hardware serial: `00ce49b2` (8 hex characters)
- ❌ Don't use ADB device ID: `emulator-5554` or `127.0.0.1:5555`

**Recommended Method: Let the bot detect it**

Run your bot or screenshot tool with verbose mode, and it will automatically detect and log the hardware serial:

```bash
python getScreenShot.py Device1 -v
```

Or when connecting to a device:

```bash
python -c "from android import Android; a = Android('test')"
```

Look for output like:
```
Detected serial: 00ce49b2
Connected to device: 00ce49b2
```

The bot automatically runs `adb shell getprop ro.boot.serialno` to retrieve the hardware serial.

**LDPlayer Users:**
- **Do NOT use the original LDPlayer instance** - its serial changes after updates
- Always use **cloned instances** for persistent serials
- Clone in LDPlayer: Right-click instance → Clone
- Each clone gets a permanent hardware serial

#### Create config.json

Create a `config.json` file in the project root:

```json
{
  "devices": {
    "Device1": {
      "serial": "00ce49b2",
      "concerttarget": -1,
      "stadiumtarget": 2
    },
    "Device2": {
      "serial": "01af38d4",
      "concerttarget": -1,
      "stadiumtarget": 2
    }
  },
  "adb": {
    "host": "127.0.0.1",
    "port": 5037
  },
  "screenshot": {
    "default_format": "png",
    "default_output": "tempScreenShot.png"
  }
}
```

**Configuration Fields:**
- `serial`: Hardware serial number (8 hex chars, found using methods above)
- `concerttarget`: Game-specific setting (use -1 for default)
- `stadiumtarget`: Game-specific setting

---

## 📁 Primary Files

### Core Bot Files

#### **ApexGirlBot.py**
The main bot implementation for the Apex Girl game. Features:
- Full GUI interface with Tkinter
- Multi-function automation (concerts, rally, studio, etc.)
- OCR integration for reading in-game numbers
- Auto-unchecking completed tasks
- Screenshot capture functionality
- Real-time logging window

**Usage:**
```bash
python ApexGirlBot.py <username>
```

Example:
```bash
python ApexGirlBot.py Device1
```

#### **botTemplate.py**
A barebones template script demonstrating how to create a bot for any game. Use this as a starting point for building automation for other Android games.

**Features:**
- Minimal bot structure
- Example image matching
- Basic click automation
- Template for adding game-specific functions

**Usage:**
```bash
python botTemplate.py <username>
```

---

## 🔧 Utility Scripts

### **ArrangeWindows.py**
Automatically arranges multiple LDPlayer windows side-by-side on your screen.

**Purpose:**
- Manage multiple emulator instances
- Align windows for easy monitoring
- Position GUI windows below emulators

**Usage:**
```bash
python ArrangeWindows.py
```

The script will:
1. Detect all open LDPlayer windows
2. Position them side-by-side horizontally
3. Calculate positions for GUI windows below them

### **getScreenShot.py**
Capture screenshots from Android devices via ADB for creating image templates ("needles") and finding pixel coordinates.

**Purpose:**
- Capture game screens for template creation
- Find exact pixel coordinates for click actions
- Create image needles for `findAndClick()` operations

**Basic Usage:**
```bash
# Capture screenshot and open in MS Paint
python getScreenShot.py Device1 -p

# Save to specific file
python getScreenShot.py Device1 -o screenshots/my_game.png

# Capture specific region
python getScreenShot.py Device1 -r 100,100,500,500 -p

# Verbose mode
python getScreenShot.py Device1 -v -p
```

**Command-Line Options:**
```
usage: getScreenShot.py [-h] [-s SERIAL] [-c CONFIG] [-o OUTPUT] [-r REGION]
                        [-f {png,jpg,bmp}] [-v] [-q] [-p]
                        [user]

Positional arguments:
  user                  User/device name from config.json

Optional arguments:
  -h, --help            Show help message
  -s SERIAL             Device serial number (overrides user lookup)
  -c CONFIG             Path to configuration file
  -o OUTPUT             Output file path (default: tempScreenShot.png)
  -r REGION             Capture region as "x1,y1,x2,y2"
  -f {png,jpg,bmp}      Output image format
  -v, --verbose         Enable verbose logging
  -q, --quiet           Suppress all output except errors
  -p, --paint           Open screenshot in MS Paint after capture
```

**Workflow for Creating Needles:**

1. **Capture a screenshot:**
   ```bash
   python getScreenShot.py Device1 -p
   ```

2. **Crop the target element in MS Paint:**
   - Use the Select tool to highlight the game element (button, icon, etc.)
   - Crop to selection (Ctrl+Shift+X)
   - Save to `findimg/` folder with a descriptive name
   - Example: `findimg/studio.png`, `findimg/start.png`

3. **Find pixel coordinates in MS Paint:**
   - Open the screenshot in MS Paint
   - Hover your mouse over the desired location
   - Look at the bottom-left corner for pixel coordinates (e.g., "150, 230")
   - Use these coordinates in `clickCoords(x, y)` or `touch(x, y)`

4. **Use in your bot:**
   ```python
   # Using image template
   bot.find_and_click('studio')

   # Using coordinates
   bot.tap(150, 230)
   ```

**Advanced Examples:**

```bash
# Capture and save to dated folder
python getScreenShot.py Device1 -o "screenshots/$(date +%Y%m%d)/screen.png" -p

# Capture region and open immediately
python getScreenShot.py Device1 -r 0,0,540,100 -p

# Quiet mode with specific format
python getScreenShot.py Device1 -o needle.jpg -f jpg -q

# Use device serial directly
python getScreenShot.py -s 00ce49b2 -o output.png -p
```

**Exit Codes:**
- `0` - Success
- `1` - No device found
- `2` - Connection error
- `3` - Screenshot capture error
- `4` - File save error
- `5` - Invalid arguments

---

## ⚙️ Configuration

### config.json Structure

```json
{
  "devices": {
    "DeviceName": {
      "serial": "00ce49b2",
      "concerttarget": -1,
      "stadiumtarget": 2
    }
  },
  "adb": {
    "host": "127.0.0.1",
    "port": 5037
  },
  "screenshot": {
    "default_format": "png",
    "default_output": "tempScreenShot.png"
  }
}
```

### Finding Your Device Serial

Use the Android class to detect the hardware serial:

```python
from android import Android

# This will show detected hardware serial numbers
andy = Android("test")
```

The script will automatically run `adb shell getprop ro.boot.serialno` and display the 8-character hardware serial (e.g., `00ce49b2`).

**Note:** Do not use the ADB device ID from `adb devices` (like `emulator-5554`). Always use the hardware serial.

---

## 🎮 Usage

### Running ApexGirlBot

1. **Start LDPlayer and launch the game**

2. **Run the bot:**
   ```bash
   python ApexGirlBot.py Device1
   ```

3. **GUI Controls:**
   - **Function Checkboxes:** Enable/disable specific bot actions
     - Street, Artists, Studio, Tour, Group
     - Concert, Help, Coin, Heal, spamHQ, Rally
   - **Settings:**
     - Sleep: Delay between action cycles (seconds)
     - Seconds: Screenshot capture interval (0 = single capture)
     - Show NO CLICK: Toggle logging of failed image matches
   - **Buttons:**
     - **Start/Stop:** Toggle button to control bot execution
     - **Screenshot:** Capture screenshots (single or continuous)

4. **Log Window:**
   - Real-time display of bot actions
   - Timestamps for all events
   - Color-coded status (green=running, red=stopped)
   - 300-line buffer with auto-scroll

### GUI Features

- **Multi-device support:** Run multiple bot windows simultaneously
- **Auto-positioning:** Windows arrange based on device order in config.json
- **Status indicators:** Live status and current action display
- **Function toggle:** Enable/disable individual bot functions
- **Smart auto-uncheck:** Studio unchecks when target reached
- **Persistent logging:** Scroll through 300 most recent log entries

---

## 🛠️ Creating Your Own Bot

> **📚 New to bot creation? Check out our comprehensive beginner's guide: [NEWBOT.md](NEWBOT.md)**
> This tutorial walks you through creating your first bot step-by-step, from setup to advanced features.

Use `botTemplate.py` as a starting point for creating automation for other games.

### Basic Bot Structure

```python
from android import Android
from bot import BOT

# Initialize Android connection
andy = Android(serial="your-device-serial")

# Create bot instance
bot = BOT(andy)

# Main bot loop
while True:
    # Your automation logic here
    bot.find_and_click('button_name')
    bot.tap(x, y)

    # Add delays
    time.sleep(1)
```

### Key Bot Methods

```python
# ============================================================================
# IMAGE RECOGNITION & CLICKING
# ============================================================================

# Find and click template images
bot.find_and_click('image_name')  # Find and click template
bot.find_and_click('image_name', tap=False)  # Just check if exists
bot.find_and_click('image_name', offset_x=10, offset_y=20)  # Click with offset
bot.find_and_click('image_name', accuracy=0.95)  # Adjust match threshold

# ============================================================================
# SCREEN INTERACTION - Touch & Gestures
# ============================================================================

bot.tap(x, y)  # Tap at coordinates
bot.swipe(x1, y1, x2, y2, duration=500)  # Swipe gesture

# ============================================================================
# SCREEN CAPTURE
# ============================================================================

screenshot = bot.screenshot()  # Capture current screen

# ============================================================================
# TEXT INPUT & KEYBOARD
# ============================================================================

bot.type_text('Hello')  # Type text followed by Enter
bot.press_enter()  # Press Enter key
bot.press_backspace(count=5)  # Press Backspace N times

# ============================================================================
# IMAGE ANALYSIS
# ============================================================================

color = bot.get_pixel_color(screenshot, x, y)  # Get RGB color at pixel
processed = bot.prepare_image_for_ocr(image)  # Prepare image for OCR
needle = bot.get_needle('name')  # Get loaded template

# ============================================================================
# LOGGING
# ============================================================================

bot.log("Your message")  # Log to GUI or console
```


### Creating Needle Images

1. **Capture a screenshot:**
   ```bash
   python getScreenShot.py Device1 -p
   ```

2. **Crop the element in MS Paint:**
   - Select the button/icon you want to detect
   - Crop to selection
   - Save to `findimg/button_name.png`

3. **Use in your bot:**
   ```python
   bot.find_and_click('button_name')
   ```

### Example: Simple Auto-Clicker Bot

```python
from android import Android
from bot import BOT
import time

# Connect to device
andy = Android("00ce49b2")
bot = BOT(andy)

# Enable GUI logging (if using GUI)
# bot.set_gui(gui_instance)

# Main loop
while True:
    # Try to find and click the "collect" button
    if bot.find_and_click('collect', accuracy=0.9):
        bot.log("Clicked collect button")
        time.sleep(2)
    else:
        bot.log("Collect button not found")

    # Click at specific coordinate
    bot.tap(270, 460)
    time.sleep(1)
```

---

## 🔧 Troubleshooting

### ADB Issues

**Problem:** "adb not running!"

**Solution:**
```bash
adb start-server
```

**Problem:** "no devices attached"

**Solution:**
1. Check emulator is running
2. Verify ADB debugging enabled in LDPlayer settings
3. Run `adb devices` to confirm connection
4. Restart ADB:
   ```bash
   adb kill-server
   adb start-server
   ```

### Tesseract OCR Issues

**Problem:** "TesseractNotFoundError"

**Solution:**
1. Ensure Tesseract is installed
2. Add to system PATH or configure in code:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

**Problem:** OCR not reading numbers correctly

**Solution:**
- Ensure game uses clear, readable fonts
- Adjust OCR config parameters
- Preprocess images (contrast, threshold)

### Image Matching Issues

**Problem:** `find_and_click()` not finding images

**Solution:**
1. **Check accuracy threshold:** Lower the accuracy value
   ```python
   bot.find_and_click('button', accuracy=0.85)  # Lower = more lenient
   ```

2. **Verify needle image:**
   - Ensure cropped image matches game exactly
   - Use same resolution (540x960)
   - Crop tightly around the element

3. **Enable debug logging:**
   ```python
   # In GUI, enable "Show NO CLICK" checkbox
   # Or check console output for accuracy values
   ```

4. **Test image manually:**
   ```python
   # Capture current screen
   sc = bot.screenshot()

   # Check if element exists
   found = bot.find_and_click('button', screenshot=sc, tap=False)
   print(f"Found: {found}")
   ```

### Connection Issues

**Problem:** Device keeps reconnecting

**Solution:**
- Check USB cable (if physical device)
- Increase emulator memory allocation
- Close other ADB applications
- Use wired connection instead of wireless ADB

### Performance Issues

**Problem:** Bot running slowly

**Solution:**
1. Reduce screenshot frequency
2. Increase sleep delays between actions
3. Close unused emulator instances
4. Allocate more CPU/RAM to LDPlayer

---

## 📝 Tips and Best Practices

### Bot Development

1. **Start simple:** Use `botTemplate.py` and add one function at a time
2. **Test frequently:** Run small sections before building complex logic
3. **Use logging:** Add `bot.log()` statements to track execution
4. **Handle errors:** Wrap risky operations in try/except blocks
5. **Add delays:** Use `time.sleep()` to avoid overwhelming the game

### Image Template Creation

1. **Unique elements:** Choose distinct UI elements for reliable matching
2. **Avoid text:** Text can change; prefer icons and buttons
3. **Proper cropping:** Include minimal background in needles
4. **Consistent resolution:** Always use 540x960 screenshots
5. **Descriptive names:** Name needles clearly (e.g., `studio_button.png`)

### Multi-Device Management

1. **Stagger start times:** Don't start all bots simultaneously
2. **Monitor logs:** Check for errors across all instances
3. **Resource allocation:** Ensure system has enough RAM/CPU
4. **Window arrangement:** Use `ArrangeWindows.py` for organization

---

## 📄 License

Part of the Apex-Girl project.

---

## 🔖 Version Tracking

This project uses [Semantic Versioning](https://semver.org/) with automated version management.

### Version Format

**MAJOR.MINOR.BUILD** (e.g., 1.2.34)

- **MAJOR**: Breaking changes, major feature overhauls
- **MINOR**: New features, significant improvements
- **BUILD**: Bug fixes, small improvements, refactoring (auto-incremented)

### Managing Versions

#### View Current Version
```bash
python version_manager.py show
```

#### Add a Change (Auto-increments Build)
```bash
python version_manager.py add "Fixed bug in image matching"
```

This will:
- Automatically increment the build number (e.g., 0.1.5 → 0.1.6)
- Add the change to the [Unreleased] section in CHANGELOG.md
- Update version.py

#### Increment Minor Version (Summarizes Build Changes)
```bash
python version_manager.py minor
```

This will:
- Increment minor version and reset build to 0 (e.g., 0.1.6 → 0.2.0)
- Create a new release section in CHANGELOG.md
- Summarize all build changes from [Unreleased] section
- Clear the [Unreleased] section

#### Increment Major Version
```bash
python version_manager.py major
```

This will:
- Increment major version and reset minor/build to 0 (e.g., 0.2.5 → 1.0.0)
- Create a new major release section in CHANGELOG.md
- List all minor versions included in this major release
- Clear the [Unreleased] section

### Workflow Example

```bash
# Make some changes and add them
python version_manager.py add "Added new OCR preprocessing"
# Version: 0.1.0 → 0.1.1

python version_manager.py add "Fixed screenshot capture bug"
# Version: 0.1.1 → 0.1.2

python version_manager.py add "Improved GUI responsiveness"
# Version: 0.1.2 → 0.1.3

# Ready to release minor version
python version_manager.py minor
# Version: 0.1.3 → 0.2.0
# Summarizes all 3 build changes into 0.2.0 release notes
```

### Changelog

See [CHANGELOG.md](CHANGELOG.md) for a complete history of changes.

---

## 🤝 Contributing

When modifying or extending this framework:

1. **Maintain backward compatibility**
2. **Follow existing code structure**
3. **Add logging to new functions**
4. **Track your changes:**
   ```bash
   python version_manager.py add "Description of your change"
   ```
5. **Update this README with new features**
6. **Test with multiple devices**
7. **Include docstrings for new methods**
8. **Update CHANGELOG.md** (automatically done by version_manager.py)

---

## 📞 Support

For issues or questions:

1. Check this README thoroughly
2. Review Troubleshooting section
3. Check console/log output for error messages
4. Verify ADB connection with `adb devices`
5. Test with `getScreenShot.py` to isolate device issues

---

**Happy Botting! 🎮🤖**
