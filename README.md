# Andy Bot Framework

[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)](docs/CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Python-based automation framework for Android games with GUI interface, featuring template-based bot creation, OCR support, and multi-device management.

## Table of Contents

- [Features](#-features)
- [Project Structure](#-project-structure)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Creating Your Own Bot](#-creating-your-own-bot)
- [Web Interface & Remote Monitoring](#-web-interface--remote-monitoring)
- [Utility Scripts](#-utility-scripts)
- [Troubleshooting](#-troubleshooting)
- [Version Tracking](#-version-tracking)
- [Contributing](#-contributing)

---

## Features

- **Template-based bot creation** - Easy framework for building game automation
- **Modular architecture** - Clean separation of core framework, game logic, and GUI
- **Multi-device support** - Manage multiple Android emulators simultaneously
- **Image recognition** - OpenCV-based template matching for game elements
- **OCR support** - Tesseract integration for reading in-game text
- **GUI interface** - Tkinter-based control panel with real-time logging
- **Web interface** - Remote monitoring and control via browser (desktop & mobile)
- **State monitoring** - Real-time multi-bot state tracking with SQLite
- **Debug logging system** - SQLite-based persistent logging with screenshot storage
- **LogViewer** - Standalone debug log viewer with session browsing and inline image display
- **Auto-start capability** - Bots can auto-connect and start on launch
- **Control key override** - Hold Ctrl to skip functions without stopping the bot
- **ADB command serialization** - Thread-safe ADB access prevents command conflicts

---

## Project Structure

```
Apex-Girl/
├── start_bot.py            # Unified bot launcher for all games
├── master.conf             # Global device settings (ADB, LDPlayer, serials)
├── apex_girl.conf          # Game-specific config (functions, commands)
│
├── core/                   # Core framework (game-agnostic)
│   ├── __init__.py         # Package exports
│   ├── android.py          # ADB device communication
│   ├── bot.py              # BOT class - image recognition & control
│   ├── bot_loop.py         # Main bot execution loop
│   ├── config_loader.py    # Configuration utilities
│   ├── ldplayer.py         # LDPlayer emulator control
│   ├── log_database.py     # SQLite debug logging
│   ├── ocr.py              # OCR utilities
│   ├── state_manager.py    # Web interface state management
│   └── utils.py            # Shared utilities and logging
│
├── games/                  # Game-specific modules
│   ├── apex_girl/          # Apex Girl game implementation
│   │   ├── __init__.py
│   │   ├── functions.py    # Game automation functions
│   │   ├── commands.py     # Command button handlers
│   │   └── findimg/        # Needle images for Apex Girl
│   └── template/           # Template for new games
│       ├── __init__.py
│       ├── functions.py    # Placeholder example functions
│       ├── commands.py     # Example command handlers
│       └── findimg/        # Needle images for your game
│
├── gui/                    # GUI components
│   ├── __init__.py
│   └── bot_gui.py          # Config-driven Tkinter GUI
│
├── web/                    # Web interface
│   ├── server.py           # Flask API server
│   ├── static/             # Frontend assets
│   └── README.md           # Web interface documentation
│
├── tools/                  # Utility scripts
│   ├── ArrangeWindows.py   # Window arrangement utility
│   ├── getScreenShot.py    # Screenshot capture tool
│   ├── LogViewer.py        # Debug log viewer
│   ├── version.py          # Version info
│   └── version_manager.py  # Version management
│
├── docs/                   # Documentation
│   ├── CHANGELOG.md        # Version history
│   ├── NEWBOT.md           # Bot creation guide
│   └── STATE_MONITORING_README.md  # State system docs
│
├── logs/                   # Debug log databases
├── screenshots/            # Captured screenshots
└── state/                  # State monitoring database
```

---

## Requirements

### System Requirements
- **Operating System:** Windows 10/11 (for LDPlayer and MS Paint integration)
- **Python:** 3.8 or higher
- **Android Emulator:** LDPlayer (recommended)
- **ADB:** Android Debug Bridge (included with LDPlayer)

### Python Packages
```bash
pip install ppadb opencv-python numpy Pillow pytesseract keyboard
```

**Note:** `tkinter` is usually included with Python on Windows.

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd AndyBotFramework
```

### 2. Install Python Dependencies

```bash
pip install ppadb opencv-python numpy Pillow pytesseract keyboard
```

### 3. Install Tesseract OCR (Optional - for text reading)

1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install and note the path (default: `C:\Program Files\Tesseract-OCR`)
3. Add to system PATH or configure in code

### 4. Setup LDPlayer

1. Download from: https://www.ldplayer.net/
2. Set resolution to **Phone 540x960**
3. Enable **ADB debugging** (Settings > Other)
4. **Important:** Use cloned instances, not the original (serials persist through updates)

---

## Configuration

Configuration is split into two files in the project root:
- **master.conf** - Global settings (devices, ADB, LDPlayer path)
- **\<game\>.conf** - Game-specific settings (e.g., `apex_girl.conf`, `template.conf`)

### master.conf

Create `master.conf` in the project root with global device settings:

```json
{
  "LDPlayerPath": "C:\\LDPlayer\\LDPlayer9\\",
  "max_reconnect_attempts": 10,
  "devices": {
    "Device1": {
      "email": "user1@example.com",
      "index": 1,
      "window": "LDPlayer-1",
      "serial": "00ce49b2"
    },
    "Device2": {
      "email": "user2@example.com",
      "index": 2,
      "window": "LDPlayer-2",
      "serial": "1a2b3c4d"
    }
  },
  "adb": {
    "host": "127.0.0.1",
    "port": 5037
  },
  "screenshot": {
    "default_format": "png",
    "default_output": "tempScreenShot.png",
    "open_in_paint": true
  }
}
```

### Game Config (\<game\>.conf)

Each game has its own config file in the project root (e.g., `apex_girl.conf`):

```json
{
  "app_name": "My Game Bot",
  "app_title": "My Game Bot Remote Monitor",
  "app_package": "com.example.game",
  "function_layout": [
    ["doCollectDaily", "doAutoBattle"],
    ["doCollectMail"]
  ],
  "commands": [
    {"id": "quick_collect", "label": "Quick Collect", "command_type": "command"},
    {"id": "start_stop", "label": "Start", "command_type": "bot_control"}
  ],
  "bot_settings": [
    {"id": "sleep_time", "label": "Sleep Time", "type": "number", "default": 1}
  ],
  "cooldowns": {
    "doCollectDaily": 86400
  },
  "auto_uncheck": [],
  "devices": {
    "Device1": {
      "concerttarget": -1,
      "stadiumtarget": 2
    }
  }
}
```

**Note:** Device-specific game settings (like `concerttarget`) go in the game config, while global device info (serial, window, email) stays in master.conf. The configs are automatically merged at runtime.

### Finding Device Serial

The bot automatically detects the hardware serial number. Run your bot and look for:
```
Detected serial: 00ce49b2
Connected to device: 00ce49b2
```

**Important:** Use the 8-character hardware serial (e.g., `00ce49b2`), NOT the ADB device ID (e.g., `emulator-5554`).

---

## Usage

### Running a Bot

```bash
python start_bot.py -g <game> -d <device> [options]
```

Options:
- `-g, --game` - Game module name (folder in games/)
- `-d, --device` - Device name (must exist in master.conf)
- `-a, --auto-start` - Auto-start the bot on launch
- `-l, --list-games` - List available games and exit

Examples:
```bash
# Run Apex Girl bot for device Gelvil
python start_bot.py -g apex_girl -d Gelvil

# Run with auto-start
python start_bot.py -g apex_girl -d Gelvil --auto-start

# List available games
python start_bot.py --list-games
```

### GUI Controls

- **Function Checkboxes:** Enable/disable bot functions
- **Commands:** Quick action buttons (e.g., Min Fans, Max Fans)
- **Settings:** Sleep time, studio stop count, debug mode
- **Start/Stop:** Toggle bot execution
- **Screenshot:** Capture device screen
- **Show Full Log:** Launch LogViewer for debug sessions

### Control Key Override

Hold **Ctrl** during bot execution to temporarily skip functions without stopping the bot.

---

## Creating Your Own Bot

The framework is designed for easy bot creation. Follow these steps:

### Step 1: Copy the Template

```bash
# Copy the game template folder
xcopy /E /I games\template games\my_game
```

### Step 2: Define Your Functions

Edit `games/my_game/functions.py`:

```python
"""My Game Functions"""
import time
from core.utils import log

def do_recover(bot, device):
    """Fix/recover function - runs between loop iterations"""
    log("Fix/Recover: Checking game state...")
    # Add your recovery logic here
    time.sleep(0.5)

def do_collect_reward(bot, device):
    """Collect daily reward"""
    log("Collecting reward...")

    if bot.find_and_click('reward_button', accuracy=0.95):
        log("Clicked reward button!")
        time.sleep(2)
        bot.find_and_click('close_button')
    else:
        log("Reward button not found")

def do_auto_battle(bot, device):
    """Start an auto battle"""
    log("Starting battle...")

    if bot.find_and_click('battle_button'):
        time.sleep(2)
        bot.find_and_click('auto_button')

        # Wait for battle to complete
        counter = 0
        while not bot.find_and_click('victory', tap=False):
            time.sleep(1)
            counter += 1
            if counter > 60:
                break

        bot.tap(270, 800)  # Collect rewards
        time.sleep(1)
```

### Step 3: Add Command Handlers (Optional)

Edit `games/my_game/commands.py`:

```python
"""My Game Command Handlers"""
import time
from core.utils import log

def handle_quick_collect(bot, gui):
    """Quick collect command - triggered by button press"""
    log("Quick collect triggered!")
    bot.find_and_click('collect_all_button')
    time.sleep(0.5)
```

### Step 4: Configure Functions in Game Config

Create `my_game.conf` in the project root:

```json
{
  "app_name": "My Game Bot",
  "app_package": "com.example.mygame",
  "function_layout": [
    ["doCollectReward", "doAutoBattle"]
  ],
  "cooldowns": {
    "doCollectReward": 86400
  },
  "auto_uncheck": ["doCollectReward"]
}
```

### Step 5: Create Needle Images

1. Run `python tools/getScreenShot.py Device1 -p`
2. Crop UI elements in MS Paint
3. Save to your game's `findimg/` folder (e.g., `games/my_game/findimg/reward_button.png`)

### Key Bot Methods

```python
# Find and click image
bot.find_and_click('button_name', accuracy=0.95)

# Check without clicking
if bot.find_and_click('image', tap=False):
    log("Found it!")

# Tap coordinates
bot.tap(270, 480)

# Swipe gesture
bot.swipe(100, 400, 400, 400, duration=300)

# Get screenshot
screenshot = bot.screenshot()

# Crop region [y1:y2, x1:x2]
crop = screenshot[50:100, 200:300]
```

For the complete bot creation guide, see [docs/NEWBOT.md](docs/NEWBOT.md).

---

## Web Interface & Remote Monitoring

The framework includes a Flask-based web interface for remote monitoring and control.

### Quick Start

```bash
# Install dependencies
pip install flask flask-cors flask-socketio

# Start the server
python web/server.py

# Open browser
# Local: http://localhost:5000
# Network: http://YOUR_IP:5000
```

### Features

- Real-time bot status monitoring
- Remote control (toggle checkboxes, adjust settings)
- Live screenshot viewing
- Send tap/swipe commands via screenshot
- Multi-device dashboard
- Mobile-friendly design

See [web/README.md](web/README.md) for full documentation.

---

## Utility Scripts

All utility scripts are in the `tools/` directory:

### LogViewer.py
Debug log viewer with three-column interface for browsing bot execution history.

```bash
python tools/LogViewer.py
```

### ArrangeWindows.py
Arrange multiple LDPlayer windows side-by-side.

```bash
python tools/ArrangeWindows.py
```

### getScreenShot.py
Capture screenshots for creating needle images.

```bash
python tools/getScreenShot.py Device1 -p  # Open in MS Paint
python tools/getScreenShot.py Device1 -o output.png
```

---

## Troubleshooting

### ADB Issues

```bash
# Check devices
adb devices

# Restart ADB
adb kill-server
adb start-server
```

### Image Matching Issues

- Lower accuracy: `accuracy=0.85`
- Re-crop needle with less background
- Use `tap=False` to test detection

### Connection Issues

- Use cloned LDPlayer instances (not original)
- Verify hardware serial in master.conf
- Check ADB debugging is enabled

### Performance Issues

- Reduce screenshot frequency
- Increase sleep time
- Close unused emulator instances

---

## Version Tracking

This project uses Semantic Versioning (MAJOR.MINOR.BUILD).

```bash
# View current version
python tools/version_manager.py show

# Add a change
python tools/version_manager.py add "Description of change"

# Bump versions
python tools/version_manager.py minor
python tools/version_manager.py major
```

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for version history.

---

## Contributing

1. Follow existing code structure
2. Add docstrings for new functions
3. Track changes: `python tools/version_manager.py add "Your change"`
4. Test with multiple devices
5. Update documentation

---

## License

Part of the Apex-Girl project.

---

**Happy Botting!**
