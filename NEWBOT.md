# Creating Your First Bot - Complete Guide

Welcome! This guide will walk you through creating your first game automation bot from scratch, even if you've never done this before.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Understanding the Framework](#understanding-the-framework)
3. [Setting Up Your First Bot](#setting-up-your-first-bot)
4. [Creating Your First Function](#creating-your-first-function)
5. [Working with Screenshots and Needles](#working-with-screenshots-and-needles)
6. [Using Bot Functions](#using-bot-functions)
7. [Advanced Features](#advanced-features)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### What You Need:
1. **Python** installed (3.8 or higher)
2. **ADB (Android Debug Bridge)** installed and running
3. **An Android device or emulator** connected via ADB
4. **MS Paint** (for creating needle images)
5. **Basic Python knowledge** (variables, functions, loops)

### Check Your Setup:
```bash
# 1. Check Python is installed
python --version

# 2. Check ADB is running
adb devices

# You should see your device listed
# Example output:
# List of devices attached
# emulator-5554   device
```

---

## Understanding the Framework

### The Big Picture
The bot framework has three main layers:

```
┌─────────────────────────────────────┐
│   Your Bot Script (e.g., MyBot.py) │  ← This is what you'll create
├─────────────────────────────────────┤
│   bot.py (BOT class)                │  ← High-level automation
├─────────────────────────────────────┤
│   android.py (Android class)        │  ← Low-level device control
└─────────────────────────────────────┘
```

### Key Concepts:

**1. Needles and Haystacks:**
- **Haystack** = Full screenshot of your game
- **Needle** = Small image you're searching for (button, icon, etc.)
- The bot uses OpenCV to find the needle in the haystack

**2. The GUI:**
- Checkboxes enable/disable functions
- Start/Stop button controls the bot
- Log window shows what's happening
- Screenshot button helps you capture images

**3. The Bot Loop:**
```python
while bot_running:
    for each enabled function:
        if not on cooldown:
            run the function
    sleep (if configured)
```

---

## Setting Up Your First Bot

### Step 1: Copy the Template

1. Make a copy of `botTemplate.py`
2. Rename it to your game name (e.g., `MyGameBot.py`)

```bash
copy botTemplate.py MyGameBot.py
```

### Step 2: Configure Your Device(s)

This is the most important step! You need to properly configure your devices in `config.json` so the bot knows which Android device/emulator to connect to.

#### 🚨 IMPORTANT: One Device at a Time!

When setting up multiple devices, **launch only ONE emulator/device at a time** to avoid confusion!

#### Finding Your Device Serial Number

The bot uses a **unique hardware serial** that persists across emulator updates. This is NOT the ADB device ID you see in `adb devices`!

**The ONLY Way to Find the Correct Serial:**

**Use the Bot Script to Detect Serial**

The bot automatically detects and logs the hardware serial number!

1. Launch **ONE** emulator/device
2. Run your bot script:
```bash
python MyGameBot.py Device1
```

3. Look at the log window - you'll see:
```
Detected serial: 00ce49b2
Connected to device: 00ce49b2
```

4. **Copy that serial number!** (e.g., `00ce49b2`)

**⚠️ IMPORTANT: Serial Format**

The serial will look like:
- ✅ `00ce49b2` (8 hex characters)
- ✅ `1a2b3c4d` (8 hex characters)
- ✅ `abcd1234` (8 hex characters)

NOT:
- ❌ `emulator-5554` (this is ADB device ID, not hardware serial!)
- ❌ `127.0.0.1:5555` (this is network address)

**Why Not Use `adb devices`?**

The command `adb devices` shows ADB device IDs (like `emulator-5554`), but the bot uses a special command to get the hardware serial:
```bash
adb shell getprop ro.boot.serialno
```

**Visual Comparison:**

```
❌ ADB Device ID (from 'adb devices'):
   emulator-5554  ← Changes between sessions
   emulator-5556
   127.0.0.1:5555

✅ Hardware Serial (from bot script):
   00ce49b2  ← Persistent, unique, use THIS!
   1a2b3c4d
   abcd1234
```

The **hardware serial** is unique and persistent - it won't change even after:
- ✅ Restarting the emulator
- ✅ Restarting your computer
- ✅ Updating LDPlayer (if using cloned instance)
- ✅ Changing ADB port

Always use the bot script to find this serial!

#### 🚨 LDPlayer Users: CRITICAL Setup Instructions!

If you're using **LDPlayer** emulator:

**❌ DO NOT USE the first/original LDPlayer instance!**

The first LDPlayer instance changes its serial number during updates, which will break your bot configuration!

**✅ How to Set Up LDPlayer Correctly:**

1. **Create a New Emulator Instance:**
   - Open LDPlayer Multi-Instance Manager
   - Click "Clone" or "New" to create a copy
   - Name it something like "Bot1"

2. **Use the Cloned Instance:**
   - Launch your cloned instance (not the original!)
   - Run the bot script to get its serial
   - The serial on cloned instances **persists through updates**

3. **For Multiple Bots:**
   - Create multiple cloned instances: "Bot1", "Bot2", "Bot3"
   - Launch **one at a time** to get each serial
   - Each clone keeps its serial permanently

**Example Setup:**
```
LDPlayer Instances:
❌ LDPlayer (original) - DO NOT USE - serial changes on update
✅ Bot1 (clone) - Serial: 00ce49b2 - Use this!
✅ Bot2 (clone) - Serial: 1a2b3c4d - Use this!
✅ Bot3 (clone) - Serial: abcd1234 - Use this!
```

**Why does this happen?**
- Original instance: Serial resets during LDPlayer updates
- Cloned instances: Serial is locked and persists
- This is an LDPlayer-specific behavior

#### Editing config.json

Open `config.json` in a text editor and configure your device(s):

**Single Device Setup:**

```json
{
  "default_device": "Device1",
  "devices": {
    "Device1": {
      "email": "user1@example.com",
      "window": "Device1",
      "serial": "00ce49b2",
      "concerttarget": -1,
      "stadiumtarget": 2
    }
  }
}
```

**Multiple Devices Setup (Advanced):**

If you want to run multiple bots on multiple emulators:

1. **Launch ONLY the first emulator (use cloned instance!)**
2. Run the bot script to detect serial (e.g., `00ce49b2`)
3. Copy serial from log: `"Detected serial: 00ce49b2"`
4. Add to config.json as Device1
5. **Close first emulator**
6. **Launch ONLY the second emulator**
7. Run bot script to get its serial (e.g., `1a2b3c4d`)
8. Add to config.json as Device2
9. Repeat for more devices

```json
{
  "default_device": "Device1",
  "devices": {
    "Device1": {
      "email": "user1@example.com",
      "window": "Bot1",
      "serial": "00ce49b2",
      "concerttarget": -1,
      "stadiumtarget": 2
    },
    "Device2": {
      "email": "user2@example.com",
      "window": "Bot2",
      "serial": "1a2b3c4d",
      "concerttarget": -1,
      "stadiumtarget": 2
    },
    "Device3": {
      "email": "user3@example.com",
      "window": "Bot3",
      "serial": "abcd1234",
      "concerttarget": -1,
      "stadiumtarget": 2
    }
  }
}
```

**config.json Field Explanations:**

| Field | Description | Required? |
|-------|-------------|-----------|
| `email` | User email (for reference only) | Optional |
| `window` | Window name (for reference) | Optional |
| `serial` | Device serial from ADB | **REQUIRED** |
| `concerttarget` | Game-specific setting | Optional |
| `stadiumtarget` | Game-specific setting | Optional |

**⚠️ Common Mistakes:**

❌ **DON'T** use the same serial for multiple devices
❌ **DON'T** have multiple emulators running when finding serials
❌ **DON'T** forget to update the serial after changing emulators

✅ **DO** launch one emulator at a time when configuring
✅ **DO** verify serial with `adb devices`
✅ **DO** test each device configuration separately

### Step 3: Launch Your Bot

Now that your device is configured, launch the bot!

**Command Format:**
```bash
python <BotScript.py> <DeviceName>
```

**Examples:**

```bash
# Single device
python MyGameBot.py Device1

# Multiple devices (in separate terminals)
# Terminal 1:
python MyGameBot.py Device1

# Terminal 2:
python MyGameBot.py Device2

# Terminal 3:
python MyGameBot.py Device3
```

**What the DeviceName argument does:**
- Tells the bot which device config to use from `config.json`
- Bot looks up the serial number for that device
- Connects to the correct emulator/device
- Positions the GUI window based on device order

**Example:**
```bash
python MyGameBot.py Device1
```
This will:
1. Look for `"Device1"` in config.json
2. Find `"serial": "00ce49b2"`
3. Connect to device with hardware serial `00ce49b2`
4. Position GUI at x=0 (first window)

```bash
python MyGameBot.py Device2
```
This will:
1. Look for `"Device2"` in config.json
2. Find `"serial": "1a2b3c4d"`
3. Connect to device with hardware serial `1a2b3c4d`
4. Position GUI at x=573 (second window, next to first)

### Step 4: Verify Connection

You should see:
- ✅ A GUI window appear
- ✅ Log message: `"Detected serial: 00ce49b2"` (your actual serial)
- ✅ Log message: `"Connected to device: 00ce49b2"` (your actual serial)
- ✅ Log message: `"Bot Template started for user: Device1"`
- ✅ A "HelloWorld" checkbox

**If you see errors:**

❌ `"Unknown user: Device1"` = Device name not in config.json
❌ `"ADB ERROR: No devices attached"` = No emulator/device running
❌ `"Connection failed, retrying..."` = Wrong serial or device not ready

**Troubleshooting Connection Issues:**

1. **Check ADB:**
```bash
adb devices
# Should show your device
```

2. **Restart ADB if needed:**
```bash
adb kill-server
adb start-server
adb devices
```

3. **Verify config.json serial matches ADB:**
```bash
adb devices
# Compare output to your config.json serial field
```

4. **Make sure emulator is fully booted:**
   - Wait for home screen to appear
   - Device should show "device" not "offline" in `adb devices`

### Step 5: Customize the Window Title (Optional)

In your bot file, find this line:
```python
self.root.title(f"Bot Template - {username}")
```

Change it to:
```python
self.root.title(f"My Game Bot - {username}")
```

---

### Quick Setup Checklist ✅

Before proceeding, make sure you've completed:

- [ ] Installed Python, ADB, and prerequisites
- [ ] Copied `botTemplate.py` to your bot file (e.g., `MyGameBot.py`)
- [ ] **(LDPlayer users)** Created cloned emulator instance (not using original!)
- [ ] Launched **ONE** emulator/device
- [ ] Ran bot script to detect hardware serial (8 hex characters like `00ce49b2`)
- [ ] Updated `config.json` with correct hardware serial number
- [ ] Tested bot launch: `python MyGameBot.py Device1`
- [ ] Verified "Detected serial: 00ce49b2" and "Connected to device" messages in log
- [ ] Customized window title (optional)

If all checkboxes are checked, you're ready to start creating functions! 🎉

---

## Creating Your First Function

Let's create a function that clicks a "Play" button in your game.

### Step 1: Define the Function

Add this function to the **BOT FUNCTIONS** section:

```python
def do_click_play(bot, user):
    """Click the Play button to start a game

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Looks for the 'play_button' needle image
    """
    _ = user  # Unused in this example

    # Try to find and click the play button
    if bot.find_and_click('play_button', accuracy=0.95):
        log("Clicked Play button!")
        time.sleep(2)  # Wait for game to load
    else:
        log("Play button not found")
```

### Step 2: Register the Function

Find the `function_map` dictionary in `run_bot_loop()` and add your function:

```python
# Function mapping - add your functions here
function_map = {
    'doHelloWorld': do_helloworld,
    'doClickPlay': do_click_play,  # ← Add this line
}
```

### Step 3: Add GUI Checkbox

**A. Add to function_states:**
```python
# Function enable/disable states - all start unchecked
self.function_states = {
    'doHelloWorld': tk.BooleanVar(value=False),
    'doClickPlay': tk.BooleanVar(value=False),  # ← Add this
}
```

**B. Add to row_layout:**
```python
# Define custom row layout
row_layout = [
    ['doHelloWorld', 'doClickPlay'],  # ← Add to layout
]
```

### Step 4: Test Your Function

1. Run your bot: `python MyGameBot.py Device1`
2. Check the "ClickPlay" checkbox
3. Click "Start"
4. You should see "Play button not found" (we haven't created the needle yet!)

---

## Working with Screenshots and Needles

### What is a Needle?

A needle is a small PNG image of the UI element you want to find. For example:
- A "Play" button
- A "Collect" icon
- A specific menu item
- A character's face

### Step 1: Capture a Screenshot

**Method 1: Using the Bot (Recommended)**

1. Start your game on the device/emulator
2. Run your bot: `python MyGameBot.py Device1`
3. Click the "Screenshot" button
4. MS Paint will open with your screenshot
5. Save it somewhere temporarily (e.g., `temp_screenshot.png`)

**Method 2: Using ADB Command**

```bash
adb -s emulator-5554 exec-out screencap -p > screenshot.png
```

### Step 2: Crop the Needle

1. Open the screenshot in MS Paint (or any image editor)
2. Use the **Select** tool (rectangle selection)
3. Carefully select ONLY the UI element you want to find
   - **Keep it small** - only the essential part
   - **Include unique parts** - avoid generic backgrounds
   - **Don't include too much** - smaller is better

**Example - Good vs Bad Cropping:**

```
❌ BAD - Too much background:
┌─────────────────────────┐
│                         │
│      ┌────────┐         │
│      │  PLAY  │         │
│      └────────┘         │
│                         │
└─────────────────────────┘

✅ GOOD - Just the button:
┌────────┐
│  PLAY  │
└────────┘
```

4. Copy the selection (Ctrl+C)
5. Create a new image (Ctrl+N)
6. Paste (Ctrl+V)
7. Save as PNG

### Step 3: Name and Save the Needle

**Naming Convention:**
- Use descriptive, lowercase names
- Use underscores, not spaces
- Use `.png` extension

**Good names:**
- `play_button.png`
- `collect_reward.png`
- `close_popup.png`
- `start_battle.png`

**Bad names:**
- `button1.png` (not descriptive)
- `Play Button.png` (has spaces)
- `PLAY.jpg` (not PNG, uppercase)

**Where to Save:**

Save your needle in the `findimg/` folder:

```
Apex-Girl/
├── findimg/              ← Save needles here!
│   ├── play_button.png
│   ├── collect_reward.png
│   └── close_popup.png
├── MyGameBot.py
├── bot.py
└── android.py
```

### Step 4: Test Your Needle

Update your function to use the needle:

```python
def do_click_play(bot, user):
    """Click the Play button to start a game"""
    _ = user

    # The needle name should match the filename without .png
    if bot.find_and_click('play_button', accuracy=0.95):
        log("✓ Clicked Play button!")
        time.sleep(2)
    else:
        log("✗ Play button not found - check needle accuracy")
```

Run your bot and test!

---

## Using Bot Functions

### Core Functions You'll Use

#### 1. find_and_click() - Find and Click Images

```python
# Basic usage - find and click
bot.find_and_click('button_name')

# Advanced options:
bot.find_and_click(
    needle_name='play_button',      # Name of PNG in findimg/
    offset_x=0,                      # Click X pixels right of found location
    offset_y=0,                      # Click Y pixels down from found location
    accuracy=0.9,                    # Match accuracy (0.0-1.0, higher = stricter)
    tap=True,                        # Set False to just check without clicking
    click_delay=10                   # Touch delay in milliseconds
)

# Check if something exists without clicking:
if bot.find_and_click('error_popup', tap=False):
    log("Error popup detected!")
    bot.find_and_click('close_button')
```

**Accuracy Tips:**
- Start with `0.9` (90% match)
- If not finding: **lower** accuracy (0.85, 0.8)
- If finding wrong things: **raise** accuracy (0.95, 0.99)

#### 2. tap() - Click at Coordinates

```python
# Click at specific X, Y coordinates
bot.tap(270, 480)

# Example: Click center of 540x960 screen
bot.tap(270, 480)
```

**How to Find Coordinates:**
1. Take a screenshot
2. Open in Paint
3. Hover mouse over the point you want
4. Look at bottom-left corner for coordinates

#### 3. swipe() - Swipe/Drag Gestures

```python
# Swipe from (x1, y1) to (x2, y2)
bot.swipe(x1=270, y1=800, x2=270, y2=200, duration=500)

# Example: Swipe up (scroll down)
bot.swipe(270, 800, 270, 200, duration=300)

# Example: Swipe right
bot.swipe(100, 400, 400, 400, duration=500)
```

#### 4. screenshot() - Capture Screen

```python
# Capture the current screen
sc = bot.screenshot()

# Crop a region [y1:y2, x1:x2]
crop = sc[100:200, 50:150]

# Use cropped image for searching
if bot.find_and_click('icon', screenshot=crop):
    log("Found icon in cropped area!")
```

### Common Patterns

#### Pattern 1: Click Until Gone

```python
# Keep clicking until button disappears
while bot.find_and_click('collect_button'):
    log("Collected reward!")
    time.sleep(0.5)
```

#### Pattern 2: Wait for Element

```python
# Wait until element appears
counter = 0
while not bot.find_and_click('ready_button', tap=False):
    log("Waiting for ready button...")
    time.sleep(1)
    counter += 1
    if counter > 30:  # Timeout after 30 seconds
        log("Timeout - ready button never appeared")
        return
```

#### Pattern 3: Handle Popups

```python
# Check for and close any popups
if bot.find_and_click('popup_close', tap=False, accuracy=0.95):
    log("Popup detected, closing...")
    bot.find_and_click('popup_close')
    time.sleep(1)
```

#### Pattern 4: Multiple Options

```python
# Try multiple buttons in order
if bot.find_and_click('option_a'):
    log("Selected Option A")
elif bot.find_and_click('option_b'):
    log("Selected Option B")
elif bot.find_and_click('option_c'):
    log("Selected Option C")
else:
    log("No options available")
```

---

## Advanced Features

### 1. Function Cooldowns

Prevent a function from running too frequently:

```python
function_cooldowns = {
    'doHelloWorld': 0,          # No cooldown
    'doClickPlay': 60,          # 1 minute cooldown
    'doDailyReward': 86400,     # 24 hour cooldown (in seconds)
}
```

**How it works:**
- After running, the function won't run again for the cooldown period
- A countdown timer appears next to the checkbox
- Useful for daily tasks, energy-based actions, etc.

### 2. Auto-Uncheck

Automatically uncheck a function after it completes:

```python
# Functions that should be unchecked after completion
auto_uncheck = {'doClickPlay', 'doClaimReward'}
```

**When to use:**
- One-time actions (claim daily reward)
- Tasks that complete (finish tutorial)
- Functions that should only run once

### 3. Random Delays (Human-like Behavior)

Make your bot less detectable:

```python
def do_play_game(bot, user):
    """Play a game with random human-like delays"""
    _ = user

    # Random delay between clicks
    pause = random.randint(50, 150) / 100  # 0.5 to 1.5 seconds

    bot.find_and_click('play_button')
    time.sleep(pause)

    # Random click offset
    offset_x = random.randint(-5, 5)
    offset_y = random.randint(-5, 5)

    bot.find_and_click('start_button', offset_x=offset_x, offset_y=offset_y)
```

### 4. Logging Effectively

Good logging helps you debug:

```python
def do_battle(bot, user):
    """Start and complete a battle"""
    _ = user

    log("=== Starting Battle ===")

    if not bot.find_and_click('battle_button'):
        log("ERROR: Battle button not found!")
        return

    log("Clicked battle button, waiting for loading...")
    time.sleep(3)

    if bot.find_and_click('auto_battle'):
        log("✓ Auto-battle enabled")
    else:
        log("⚠ Auto-battle not available, playing manually")

    log("=== Battle Complete ===")
```

**Tips:**
- Use prefixes: `✓` for success, `✗` for failure, `⚠` for warnings
- Log important state changes
- Log when waiting for long operations
- Use `===` to separate major sections

### 5. Using OCR (Text Recognition)

OCR (Optical Character Recognition) lets you read text from the screen, like reading energy counts, currency amounts, player levels, or any on-screen numbers/text.

#### Understanding OCR Basics

**When to use OCR:**
- ✅ Reading resource counts (gold, energy, gems)
- ✅ Checking player stats (level, HP, damage)
- ✅ Reading quest requirements ("Defeat 5 enemies")
- ✅ Verifying ratios ("3/10 complete")

**When NOT to use OCR:**
- ❌ Finding buttons (use needles instead - much faster and reliable)
- ❌ Detecting images (use find_and_click)
- ❌ Complex text with fancy fonts (very unreliable)

#### Step-by-Step: Reading Energy Count

Let's read an energy counter that shows "50/100" on screen.

**Step 1: Find the Text Location**

1. Take a screenshot
2. Open in Paint
3. Note the coordinates of the text area

```
Example: Energy is at coordinates
Top-left: (400, 50)
Bottom-right: (480, 80)
```

**Step 2: Crop the Screenshot**

Screenshot coordinates are `[y1:y2, x1:x2]` (notice Y comes first!)

```python
def get_energy_count(bot):
    """Read energy count from screen using OCR"""
    sc = bot.screenshot()

    # Crop to energy display area
    # Format: [y_start:y_end, x_start:x_end]
    energy_area = sc[50:80, 400:480]

    # Save cropped area to debug (optional but helpful!)
    cv.imwrite('debug_energy_crop.png', energy_area)
    log("Saved crop for debugging")
```

**Visual Example of Cropping:**

```
Full Screen (540x960):
┌────────────────────────┐
│  🎮 Game Title         │
│                        │
│  Energy: 50/100  ← Target this!
│  [y=50 to y=80]       │
│  [x=400 to x=480]     │
│                        │
│  [Play Button]         │
│                        │
│                        │
└────────────────────────┘

Cropped Result:
┌──────────┐
│ 50/100   │  ← Just this part
└──────────┘
```

**Step 3: Prepare Image for OCR**

The `prepare_image_for_ocr()` function optimizes the image:

```python
def get_energy_count(bot):
    """Read energy count from screen"""
    sc = bot.screenshot()

    # Crop to energy area
    energy_area = sc[50:80, 400:480]

    # Prepare image for OCR - this makes text clearer
    # It resizes, converts to black & white, and inverts
    processed = bot.prepare_image_for_ocr(energy_area)

    # Optional: Save to see what OCR sees
    cv.imwrite('debug_energy_processed.png', processed)
```

**What prepare_image_for_ocr does:**
- ✅ Resizes 5x larger (better accuracy)
- ✅ Converts to grayscale
- ✅ Applies threshold (black & white only)
- ✅ Inverts colors (black text on white background)

**Step 4: Configure OCR Settings**

Tesseract has many configuration options:

```python
import pytesseract

def get_energy_count(bot):
    """Read energy count from screen"""
    sc = bot.screenshot()
    energy_area = sc[50:80, 400:480]
    processed = bot.prepare_image_for_ocr(energy_area)

    # Read text with custom config
    text = pytesseract.image_to_string(
        processed,
        config='--psm 7 -c tessedit_char_whitelist=0123456789/'
    )

    log(f"Energy OCR result: '{text}'")
    return text.strip()
```

**OCR Config Options:**

```python
# For single line text (like "50/100")
config='--psm 7 -c tessedit_char_whitelist=0123456789/'

# For single word/number (like "999")
config='--psm 8 -c tessedit_char_whitelist=0123456789'

# For multiple lines
config='--psm 6'

# For numbers only (no slash)
config='--psm 8 -c tessedit_char_whitelist=0123456789'

# For letters and numbers
config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
```

**PSM Modes (Page Segmentation Mode):**
- `--psm 6` = Assume uniform block of text (default)
- `--psm 7` = Single text line (best for "50/100")
- `--psm 8` = Single word (best for "999")
- `--psm 13` = Raw line (no processing)

**Whitelist Characters:**
- Only recognize specific characters
- `tessedit_char_whitelist=0123456789/` = Only digits and slash
- Prevents misreading (like "O" as "0" or "l" as "1")

**Step 5: Parse the OCR Result**

OCR results often need cleaning:

```python
import re

def get_energy_count(bot):
    """Read and parse energy count"""
    sc = bot.screenshot()
    energy_area = sc[50:80, 400:480]
    processed = bot.prepare_image_for_ocr(energy_area)

    # Read text
    text = pytesseract.image_to_string(
        processed,
        config='--psm 7 -c tessedit_char_whitelist=0123456789/'
    ).strip()

    log(f"Raw OCR: '{text}'")

    # Parse "50/100" format
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        current = int(match.group(1))
        maximum = int(match.group(2))
        log(f"Energy: {current}/{maximum}")
        return {"current": current, "max": maximum}
    else:
        log("Failed to parse energy count")
        return {"current": 0, "max": 0}
```

#### Complete OCR Example: Check Energy Before Battle

```python
def do_battle_if_energy(bot, user):
    """Start battle only if we have enough energy"""
    _ = user

    log("=== Checking Energy ===")

    # Get current energy
    energy = get_energy_count(bot)

    if energy["current"] < 10:
        log(f"⚠ Not enough energy: {energy['current']}/10 required")
        return

    log(f"✓ Energy OK: {energy['current']}/{energy['max']}")

    # We have energy, start battle
    if bot.find_and_click('battle_button'):
        log("Starting battle...")
    else:
        log("✗ Battle button not found")


def get_energy_count(bot):
    """Read energy from screen

    Returns:
        dict: {"current": int, "max": int}
    """
    try:
        # Step 1: Capture and crop
        sc = bot.screenshot()
        energy_area = sc[50:80, 400:480]  # Adjust for your game!

        # Step 2: Prepare for OCR
        processed = bot.prepare_image_for_ocr(energy_area)

        # Step 3: Read text
        text = pytesseract.image_to_string(
            processed,
            config='--psm 7 -c tessedit_char_whitelist=0123456789/'
        ).strip()

        log(f"Energy OCR: '{text}'")

        # Step 4: Parse result
        match = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if match:
            return {
                "current": int(match.group(1)),
                "max": int(match.group(2))
            }
        else:
            log("⚠ Failed to parse energy")
            return {"current": 0, "max": 0}

    except Exception as e:
        log(f"✗ OCR Error: {e}")
        return {"current": 0, "max": 0}
```

#### Advanced OCR: Multiple Attempts

Sometimes OCR fails. Try multiple preprocessing methods:

```python
def get_gold_count_robust(bot):
    """Read gold count with multiple OCR attempts"""
    sc = bot.screenshot()
    gold_area = sc[100:130, 350:450]

    # Try different preprocessing approaches
    attempts = [
        ('Simple Threshold', cv.threshold(
            cv.cvtColor(gold_area, cv.COLOR_BGR2GRAY),
            127, 255, cv.THRESH_BINARY)[1]),

        ('Adaptive Threshold', cv.adaptiveThreshold(
            cv.cvtColor(gold_area, cv.COLOR_BGR2GRAY),
            255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv.THRESH_BINARY, 11, 2)),

        ('OTSU Threshold', cv.threshold(
            cv.cvtColor(gold_area, cv.COLOR_BGR2GRAY),
            0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)[1]),
    ]

    # Try each preprocessing method
    for method_name, processed_img in attempts:
        text = pytesseract.image_to_string(
            processed_img,
            config='--psm 8 -c tessedit_char_whitelist=0123456789'
        ).strip()

        # Check if we got a valid number
        if text.isdigit():
            log(f"✓ Gold count ({method_name}): {text}")
            return int(text)

    log("⚠ All OCR attempts failed")
    return 0
```

#### OCR Tips & Tricks

**1. Finding the Right Crop Coordinates**

Use this helper function:

```python
def find_crop_coords(bot):
    """Helper to find crop coordinates

    Steps:
    1. Run this function
    2. Open saved screenshot in Paint
    3. Hover over corners to get coordinates
    4. Update your crop [y1:y2, x1:x2]
    """
    sc = bot.screenshot()
    cv.imwrite('fullscreen_debug.png', sc)
    log("Saved fullscreen_debug.png - open in Paint to find coords")
    log("Format: crop = sc[y1:y2, x1:x2]")
    log(f"Screen size: {sc.shape[0]}x{sc.shape[1]}")
```

**2. Debugging OCR**

Save intermediate images to see what's wrong:

```python
def debug_ocr(bot):
    """Debug OCR by saving all intermediate steps"""
    sc = bot.screenshot()

    # Step 1: Save full screenshot
    cv.imwrite('1_fullscreen.png', sc)

    # Step 2: Save cropped area
    crop = sc[50:80, 400:480]
    cv.imwrite('2_cropped.png', crop)

    # Step 3: Save processed for OCR
    processed = bot.prepare_image_for_ocr(crop)
    cv.imwrite('3_processed.png', processed)

    # Step 4: Try OCR
    text = pytesseract.image_to_string(processed, config='--psm 7')
    log(f"OCR Result: '{text}'")

    log("Saved debug images: 1_fullscreen.png, 2_cropped.png, 3_processed.png")
```

**3. Common OCR Issues**

| Problem | Solution |
|---------|----------|
| "Returns empty string" | Crop too small or wrong area - check coordinates |
| "Returns gibberish" | Wrong PSM mode or preprocessing - try different configs |
| "Confuses 0 and O" | Use whitelist: `tessedit_char_whitelist=0123456789` |
| "Doesn't read slash" | Add to whitelist: `0123456789/` |
| "Wrong numbers" | Text too small - make sure crop is correct size |
| "Inconsistent results" | Text color/background varies - try multiple preprocessing |

**4. Whitelist Examples**

```python
# Numbers only
'tessedit_char_whitelist=0123456789'

# Numbers with slash (50/100)
'tessedit_char_whitelist=0123456789/'

# Numbers with comma (1,234)
'tessedit_char_whitelist=0123456789,'

# Letters and numbers
'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

# Specific characters only (Level 50)
'tessedit_char_whitelist=Level0123456789 '
```

**5. Full Working Example**

Here's a complete function that reads and acts on OCR data:

```python
def do_spend_energy(bot, user):
    """Spend energy if we have enough

    Reads energy count and does battles until energy is low
    """
    _ = user

    while True:
        # Read current energy
        energy = get_energy_robust(bot)

        if energy < 10:
            log(f"⚠ Energy too low: {energy}")
            break

        log(f"✓ Current energy: {energy}")

        # Do one battle
        if bot.find_and_click('battle_button'):
            time.sleep(2)
            bot.find_and_click('quick_battle')
            time.sleep(5)

            # Wait for battle to complete
            counter = 0
            while not bot.find_and_click('victory', tap=False):
                time.sleep(1)
                counter += 1
                if counter > 60:
                    break

            # Collect rewards
            bot.tap(270, 800)
            time.sleep(2)

            log("Battle complete, checking energy again...")
        else:
            log("✗ Battle button not found")
            break


def get_energy_robust(bot):
    """Read energy count with error handling

    Returns:
        int: Current energy count (0 if failed)
    """
    try:
        sc = bot.screenshot()
        energy_area = sc[50:80, 400:480]
        processed = bot.prepare_image_for_ocr(energy_area)

        text = pytesseract.image_to_string(
            processed,
            config='--psm 7 -c tessedit_char_whitelist=0123456789/'
        ).strip()

        # Parse "50/100" or just "50"
        numbers = re.findall(r'\d+', text)
        if numbers:
            current = int(numbers[0])
            log(f"OCR energy: {current}")
            return current
        else:
            log("⚠ No numbers found in OCR")
            return 0

    except Exception as e:
        log(f"✗ OCR error: {e}")
        return 0
```

---

## Complete Example Bot

Here's a complete example for a fictional game:

```python
# ============================================================================
# BOT FUNCTIONS
# ============================================================================

def do_claim_daily(bot, user):
    """Claim daily login reward

    Steps:
    1. Click daily reward icon
    2. Click claim button
    3. Close the popup
    """
    _ = user

    log("=== Claiming Daily Reward ===")

    # Step 1: Open daily rewards
    if not bot.find_and_click('daily_icon', accuracy=0.95):
        log("✗ Daily icon not found - may already be claimed")
        return

    time.sleep(1.5)

    # Step 2: Click claim
    if bot.find_and_click('claim_button', accuracy=0.92):
        log("✓ Claimed daily reward!")
        time.sleep(1)
    else:
        log("⚠ Claim button not found")

    # Step 3: Close popup
    bot.find_and_click('close_button')
    time.sleep(0.5)

    log("=== Daily Reward Complete ===")


def do_auto_battle(bot, user):
    """Start and complete an auto battle

    Steps:
    1. Click battle button
    2. Select first stage
    3. Click start
    4. Enable auto
    5. Wait for completion
    6. Collect rewards
    """
    _ = user

    log("=== Starting Auto Battle ===")

    # Step 1: Enter battle menu
    if not bot.find_and_click('battle_icon'):
        log("✗ Battle icon not found")
        return

    time.sleep(2)

    # Step 2: Select stage
    bot.tap(270, 400)  # Click first stage (coordinates)
    time.sleep(1)

    # Step 3: Click start
    if not bot.find_and_click('start_battle'):
        log("✗ Start button not found")
        bot.find_and_click('back_button')
        return

    time.sleep(3)

    # Step 4: Enable auto
    if bot.find_and_click('auto_button', accuracy=0.90):
        log("✓ Auto-battle enabled")

    # Step 5: Wait for battle to finish
    log("Waiting for battle to complete...")
    counter = 0
    while not bot.find_and_click('victory', tap=False, accuracy=0.85):
        time.sleep(2)
        counter += 1
        if counter > 60:  # 2 minute timeout
            log("⚠ Battle timeout - may have failed")
            break

    # Step 6: Collect rewards
    time.sleep(2)
    bot.tap(270, 800)  # Click to collect
    time.sleep(1)
    bot.tap(270, 800)  # Click again to close

    log("=== Battle Complete ===")


def do_collect_all(bot, user):
    """Collect all available rewards from mailbox"""
    _ = user

    log("=== Collecting Mailbox ===")

    # Open mailbox
    if not bot.find_and_click('mailbox_icon'):
        log("✗ Mailbox not found")
        return

    time.sleep(1)

    # Click collect all
    if bot.find_and_click('collect_all'):
        log("✓ Collected all rewards!")
        time.sleep(1)
    else:
        log("⚠ No rewards to collect")

    # Close mailbox
    bot.find_and_click('close_button')

    log("=== Mailbox Complete ===")


# ============================================================================
# CONFIGURE FUNCTIONS
# ============================================================================

# In run_bot_loop(), update these:

function_map = {
    'doClaimDaily': do_claim_daily,
    'doAutoBattle': do_auto_battle,
    'doCollectAll': do_collect_all,
}

auto_uncheck = {'doClaimDaily', 'doCollectAll'}

function_cooldowns = {
    'doClaimDaily': 86400,      # Once per day (24 hours)
    'doAutoBattle': 0,          # No cooldown - can spam
    'doCollectAll': 300,        # Every 5 minutes
}

# In __init__, update function_states:
self.function_states = {
    'doClaimDaily': tk.BooleanVar(value=False),
    'doAutoBattle': tk.BooleanVar(value=False),
    'doCollectAll': tk.BooleanVar(value=False),
}

# In _create_functions_section, update row_layout:
row_layout = [
    ['doClaimDaily', 'doCollectAll'],
    ['doAutoBattle'],
]
```

---

### 6. Debug Logging with Database

The bot template now includes advanced debug logging that saves all actions and screenshots to a SQLite database for later review.

#### Enabling Debug Mode

1. **Check the "Debug" checkbox** in the GUI Settings panel
2. Bot will start logging to `logs/<username>.db`
3. All log entries will include millisecond timestamps
4. Screenshots are automatically saved with each action

#### Using Debug Mode

```python
def do_collect_rewards(bot, user):
    """Collect rewards with debug logging"""
    _ = user

    log("Starting reward collection")

    # Take a screenshot and log it
    sc = bot.screenshot()
    log("Looking for reward button", screenshot=sc)

    if bot.find_and_click('reward_button'):
        sc2 = bot.screenshot()
        log("Clicked reward button", screenshot=sc2)
    else:
        log("Reward button not found")
```

**What gets logged:**
- ✅ All log messages with millisecond timestamps
- ✅ Optional screenshots (pass `screenshot=` parameter)
- ✅ Session start/end times
- ✅ Database stored in `logs/<device_name>.db`

#### Viewing Debug Logs

**Method 1: Show Full Log button**
1. Enable Debug mode
2. Run your bot
3. Click **"Show Full Log"** button
4. LogViewer.py launches automatically

**Method 2: Standalone LogViewer**
```bash
python LogViewer.py
```

**LogViewer Features:**
- 📁 **Device List** (left panel) - Browse all logged devices
- 📅 **Session List** (middle panel) - View all bot sessions by date/time
- 📝 **Log Content** (right panel) - See logs with inline screenshots
- 🖼️ **Lazy Loading** - Only loads images when visible (fast!)
- 🔍 **Session Browsing** - Review past bot runs

#### Debug Mode Best Practices

**When to use Debug mode:**
- ✅ Developing new functions
- ✅ Troubleshooting failures
- ✅ Verifying bot behavior
- ✅ Creating documentation

**When to disable Debug mode:**
- ❌ Long production runs (uses disk space)
- ❌ When not actively debugging
- ❌ Multiple bots running (can slow down)

**Managing Log Files:**
```bash
# View log database size
ls -lh logs/

# Delete old logs
rm logs/Device1.db

# Logs are organized per device:
logs/
  ├── Device1.db
  ├── Device2.db
  └── Device3.db
```

#### Example: Debug a Failing Function

```python
def do_claim_gift(bot, user):
    """Claim gift with debug logging"""
    _ = user

    log("=== Starting Gift Claim ===")

    # Capture initial state
    sc = bot.screenshot()
    log("Initial screen", screenshot=sc)

    # Try to find gift icon
    if not bot.find_and_click('gift_icon', tap=False):
        sc_fail = bot.screenshot()
        log("ERROR: Gift icon not found!", screenshot=sc_fail)
        return

    log("Found gift icon, clicking...")
    bot.find_and_click('gift_icon')
    time.sleep(2)

    # Verify gift menu opened
    sc_menu = bot.screenshot()
    log("After click - checking menu", screenshot=sc_menu)

    if bot.find_and_click('claim_button'):
        sc_success = bot.screenshot()
        log("✓ Gift claimed successfully", screenshot=sc_success)
    else:
        sc_error = bot.screenshot()
        log("✗ Claim button not found", screenshot=sc_error)

    log("=== Gift Claim Complete ===")
```

**Review in LogViewer:**
1. Open LogViewer.py
2. Select your device
3. Select the session (by timestamp)
4. Scroll through logs to see:
   - Initial screen state
   - Where the gift icon was (or wasn't) found
   - What happened after each click
   - Visual confirmation of success/failure

This makes debugging 10x easier than guessing from text logs alone!

---

## Troubleshooting

### Problem: "Bot can't find my needle"

**Solutions:**
1. **Check accuracy** - Lower it: `accuracy=0.85` or `0.80`
2. **Re-crop needle** - Make sure it's clean, no extra background
3. **Check needle location** - Must be in `findimg/` folder
4. **Check needle name** - Use exact name without `.png`: `'button_name'` not `'button_name.png'`
5. **Test with tap=False** - See if it's finding it at all:
   ```python
   if bot.find_and_click('my_needle', tap=False):
       log("Found it!")
   else:
       log("Not found - try different accuracy")
   ```

### Problem: "Clicking in wrong place"

**Solutions:**
1. **Use offsets** - Adjust click position:
   ```python
   bot.find_and_click('button', offset_x=10, offset_y=5)
   ```
2. **Re-crop needle** - Make needle more centered on the clickable area

### Problem: "Bot is too slow"

**Solutions:**
1. **Reduce sleep times** - Lower delays between actions
2. **Remove unnecessary waits** - Only wait when needed
3. **Use smaller needle images** - Faster to process
4. **Use cropped screenshots** - Search in smaller areas

### Problem: "Bot clicks too fast / gets detected"

**Solutions:**
1. **Add random delays:**
   ```python
   pause = random.randint(100, 300) / 100
   time.sleep(pause)
   ```
2. **Add random offsets:**
   ```python
   offset_x = random.randint(-3, 3)
   offset_y = random.randint(-3, 3)
   bot.find_and_click('button', offset_x=offset_x, offset_y=offset_y)
   ```
3. **Increase sleep time** - Use the GUI Sleep setting

### Problem: "Function runs but nothing happens"

**Solutions:**
1. **Check logs** - Look for error messages
2. **Add more logging** - Log each step:
   ```python
   log("Step 1: Opening menu")
   bot.find_and_click('menu')
   log("Step 2: Clicking option")
   bot.find_and_click('option')
   ```
3. **Take screenshots** - See what the bot sees:
   ```python
   sc = bot.screenshot()
   cv.imwrite('debug.png', sc)
   log("Saved debug screenshot")
   ```

### Problem: "Device not found / ADB connection error"

**Solutions:**
1. **Check ADB:** `adb devices`
2. **Restart ADB:**
   ```bash
   adb kill-server
   adb start-server
   ```
3. **Check config.json** - Make sure serial matches
4. **Check USB debugging** - Must be enabled on device

---

## Best Practices

### DO:
✅ Start simple - One function at a time
✅ Test frequently - Run after each change
✅ Use descriptive names - `do_claim_reward` not `do_thing`
✅ Add logging - Know what your bot is doing
✅ Use try-except for errors - Handle failures gracefully
✅ Comment your code - Explain complex logic
✅ Take breaks - Don't run 24/7, you'll get banned

### DON'T:
❌ Run on live accounts initially - Test on throwaway accounts
❌ Make pixel-perfect needles - Include some tolerance
❌ Hardcode everything - Use config.json for settings
❌ Ignore errors - Check logs, fix issues
❌ Run without monitoring - Watch it occasionally
❌ Share your bot publicly - Keep it private

---

## Next Steps

Congratulations! You now know how to:
- ✅ Set up a bot from the template
- ✅ Create functions
- ✅ Work with screenshots and needles
- ✅ Use find_and_click, tap, and swipe
- ✅ Configure cooldowns and auto-uncheck
- ✅ Debug and troubleshoot

### To Learn More:

1. **Study ApexGirlBot.py** - See real-world examples
2. **Experiment** - Try different functions in your game
3. **Read the code** - bot.py and android.py have more features
4. **Join communities** - Learn from other bot developers (carefully!)

### Your First Project:

Start with something simple:
1. **Auto-collect daily reward**
2. **Auto-battle one stage**
3. **Claim mailbox rewards**

Then expand from there!

---

## Quick Reference

### File Structure
```
YourBot/
├── findimg/              ← Save needles here
├── screenshots/          ← Auto-created for screenshots
├── config.json          ← Device configuration
├── MyGameBot.py         ← Your bot script
├── bot.py               ← BOT class (don't edit)
├── android.py           ← Android class (don't edit)
└── NEWBOT.md            ← This guide!
```

### Core Functions Cheat Sheet
```python
# Find and click
bot.find_and_click('needle_name', accuracy=0.9)

# Check without clicking
if bot.find_and_click('needle', tap=False):

# Click coordinates
bot.tap(x, y)

# Swipe
bot.swipe(x1, y1, x2, y2, duration=500)

# Screenshot
sc = bot.screenshot()

# Crop
crop = sc[y1:y2, x1:x2]

# Log
log("Your message")

# Wait
time.sleep(seconds)
```

### Essential Edits for New Bot
1. **Function definition** - Add `def do_yourfunction(bot, user):`
2. **function_map** - Add to dictionary
3. **function_states** - Add checkbox variable
4. **row_layout** - Add to GUI layout
5. **function_cooldowns** - Optional: add cooldown
6. **auto_uncheck** - Optional: auto-uncheck after completion

---

**Happy Botting! 🤖**

Remember: Use responsibly, respect game ToS, and don't ruin the game for others!
