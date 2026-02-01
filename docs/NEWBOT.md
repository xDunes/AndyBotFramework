# Creating Your First Bot - Complete Guide

Welcome! This guide walks you through creating a game automation bot using the Andy Bot Framework's modular architecture.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Understanding the Framework](#understanding-the-framework)
3. [Quick Start - Creating a New Bot](#quick-start---creating-a-new-bot)
4. [Step-by-Step Bot Creation](#step-by-step-bot-creation)
5. [Working with Screenshots and Needles](#working-with-screenshots-and-needles)
6. [Bot Function Patterns](#bot-function-patterns)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### What You Need:
1. **Python 3.8+** installed
2. **ADB (Android Debug Bridge)** running
3. **An Android device or emulator** connected via ADB
4. **MS Paint** (for creating needle images)

### Verify Your Setup:
```bash
# Check Python
python --version

# Check ADB
adb devices
# Should show your device listed
```

---

## Understanding the Framework

### Project Structure

```
Apex-Girl/
├── start_bot.py            # Unified bot launcher for all games
├── master.conf             # Global device settings
├── apex_girl.conf          # Game-specific config (example)
├── my_game.conf            # Your game config
│
├── core/                   # Framework (don't modify)
│   ├── android.py          # ADB device communication
│   ├── bot.py              # BOT class - image recognition
│   ├── bot_loop.py         # Main execution loop
│   └── ...                 # Other framework modules
│
├── games/                  # Game-specific modules
│   ├── apex_girl/          # Apex Girl functions
│   │   ├── functions.py
│   │   ├── commands.py     # Command handlers
│   │   └── findimg/        # Needle images
│   └── template/           # Template for new games
│       ├── functions.py    # Copy this for your game!
│       ├── commands.py     # Command handlers template
│       └── findimg/        # Your needle images go here
│
├── gui/                    # GUI components
├── web/                    # Web interface
└── tools/                  # Utility scripts
```

### How It Works

```
┌─────────────────────────────────────────┐
│   start_bot.py -g your_game -d Device1  │  ← Unified launcher
├─────────────────────────────────────────┤
│   your_game.conf (in project root)      │  ← Your game config
│   games/your_game/functions.py          │  ← Your game functions
│   games/your_game/commands.py           │  ← Your command handlers
├─────────────────────────────────────────┤
│   core/ (Bot Framework)                 │  ← Don't modify
│   - bot.py, android.py, bot_loop.py     │
└─────────────────────────────────────────┘
```

### Key Concepts

**1. Needles and Haystacks:**
- **Haystack** = Full screenshot of your game
- **Needle** = Small image of a UI element (button, icon)
- The bot uses OpenCV to find the needle in the haystack

**2. The Bot Loop:**
```python
while bot_running:
    for each enabled_function:
        if not on_cooldown:
            run_function()
    run_fix_recover()
    sleep()
```

**3. Function Naming Convention:**
- Python uses snake_case: `do_collect_reward`
- Config files use camelCase: `doCollectReward`
- The framework converts automatically

---

## Quick Start - Creating a New Bot

### 1. Copy the Template Files

```bash
# Copy the game functions template
xcopy /E /I games\template games\my_game
```

### 2. Edit Your Functions

Open `games/my_game/functions.py` and add your bot logic:

```python
"""My Game Functions"""
import time
from core.utils import log

def do_recover(bot, device):
    """Fix/recover - runs between loop iterations"""
    # Close popups, navigate to home screen, etc.
    if bot.find_and_click('close_popup'):
        time.sleep(0.5)

def do_collect_daily(bot, device):
    """Collect daily login reward"""
    if bot.find_and_click('daily_reward_icon'):
        time.sleep(1)
        bot.find_and_click('claim_button')
        time.sleep(1)
        bot.find_and_click('close_button')
        log("Daily reward collected!")
```

### 3. Add Command Handlers (Optional)

Edit `games/my_game/commands.py` for quick action buttons:

```python
"""My Game Command Handlers"""
import time
from core.utils import log

def handle_quick_collect(bot, gui):
    """Quick collect command - triggered by button press"""
    _ = gui
    log("Quick collect triggered!")
    bot.find_and_click('collect_all_button')
    time.sleep(0.5)
```

### 4. Configure Your Bot

Create two configuration files in the **root directory**:

**master.conf** - Global device settings (create once, use for all games):
```json
{
  "LDPlayerPath": "D:\\LDPlayer\\LDPlayer9\\",
  "max_reconnect_attempts": 10,
  "devices": {
    "Device1": {
      "email": "your@email.com",
      "index": 0,
      "window": "LDPlayer",
      "serial": "00ce49b2"
    }
  },
  "adb": {
    "host": "127.0.0.1",
    "port": 5037
  }
}
```

**my_game.conf** - Game-specific settings:
```json
{
  "app_name": "My Game Bot",
  "app_title": "My Game Remote Monitor",
  "app_package": "com.example.mygame",
  "function_layout": [
    ["doCollectDaily", "doAutoBattle"]
  ],
  "commands": [
    {"id": "quick_collect", "label": "Quick Collect", "command_type": "command"}
  ],
  "bot_settings": [],
  "cooldowns": {},
  "auto_uncheck": [],
  "devices": {}
}
```

> **Note:** Device serial goes in master.conf. Game-specific device settings (like targets) go in my_game.conf under devices.

### 5. Run Your Bot

```bash
python start_bot.py -g my_game -d Device1
```

---

## Step-by-Step Bot Creation

### Step 1: Configure Your Device

#### Finding the Device Serial

The bot auto-detects the hardware serial. Run any bot and look for:
```
Detected serial: 00ce49b2
Connected to device: 00ce49b2
```

**Important:**
- Use the 8-character hardware serial: `00ce49b2`
- NOT the ADB device ID: `emulator-5554`

#### LDPlayer Users - Critical Setup

**DO NOT use the original LDPlayer instance** - its serial changes on updates!

1. Open LDPlayer Multi-Instance Manager
2. Click "Clone" to create a copy
3. Use the cloned instance - its serial persists

#### Update master.conf

Add your device to master.conf in the root directory:

```json
{
  "devices": {
    "Device1": {
      "serial": "00ce49b2",
      "window": "LDPlayer-Clone",
      "email": "your@email.com",
      "index": 0
    }
  }
}
```

### Step 2: Create Your Game Functions

Create `games/my_game/functions.py`:

```python
"""
My Game Bot Functions

Function naming:
- Python: snake_case (do_collect_reward)
- Config: camelCase (doCollectReward)
"""

import time
from core.utils import log


# ============================================================================
# FIX/RECOVER FUNCTION (Required)
# ============================================================================

def do_recover(bot, device):
    """Fix/recover function - runs between loop iterations

    Use this to:
    - Close unexpected popups
    - Navigate back to known screen state
    - Recover from errors
    """
    _ = device  # Unused

    log("Fix/Recover: Checking state...")

    # Close any popups
    if bot.find_and_click('close_button', accuracy=0.9):
        time.sleep(0.5)

    # Make sure we're on home screen
    if not bot.find_and_click('home_icon', tap=False):
        bot.tap(270, 850)  # Tap home position
        time.sleep(0.5)


# ============================================================================
# BOT FUNCTIONS
# ============================================================================

def do_collect_daily(bot, device):
    """Collect daily login reward

    Config name: doCollectDaily
    """
    _ = device
    log("=== Collecting Daily Reward ===")

    # Open daily rewards
    if not bot.find_and_click('daily_icon', accuracy=0.95):
        log("Daily icon not found - may already be claimed")
        return

    time.sleep(1.5)

    # Click claim
    if bot.find_and_click('claim_button', accuracy=0.92):
        log("Claimed daily reward!")
        time.sleep(1)
    else:
        log("No claim button found")

    # Close popup
    bot.find_and_click('close_button')


def do_auto_battle(bot, device):
    """Start and complete an auto battle

    Config name: doAutoBattle
    """
    _ = device
    log("=== Starting Battle ===")

    # Enter battle
    if not bot.find_and_click('battle_button'):
        log("Battle button not found")
        return

    time.sleep(2)

    # Click start
    if not bot.find_and_click('start_button'):
        log("Start button not found")
        bot.find_and_click('back_button')
        return

    time.sleep(3)

    # Enable auto
    bot.find_and_click('auto_button', accuracy=0.90)

    # Wait for battle completion
    log("Waiting for battle to complete...")
    counter = 0
    while not bot.find_and_click('victory', tap=False, accuracy=0.85):
        time.sleep(2)
        counter += 1
        if counter > 60:  # 2 minute timeout
            log("Battle timeout")
            break

    # Collect rewards
    time.sleep(2)
    bot.tap(270, 800)
    time.sleep(1)

    log("=== Battle Complete ===")


def do_collect_mail(bot, device):
    """Collect all mail rewards

    Config name: doCollectMail
    Returns True to trigger auto-uncheck
    """
    _ = device
    log("=== Collecting Mail ===")

    if not bot.find_and_click('mail_icon'):
        log("Mail icon not found")
        return False

    time.sleep(1)

    if bot.find_and_click('collect_all'):
        log("Collected all mail!")
        time.sleep(1)
        bot.find_and_click('close_button')
        return True  # Auto-uncheck this function
    else:
        log("No mail to collect")
        bot.find_and_click('close_button')
        return False
```

### Step 3: Add Command Handlers (Optional)

Create `games/my_game/commands.py` for quick action buttons:

```python
"""
My Game Command Handlers

Command naming convention:
- Config uses snake_case IDs: "quick_collect", "boost_all"
- Python uses handle_ prefix: "handle_quick_collect", "handle_boost_all"

All command handlers take (bot, gui) as standard parameters.
"""

import time
from core.utils import log


def handle_quick_collect(bot, gui):
    """Handle quick collect command

    Commands are triggered by buttons in the GUI, not the automatic loop.
    Use for actions that should run immediately on user request.

    Args:
        bot: BOT instance for game interactions
        gui: BotGUI instance for logging and state access
    """
    _ = gui  # Can be used for gui.log() or accessing gui state
    log("Quick collect triggered!")

    # Perform immediate action
    bot.find_and_click('collect_all_button')
    time.sleep(0.5)
```

### Step 4: Configure Your Bot

Create configuration files in the **root directory**:

**master.conf** - Global settings (one file for all your bots):
```json
{
  "LDPlayerPath": "D:\\LDPlayer\\LDPlayer9\\",
  "max_reconnect_attempts": 10,
  "devices": {
    "Device1": {
      "email": "your@email.com",
      "index": 0,
      "window": "LDPlayer",
      "serial": "00ce49b2"
    }
  },
  "adb": {"host": "127.0.0.1", "port": 5037}
}
```

**my_game.conf** - Game-specific settings:
```json
{
  "app_name": "My Game Bot",
  "app_title": "My Game Remote Monitor",
  "app_package": "com.example.mygame",
  "function_layout": [
    ["doCollectDaily", "doCollectMail"],
    ["doAutoBattle"]
  ],
  "commands": [
    {"id": "quick_collect", "label": "Quick Collect", "command_type": "command"}
  ],
  "bot_settings": [
    {"id": "sleep_time", "label": "Sleep", "type": "number", "default": 1}
  ],
  "cooldowns": {
    "doCollectDaily": 86400,
    "doCollectMail": 300
  },
  "auto_uncheck": ["doCollectMail"],
  "devices": {}
}
```

> **Note:** The game name in the .conf filename must match your game folder name (e.g., `my_game.conf` for `games/my_game/`).

### Step 5: Create Needle Images

See [Working with Screenshots and Needles](#working-with-screenshots-and-needles) section.

---

## Working with Screenshots and Needles

### What is a Needle?

A needle is a small PNG image of a UI element you want to find:
- Buttons
- Icons
- Text labels
- Game elements

### Creating Needles

#### 1. Capture a Screenshot

```bash
python tools/getScreenShot.py Device1 -p
```

This captures a screenshot and opens it in MS Paint.

#### 2. Crop the Element

In MS Paint:
1. Use the Select tool (rectangle)
2. Select ONLY the UI element
3. Copy (Ctrl+C)
4. New image (Ctrl+N)
5. Paste (Ctrl+V)
6. Save as PNG

**Good vs Bad Cropping:**

```
BAD - Too much background:
┌─────────────────────────┐
│                         │
│      ┌────────┐         │
│      │  PLAY  │         │
│      └────────┘         │
│                         │
└─────────────────────────┘

GOOD - Just the button:
┌────────┐
│  PLAY  │
└────────┘
```

#### 3. Save to Your Game's findimg/

Save with a descriptive name in your game's findimg folder:
- `games/my_game/findimg/daily_icon.png`
- `games/my_game/findimg/claim_button.png`
- `games/my_game/findimg/close_button.png`

#### 4. Use in Your Bot

```python
# Name matches filename without .png
bot.find_and_click('daily_icon')
bot.find_and_click('claim_button')
```

### Finding Coordinates

For `bot.tap(x, y)`:
1. Open screenshot in MS Paint
2. Hover over the target location
3. Read coordinates from bottom-left corner

```python
# Example: Click at coordinates
bot.tap(270, 480)  # Center of 540x960 screen
```

---

## Bot Function Patterns

### Pattern 1: Simple Click

```python
def do_claim_reward(bot, device):
    """Click a button if it exists"""
    _ = device

    if bot.find_and_click('reward_button'):
        log("Clicked reward!")
        time.sleep(1)
    else:
        log("No reward available")
```

### Pattern 2: Click Until Gone

```python
def do_collect_all(bot, device):
    """Keep clicking until button disappears"""
    _ = device

    count = 0
    while bot.find_and_click('collect_button'):
        count += 1
        log(f"Collected #{count}")
        time.sleep(0.5)

    log(f"Total collected: {count}")
```

### Pattern 3: Wait for Element

```python
def do_wait_for_ready(bot, device):
    """Wait until element appears"""
    _ = device

    counter = 0
    while not bot.find_and_click('ready_button', tap=False):
        log("Waiting for ready...")
        time.sleep(1)
        counter += 1
        if counter > 30:
            log("Timeout!")
            return

    log("Ready button found!")
    bot.find_and_click('ready_button')
```

### Pattern 4: Multi-Step Workflow

```python
def do_complete_quest(bot, device):
    """Multi-step workflow with error handling"""
    _ = device

    log("=== Starting Quest ===")

    # Step 1: Open menu
    if not bot.find_and_click('quest_menu'):
        log("Quest menu not found")
        return

    time.sleep(1)

    # Step 2: Select quest
    if not bot.find_and_click('available_quest'):
        log("No available quests")
        bot.find_and_click('close_button')
        return

    time.sleep(1)

    # Step 3: Start quest
    if bot.find_and_click('start_quest'):
        log("Quest started!")
    else:
        log("Could not start quest")

    # Step 4: Close
    bot.find_and_click('close_button')

    log("=== Quest Complete ===")
```

### Pattern 5: Return True for Auto-Uncheck

```python
def do_one_time_task(bot, device):
    """Return True to auto-uncheck after completion"""
    _ = device

    if bot.find_and_click('task_button'):
        log("Task completed!")
        return True  # This unchecks the function

    return False  # Keep checked, try again next loop
```

---

## Advanced Features

### 1. Function Cooldowns

Prevent functions from running too frequently:

```json
{
  "cooldowns": {
    "doCollectDaily": 86400,
    "doAutoBattle": 0,
    "doCollectMail": 300
  }
}
```

- `86400` = 24 hours (daily tasks)
- `300` = 5 minutes
- `0` = no cooldown

### 2. Auto-Uncheck

Automatically uncheck function after it completes:

```json
{
  "auto_uncheck": ["doCollectMail", "doOneTimeTask"]
}
```

Functions return `True` to trigger uncheck.

### 3. Debug Logging

Enable debug mode for detailed logging with screenshots:

1. Check "Debug" in GUI Settings
2. Use `log()` with screenshots:

```python
def do_debug_task(bot, device):
    sc = bot.screenshot()
    log("Starting task", screenshot=sc)

    if bot.find_and_click('button'):
        sc2 = bot.screenshot()
        log("Button clicked", screenshot=sc2)
```

3. View logs with LogViewer:

```bash
python tools/LogViewer.py
```

### 4. OCR (Text Recognition)

Read numbers from screen:

```python
import pytesseract
import re

def get_energy_count(bot):
    """Read energy from screen (e.g., "50/100")"""
    sc = bot.screenshot()

    # Crop to energy area [y1:y2, x1:x2]
    energy_area = sc[50:80, 400:480]

    # Prepare for OCR
    processed = bot.prepare_image_for_ocr(energy_area)

    # Read text
    text = pytesseract.image_to_string(
        processed,
        config='--psm 7 -c tessedit_char_whitelist=0123456789/'
    ).strip()

    # Parse "50/100"
    match = re.search(r'(\d+)/(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0
```

### 5. Web Interface

Monitor and control bots remotely:

```bash
# Start web server
python web/server.py

# Access at http://localhost:5000
```

---

## Troubleshooting

### "Bot can't find my needle"

1. **Lower accuracy:**
   ```python
   bot.find_and_click('button', accuracy=0.85)
   ```

2. **Check needle file:**
   - Must be in your game's `findimg/` folder (e.g., `games/my_game/findimg/`)
   - Must be PNG format
   - Name matches without `.png`

3. **Re-crop needle:**
   - Remove excess background
   - Keep it small and unique

4. **Test detection:**
   ```python
   if bot.find_and_click('button', tap=False):
       log("Found it!")
   else:
       log("Not found")
   ```

### "Clicking wrong location"

Use offsets:
```python
bot.find_and_click('button', offset_x=10, offset_y=5)
```

### "Device not found"

```bash
# Check ADB
adb devices

# Restart ADB
adb kill-server
adb start-server
```

### "Import errors"

Make sure you're running from the project root:
```bash
cd AndyBotFramework
python start_bot.py -g my_game -d Device1
```

---

## Quick Reference

### File Structure for New Bot

```
games/my_game/
├── __init__.py          # Package marker
├── functions.py         # Your bot functions
├── commands.py          # Your command handlers (optional)
└── findimg/             # Your needle images
    ├── button.png
    └── icon.png
```

### Required Function

```python
def do_recover(bot, device):
    """Called between loop iterations"""
    pass
```

### Core Bot Methods

```python
# Find and click image
bot.find_and_click('needle_name', accuracy=0.9)

# Check without clicking
if bot.find_and_click('needle', tap=False):
    pass

# Click coordinates
bot.tap(270, 480)

# Swipe
bot.swipe(x1, y1, x2, y2, duration=500)

# Get screenshot
sc = bot.screenshot()

# Crop [y:y, x:x]
crop = sc[50:100, 200:300]

# Log message
log("Your message")
```

### Config File Structure

**master.conf** - Global device settings:
```json
{
  "devices": {"Device1": {"serial": "00ce49b2", "window": "LDPlayer", "index": 0}}
}
```

**game.conf** - Game-specific settings:
```json
{
  "function_layout": [["doFunc1", "doFunc2"]],
  "cooldowns": {"doFunc1": 300},
  "auto_uncheck": ["doFunc2"],
  "devices": {"Device1": {"game_specific_setting": 5}}
}
```

---

**Happy Botting!**

For more details, see the main [README.md](../README.md).
