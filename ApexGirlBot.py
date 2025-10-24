"""
ApexGirl Bot - Automated game bot with GUI interface
Manages multiple Android devices and performs various in-game actions
"""

from android import Android
from bot import BOT, BotStoppedException
import time
import sys
import random
import json
import os
import tkinter as tk
from tkinter import ttk
import threading
import cv2 as cv
import pytesseract
import re
import numpy as np
from PIL import Image
from datetime import datetime

# ============================================================================
# GLOBAL STATE
# ============================================================================
andy = None
bot = None
bot_running = False
gui_root = None
gui_instance = None

# Cached configuration to avoid repeated file I/O
_cached_config = None

# Pre-compiled regex patterns for performance
RATIO_PATTERN = re.compile(r'\b(\d+)/(\d+)\b')
RATIO_PATTERN_FLEXIBLE = re.compile(r'(\d+)\s*/\s*(\d+)')
LEVEL_PATTERN = re.compile(r'(?P<level>\d+)')
NUMBER_SLASH_PATTERN = re.compile(r'(?P<used>\d+)[^\d]+(?P<of>\d+)')


# ============================================================================
# LOGGING HELPER
# ============================================================================

def log(message):
    """Log message to GUI if available, otherwise print to console

    Args:
        message: Message string to log

    Note:
        Uses global gui_instance if available, falls back to console print
    """
    global gui_instance
    if gui_instance:
        gui_instance.log(message)
    else:
        print(message)


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def load_config():
    """Load configuration from config.json (with caching)"""
    global _cached_config
    if _cached_config is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            _cached_config = json.load(f)
    return _cached_config


def get_device_config(user):
    """Get device configuration for a specific user"""
    config = load_config()
    devices = config.get('devices', {})
    if user not in devices:
        raise KeyError(f"Unknown user: {user}")
    return devices[user]


def get_serial(user):
    """Get device serial for a user"""
    return get_device_config(user)["serial"]


def get_concert_target(user):
    """Get concert target level for a user"""
    return get_device_config(user)["concerttarget"]


def get_stadium_target(user):
    """Get stadium target level for a user"""
    return get_device_config(user)["stadiumtarget"]


def format_cooldown_time(seconds):
    """Format cooldown time in condensed format

    Args:
        seconds: Remaining seconds

    Returns:
        str: Formatted time - rounded to nearest minute until < 60s (e.g., "5m", "3m", "45s")
    """
    if seconds < 60:
        # Less than 1 minute - show seconds only
        return f"{seconds}s"
    else:
        # 1 minute or more - round to nearest minute for space saving
        minutes = round(seconds / 60)
        return f"{minutes}m"


# ============================================================================
# OCR AND IMAGE PROCESSING
# ============================================================================

def extract_ratio_from_image(bot, image, fallback_used=0, fallback_of=1):
    """
    Extract 'number/number' pattern from image using OCR

    Args:
        bot: Bot instance for logging
        image: Image to process
        fallback_used: Default value for 'used' if OCR fails
        fallback_of: Default value for 'of' if OCR fails

    Returns:
        dict: {'used': int, 'of': int}
    """
    try:
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

        # Multiple preprocessing approaches
        processed_images = [
            ('Simple Threshold', cv.threshold(gray, 127, 255, cv.THRESH_BINARY)[1]),
            ('Adaptive Threshold', cv.adaptiveThreshold(gray, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 11, 2)),
            ('OTSU Threshold', cv.threshold(gray, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)[1]),
        ]

        # Add morphological processing
        kernel = np.ones((2, 2), np.uint8)
        morph = cv.morphologyEx(processed_images[2][1], cv.MORPH_CLOSE, kernel)
        processed_images.append(('Morphological', morph))

        # OCR configurations to try
        configs = [
            r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789/',
            r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789/',
            r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789/'
        ]

        # Test each processed image with each config
        for name, processed_img in processed_images:
            pil_img = Image.fromarray(processed_img)

            for config in configs:
                text = pytesseract.image_to_string(pil_img, config=config).strip()

                # Look for exact number/number pattern
                match = RATIO_PATTERN.search(text)
                if match:
                    return {
                        'used': int(match.group(1)),
                        'of': int(match.group(2))
                    }

                # Look for flexible pattern with possible spaces
                flexible_match = RATIO_PATTERN_FLEXIBLE.search(text)
                if flexible_match:
                    return {
                        'used': int(flexible_match.group(1)),
                        'of': int(flexible_match.group(2))
                    }

        return {'used': fallback_used, 'of': fallback_of}

    except Exception as e:
        bot.log(f"OCR ERROR: {e}")
        return {'used': fallback_used, 'of': fallback_of}


def get_active_cars(bot):
    """Get the count of active cars (used/total)

    Returns:
        dict: {'used': int, 'of': int} or error codes:
              - {'used': -2, 'of': 3} if no cars sent
              - {'used': 0, 'of': 2} if OCR fails (empty text)
              - {'used': 0, 'of': 1} if pattern match fails
    """
    bot.find_and_click('x')
    sc = bot.screenshot()
    crop = sc[354:371, 1:35]

    if not bot.find_and_click('nocarssent', screenshot=crop, tap=False):
        return {"used": -2, "of": 3}

    sc = bot.screenshot()
    crop = sc[354:371, 35:70]

    # Show the cropped region for debugging
    #cv.imshow("Rally OCR - Cropped Region", crop)
    #cv.waitKey(0)
    #cv.destroyAllWindows()

    # Isolate WHITE TEXT: Convert all non-white pixels to black
    # Define white threshold (adjust tolerance as needed)
    white_threshold = 200  # Pixels with values >= 200 are considered "white-ish"

    # Convert to grayscale first
    gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)

    # Create binary mask: white pixels stay white (255), everything else becomes black (0)
    _, white_mask = cv.threshold(gray, white_threshold, 255, cv.THRESH_BINARY)

    # Show the white-isolated image
    #cv.imshow("Rally OCR - White Isolated", white_mask)
    #cv.waitKey(0)
    #cv.destroyAllWindows()

    # Now prepare for OCR: resize, clean up, and invert
    # Resize for better OCR
    resized = cv.resize(white_mask, None, fx=6, fy=6, interpolation=cv.INTER_CUBIC)

    # Apply morphological operations to clean up noise
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv.morphologyEx(resized, cv.MORPH_OPEN, kernel, iterations=1)
    cleaned = cv.morphologyEx(cleaned, cv.MORPH_CLOSE, kernel, iterations=1)

    # Invert so text is BLACK on WHITE background (Tesseract preference)
    processed = cv.bitwise_not(cleaned)

    # Show the final processed image for debugging
    #cv.imshow("Rally OCR - Final Processed", processed)
    #cv.waitKey(0)
    #cv.destroyAllWindows()

    # Try OCR with PSM 7 (single line) and restricted character set
    text = pytesseract.image_to_string(
        processed,
        config='--psm 7 -c tessedit_char_whitelist=0123456789/'
    )

    # Clean up whitespace
    text = text.strip()
    #bot.log(f'Rally OCR: "{text}"')

    if text == "":
        return {"used": 0, "of": 2}

    result = NUMBER_SLASH_PATTERN.search(text)
    if not result:
        bot.log(f'Rally OCR pattern match failed for: "{text}"')
        return {"used": 0, "of": 1}

    return {
        "used": int(result.group('used')),
        "of": int(result.group('of'))
    }


def get_record_count(bot):
    """
    Get the count of records in studio (used/total)

    Returns:
        dict: {'used': int, 'of': int} or {'used': -1, 'of': 6} on error
    """
    try:
        sc = bot.screenshot()
        image = sc[775:800, 460:510]

        if bot.find_and_click("record0", accuracy=0.99, tap=False, screenshot=image):
            return {'used': 0, 'of': 6}

        return extract_ratio_from_image(bot, image, fallback_used=-1, fallback_of=6)

    except Exception as e:
        bot.log(f"ERROR: {e}")
        return {'used': -1, 'of': 6}


def adjust_level(bot, target):
    """
    Adjust the level selector to match target level

    Args:
        bot: Bot instance
        target: Target level (-1 to skip adjustment)
    """
    if target == -1:
        return

    was_level_adjusted = True
    level_adjust_count = 0

    while was_level_adjusted:
        was_level_adjusted = False

        if target != 0:
            sc = bot.screenshot()
            crop = sc[830:850, 0:540]
            white_threshold = np.array([255, 255, 255, 255])  # RGBA format
            tolerance = 40

            # Create mask for pixels close to white
            mask = np.all(crop >= white_threshold - np.array([tolerance, tolerance, tolerance, 0]), axis=-1)

            # Create processed image where non-white pixels are black
            processed_image = np.zeros_like(crop)
            processed_image[mask] = white_threshold

            text = pytesseract.image_to_string(bot.prepare_image_for_ocr(processed_image),
                                               config='--psm 7 -c tessedit_char_whitelist="Levl1234567890')
            bot.log(f'Level OCR: {text}')

            result = LEVEL_PATTERN.search(text)
            if not result:
                bot.log("Level OCR: No result")
                break

            current_level = int(result.group('level'))
            bot.log(f'Target:{target} Cur:{current_level}')

            if target < current_level:
                bot.find_and_click("search-min", tap=True, accuracy=0.95)
                was_level_adjusted = True
                level_adjust_count += 1
            elif target > current_level:
                bot.find_and_click("search-max", tap=True, accuracy=0.95)
                level_adjust_count += 1
                was_level_adjusted = True

            time.sleep(1)

            if level_adjust_count > target:
                was_level_adjusted = False


# ============================================================================
# GAME ACTION FUNCTIONS - CONCERTS & EVENTS
# ============================================================================

def do_concert(bot, user):
    """Send cars to concerts until all are sent or limit reached

    Repeatedly sends available cars to concerts by:
    1. Checking how many cars are currently active
    2. Selecting a car and choosing concert action
    3. Finding and performing at available concert venues
    4. Driving to location (with optional teleport)
    5. Waiting for all cars to return before completing

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        - Exits if out of energy
        - Maximum 9 iterations to prevent infinite loops
        - Uses random delays for human-like behavior
    """
    if not bot.find_and_click("screen-map",accuracy=0.99, tap=False) and not bot.find_and_click("screen-main", accuracy=0.99, tap=False):
        return
    
    bot.find_and_click("screen-main")
    time.sleep(1)
    
    counter = 0

    while True:
        counter += 1
        result = get_active_cars(bot)

        log(f'Cars: {result["used"]}/{result["of"]}')

        if result["used"] < result["of"]:
            # Send a car to concert
            # First check if we're out of energy - uncheck concert and return
            if bot.find_and_click('outofenergy', tap=False, accuracy=0.99):
                log("Out of energy - stopping concert runs")
                if hasattr(bot, 'gui') and bot.gui:
                    bot.gui.function_states['doConcert'].set(False)
                return

            # Check if we have cars available to send
            sc = bot.screenshot()
            crop = sc[350:370, 1:35]  # Crop to car status area

            # If no cars sent yet, need to select and send a car
            if not bot.find_and_click('nocarssent', screenshot=crop, tap=False, accuracy=0.97):
                bot.tap(115, 790)  # Select car slot
                time.sleep(0.5)
                bot.tap(115, 790)  # Confirm selection
                time.sleep(1)

                # Select concert action from menu
                bot.tap(95, 580)
                time.sleep(0.5)

                if not bot.find_and_click("search-target", tap=True, accuracy=0.92):
                    continue

                time.sleep(3)
            else:
                bot.tap(270, 460)

            # Random delays and offsets for human-like behavior
            pause = random.randint(1, 100) / 100
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)

            time.sleep(1)

            # Click "Perform" button repeatedly until it disappears
            while bot.find_and_click("perform", tap=True, accuracy=0.99, click_delay=1):
                pause = random.randint(50, 100) / 100
                time.sleep(pause)

            time.sleep(1)

            # Drive to concert location
            while bot.find_and_click("driveto", tap=True, accuracy=0.99, click_delay=1, offset_x=offset_x, offset_y=offset_y):
                time.sleep(pause)

                # Check if teleport option appears
                if bot.find_and_click("teleportx", tap=True, accuracy=0.99):
                    time.sleep(0.5)
                    bot.tap(500, 830)  # Confirm teleport
                    time.sleep(0.3)
                    bot.tap(500, 830)  # Double confirm
                    break

                pause = random.randint(1, 100) / 100
        else:
            break

        if counter > 9:
            break

    # Wait for all cars to return before finishing
    # -2 indicates all cars have returned and are ready
    while get_active_cars(bot)["used"] != -2:
        log("Waiting for cars to return...")
        time.sleep(1)


# ============================================================================
# GAME ACTION FUNCTIONS - RALLY
# ============================================================================

def do_rally(bot, user):
    """Join rally if cars are available

    Checks if cars are available and joins an active rally event:
    1. Verifies car availability
    2. Looks for available rally
    3. Attempts to join rally (with retries)
    4. Drives to rally location if successfully joined

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        - Only joins if cars are available
        - Maximum 5 retry attempts for joining
        - Uses random delays for human-like behavior
    """

    if not bot.find_and_click('rallyavailable',tap=False):
        return
    # Check car availability
    result = get_active_cars(bot)

    #while result["used"] == -1:
    #    result = get_active_cars(bot)

    log(f'Rally Cars: {result["used"]}/{result["of"]}')

    # Only proceed if cars are available
    if result["used"] >= result["of"]:
        return

    # Join rally
    if bot.find_and_click('rallyavailable'):
        counter=0
        while not bot.find_and_click('rallyjoin') and counter<=20:
            counter+=1
            time.sleep(0.5)
            if counter>20:
                bot.find_and_click('rallyback')
                return

        offset_x = random.randint(1, 30)
        offset_y = random.randint(1, 35)
        counter2=0
        while not bot.find_and_click("driveto", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            counter2+=1
            bot.find_and_click('rallyjoin')
            time.sleep(0.1)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)
            if counter2>30:
                bot.find_and_click('rallyback')
                return




def get_alert_rally_info(bot):
    """Get information about rally alerts

    Args:
        bot: BOT instance for game interactions

    Returns:
        None - Not yet implemented

    TODO:
        Implement rally alert parsing from screenshot
    """
    sc = bot.screenshot()
    # TODO: Implement rally alert parsing


# ============================================================================
# GAME ACTION FUNCTIONS - STUDIO & RECORDING
# ============================================================================

def do_studio(bot, user, stop):
    """
    Record albums in studio until reaching stop threshold

    Args:
        bot: Bot instance
        user: Username
        stop: Stop when this many records exist (user-configurable)

    Returns:
        bool: True if should uncheck (stop threshold reached), False otherwise
    """

    if not bot.find_and_click("screen-map",accuracy=0.99, tap=False) and not bot.find_and_click("screen-main", accuracy=0.99, tap=False):
        return

    bot.find_and_click("screen-map")
    time.sleep(1)

    bot.tap(485,850)
    time.sleep(1)

    log(f'Checking if record expired')
    if bot.find_and_click("records0of6", accuracy=0.75):
        time.sleep(2)
        if bot.find_and_click("recordsexpired"):
            time.sleep(2)
            bot.find_and_click("recordconfirm")
            time.sleep(2)

    result = get_record_count(bot)

    if result["used"] == -1:
        return False

    while result["used"] > 6:
        time.sleep(0.1)
        result = get_record_count(bot)

    log(f'Records: {result["used"]}/{result["of"]}')

    # Check if we've reached the stop threshold - if so, return True to uncheck
    if bot.find_and_click("record6", tap=False, accuracy=0.92) or result["used"] >= stop:
        if result["used"] >= stop:
            log(f"Studio at {result['used']}/{result['of']} (target: {stop}) - Auto-unchecking")
            return True
        return False

    # Record a new album if slots are available
    if result["used"] < result["of"]:
        while not bot.find_and_click("studio", tap=True, accuracy=0.99):
            time.sleep(0.5)
        time.sleep(1)

        bot.find_and_click("askhelp", tap=True, accuracy=0.90)
        time.sleep(1)

        while not bot.find_and_click("record", tap=True, accuracy=0.99):
            time.sleep(0.1)

        while not bot.find_and_click("select", tap=True, accuracy=0.99):
            time.sleep(0.1)

        while not bot.find_and_click("autoassign", tap=True, accuracy=0.99):
            time.sleep(0.1)
        time.sleep(1)

        while not bot.find_and_click("start", tap=True, accuracy=0.92):
            time.sleep(0.1)
        time.sleep(1)

        while not bot.find_and_click("skip", tap=True, accuracy=0.99):
            time.sleep(0.1)
        time.sleep(1)

        while not bot.find_and_click("skip", tap=True, accuracy=0.92):
            time.sleep(0.1)
        time.sleep(1)

        while not bot.find_and_click("claim", tap=True, accuracy=0.99):
            time.sleep(0.1)
        time.sleep(1)

    # Return False - continue checking, not at 6/6 yet
    return False


# ============================================================================
# GAME ACTION FUNCTIONS - GROUP ACTIVITIES
# ============================================================================

def assist_one_fan(bot):
    """Assist one group building by selecting and driving a character

    This function handles the process of:
    1. Finding the min/max slider settings
    2. Configuring character selection settings
    3. Selecting a random SSR character
    4. Driving to the building location

    Args:
        bot: BOT instance for game interactions

    Note:
        - Uses random offsets for human-like clicking
        - Maximum 10 retries for finding settings
    """
    counter = 0
    while not bot.find_and_click("min") and counter <= 5 and not bot.find_and_click("max", tap=False):
        counter += 1
        time.sleep(1)

    counter = 0
    while not bot.find_and_click("settings") and counter <= 10:
        counter += 1
        time.sleep(0.1)

    while bot.find_and_click("settings") or bot.find_and_click("brokensettings", offset_y=5):
        time.sleep(0.1)

    time.sleep(2)

    offset_x = random.randint(1, 15)
    offset_y = random.randint(1, 10)

    while bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
        time.sleep(0.1)
        offset_x = random.randint(1, 15)
        offset_y = random.randint(1, 10)
    time.sleep(1)
    bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y)
    time.sleep(1)
    bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y)

    bot.swipe(270, 630, 270, -700)

    time.sleep(3)
    bot.find_and_click("randomssr")

    time.sleep(0.5)
    counter = 0
    while not bot.find_and_click("settingsdriveto"):
        counter += 1
        if counter >= 10:
            return
        time.sleep(0.1)
    
    time.sleep(2)
    bot.find_and_click("continuemarch")


def do_group(bot, user):
    """Perform group-related activities (gifts, investments, zone)

    Comprehensive group activity automation including:
    1. Navigating to group menu
    2. Collecting and claiming gifts
    3. Making investments in group plans
    4. Participating in zone activities
    5. Assisting group buildings
    6. Selecting and driving characters to locations

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Returns:
        None - Exits early if required screens not found

    Note:
        - Starts cooldown timer only on successful completion
        - Multiple early exit points if navigation fails
        - Uses random offsets for human-like clicking
        - Maximum 10 retries for finding settings
    """
    # Verify we're on map or main screen before proceeding
    if not bot.find_and_click("screen-map",accuracy=0.99, tap=False) and not bot.find_and_click("screen-main", accuracy=0.99, tap=False):
        return

    while bot.find_and_click("group", accuracy=0.99) or bot.find_and_click("help", accuracy=0.99):
        time.sleep(0.2)

    while not bot.find_and_click("gift") and bot.find_and_click("group", accuracy=0.99):
        time.sleep(0.1)

    offset_x = random.randint(1, 5)
    offset_y = random.randint(1, 5)
    while bot.find_and_click("gift", offset_x=offset_x, offset_y=offset_y,accuracy=0.98):
        time.sleep(0.1)

    while not bot.find_and_click("giftscreen",accuracy=0.99,tap=False) and bot.find_and_click("gift"):
        time.sleep(0.1)

    # Collect gifts
    if bot.find_and_click("giftcollect"):
        time.sleep(1)
        bot.tap(250, 865)
        time.sleep(2)

    if bot.find_and_click("claimall"):
        time.sleep(0.5)
        bot.tap(250, 865)
        time.sleep(1)
        bot.tap(250, 865)
        time.sleep(2)

    bot.tap(250, 865)
    time.sleep(0.5)

    # Investments
    bot.find_and_click("plan")
    time.sleep(1)

    while bot.find_and_click("invest", accuracy=0.99):
        time.sleep(0.2)

    # Zone activities
    while not bot.find_and_click("zone"):
        time.sleep(0.1)
        bot.tap(250, 865)
        bot.find_and_click("rallyback")

    offset_x = random.randint(1, 5)
    offset_y = random.randint(1, 5)
    while bot.find_and_click("zone", offset_x=offset_x, offset_y=offset_y,accuracy=0.98):
        time.sleep(0.5)

    time.sleep(1.5)
    bot.find_and_click("groupclaim")
    time.sleep(0.3)

    counter=0
    offset_x = random.randint(1, 30)
    offset_y = random.randint(1, 35)
    buildings_found = True
    while not bot.find_and_click("assist", accuracy=0.92, offset_x=offset_x, offset_y=offset_y) and counter<=10:
        if bot.find_and_click("groupzonenormal", accuracy=0.95, tap=False):
            counter=10
            buildings_found = False
        counter+=1
        time.sleep(0.1)
        bot.swipe(270, 490, 400, 490)


    if counter<=6:
        bot.find_and_click("assist")
        time.sleep(2)
        assist_one_fan(bot)
    else:
        offset_x = random.randint(1, 30)
        offset_y = random.randint(1, 35)

        while bot.find_and_click("back", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            time.sleep(0.5)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)

    # Start cooldown timer only if no buildings were found (buildings_found is False)
    # This means we successfully assisted buildings
    if not buildings_found:
        global gui_instance
        if gui_instance:
            gui_instance.last_run_times['doGroup'] = time.time()




# ============================================================================
# GAME ACTION FUNCTIONS - SIMPLE ACTIONS
# ============================================================================

def do_street(bot, user):
    """Perform street-related activities (XP collection and demo completion)

    Navigates to the street screen and performs available actions:
    1. Claims offline income if popup appears
    2. Navigates to Tokyo 2 street location
    3. Collects street XP if ready
    4. Completes available demo tasks with assistant
    5. Returns to main screen

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups (currently unused)

    Note:
        - Auto-unchecks itself in GUI when complete
        - Exits early if street button not found
    """
    _ = user  # Unused parameter

    if not bot.find_and_click("street"):
        log("Street button not found - skipping street tasks")
        return
    time.sleep(1)

    # Wait for street screen to load (with timeout protection)
    counter = 0
    while not bot.find_and_click("streetback",tap=False) and not bot.find_and_click("offlineincomeclaim"):
        time.sleep(0.1)
        counter += 1
        if counter > 100:  # 10 second timeout
            log("Street screen load timeout - aborting")
            return

    counter = 0
    while not bot.find_and_click("streetback",tap=False):
        time.sleep(0.1)
        counter += 1
        if counter > 100:  # 10 second timeout
            log("Street back button not found - aborting")
            return

    bot.find_and_click("tokyo2street",accuracy=0.99)
    time.sleep(2)

    if bot.find_and_click("streetxpready",accuracy=0.99):
        while not bot.find_and_click("streetxpreadyselected",accuracy=0.99):
            time.sleep(0.1)
            bot.find_and_click("streetback",tap=False)

        time.sleep(1)
        bot.find_and_click("collectxp")
        time.sleep(1)
        bot.find_and_click("tokyo2street")
        time.sleep(2)

    if bot.find_and_click("demoassistant",accuracy=0.99):

        time.sleep(1)
        if bot.find_and_click("demosready",accuracy=0.99):

            time.sleep(2)
            while bot.find_and_click("democomplete"):
                time.sleep(0.2)
                while not bot.find_and_click("tapscreentocontinue"):
                    time.sleep(0.1)
                while bot.find_and_click("tapscreentocontinue"):
                    time.sleep(0.1)
                time.sleep(0.5)

            while bot.find_and_click("back"):
                time.sleep(0.1)
    
    while bot.find_and_click("streetback"):
        time.sleep(0.1)

    # Auto-uncheck Street function in GUI
    if hasattr(bot, 'gui') and bot.gui:
        bot.gui.function_states['doStreet'].set(False)


def do_artists(bot, user):
    """Perform artist-related activities - placeholder"""
    _ = bot, user  # Unused - placeholder function
    log("doArtists executed - not yet implemented")


def do_tour(bot, user):
    """Run a tour

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Simple action - finds and clicks tour button
    """
    _ = user  # Unused parameter
    bot.find_and_click("tour")
    time.sleep(0.2)


def do_help(bot, user):
    """Click help button

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Opens the help/menu interface
    """
    _ = user  # Unused parameter
    bot.find_and_click("help", accuracy=0.99)
    time.sleep(0.5)


def do_heal(bot, user):
    """Heal assist - find and click heal assist button

    Attempts to find and click the heal assist button. If not found,
    scrolls down to reveal it.

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Uses swipe to scroll if button not immediately visible
    """
    _ = user  # Unused parameter
    if not bot.find_and_click("healassist", accuracy=0.91):
        bot.log("Dragging to find heal assist")
        bot.swipe(230, 830, 230, 700)
        time.sleep(3)
    time.sleep(0.5)


def do_spam_hq(bot, user):
    """Spam click company HQ

    Repeatedly clicks the company headquarters location to
    collect resources or trigger events.

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Hard-coded coordinates (310, 745) for HQ location
    """
    _ = user  # Unused parameter
    bot.tap(310, 745)


def do_coin(bot, user):
    """Check if coin is ready and collect it

    Checks if the coin collection button is ready (visible),
    and clicks it to collect coins if available.

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        Only collects if coinReady image is detected
    """
    _ = user  # Unused parameter
    if bot.find_and_click("coinReady", tap=False, accuracy=0.99):
        bot.find_and_click("coin")


# ============================================================================
# GUI CLASS
# ============================================================================

class BotGUI:
    """Main GUI class for the bot interface"""

    def __init__(self, root, username):
        """Initialize BotGUI with window and widgets

        Args:
            root: tkinter.Tk root window
            username: Device username from config

        Note:
            Window position is calculated based on device order in config
            to arrange multiple bot windows horizontally on screen
        """
        self.root = root
        self.username = username
        self.root.title(f"ApexGirl Bot - {username}")

        # Calculate window position based on device order in config.json
        # This arranges multiple bot windows horizontally across the screen
        config = load_config()
        device_list = list(config.get('devices', {}).keys())
        try:
            position = device_list.index(username) + 1
        except ValueError:
            position = 1

        # Position windows side-by-side: 573px wide each, at y=1030
        x_pos = (position - 1) * 573
        y_pos = 1030

        self.root.geometry(f"573x330+{x_pos}+{y_pos}")
        self.root.resizable(False, False)

        # Function enable/disable states - all start unchecked
        # Order: Row 1: Street, Artists, Studio, Tour, Group
        #        Row 2: Concert, Help, Coin, Heal, spamHQ
        #        Row 3: Rally
        self.function_states = {
            'doStreet': tk.BooleanVar(value=False),
            'doArtists': tk.BooleanVar(value=False),
            'doStudio': tk.BooleanVar(value=False),
            'doTour': tk.BooleanVar(value=False),
            'doGroup': tk.BooleanVar(value=False),
            'doConcert': tk.BooleanVar(value=False),
            'doHelp': tk.BooleanVar(value=False),
            'doCoin': tk.BooleanVar(value=False),
            'doHeal': tk.BooleanVar(value=False),
            'spamHQ': tk.BooleanVar(value=False),
            'doRally': tk.BooleanVar(value=False)
        }

        # Settings
        self.sleep_time = tk.StringVar(value="1")
        self.studio_stop = tk.StringVar(value="6")
        self.screenshot_interval = tk.StringVar(value="0")
        self.show_no_click = tk.BooleanVar(value=False)

        # Bot state
        self.is_running = False
        self.bot_thread = None

        # Screenshot state
        self.screenshot_running = False
        self.screenshot_thread = None

        # Log buffer
        self.log_buffer = []

        # Cooldown display labels (for functions with cooldowns)
        self.cooldown_labels = {}
        self.max_log_lines = 300
        self.user_scrolling = False

        # Track last run times for cooldown system
        self.last_run_times = {}

        # Shortcut triggers (for immediate execution on next bot loop)
        self.shortcut_triggers = {
            'assist_one_fan': False
        }

        self.create_widgets()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Top bar with username and status
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=3, pady=1)

        ttk.Label(top_frame, text=f"User: {self.username}",
                 font=("Arial", 9, "bold")).pack(side="left")

        self.status_label = ttk.Label(top_frame, text="Stopped",
                                       foreground="red", font=("Arial", 8))
        self.status_label.pack(side="right")

        # Current action label
        self.current_action_label = ttk.Label(self.root, text="", font=("Arial", 7))
        self.current_action_label.pack(pady=0)

        # Top content frame - Functions and Settings side by side
        top_content_frame = ttk.Frame(self.root)
        top_content_frame.pack(fill="x", padx=3, pady=1)

        # Left side - Functions
        left_column = ttk.Frame(top_content_frame)
        left_column.pack(side="left", fill="both", expand=True)

        self._create_functions_section(left_column)
        self._create_shortcuts_section(left_column)

        # Right side - Settings and controls
        self._create_controls_section(top_content_frame)

        # Bottom - Log window
        self._create_log_section()

    def _create_functions_section(self, parent):
        """Create the functions checkboxes section"""
        functions_frame = ttk.LabelFrame(parent, text="Functions", padding=1)
        functions_frame.pack(fill="x", padx=1)

        # Define custom row layout
        # Row 1: Street, Artists, Studio, Tour, Group
        # Row 2: Help, Coin, Heal, spamHQ
        # Row 3: Rally, Concert
        row_layout = [
            ['doStreet', 'doArtists', 'doStudio', 'doTour', 'doGroup'],
            ['doHelp', 'doCoin', 'doHeal', 'spamHQ'],
            ['doRally', 'doConcert']
        ]

        # Create rows
        for row_items in row_layout:
            row_frame = ttk.Frame(functions_frame)
            row_frame.pack(fill="x", padx=1, pady=1)

            for func_name in row_items:
                if func_name in self.function_states:
                    var = self.function_states[func_name]

                    # Create display label by removing "do" prefix
                    if func_name.startswith('do'):
                        display_name = func_name[2:]  # Remove "do" prefix
                    else:
                        display_name = func_name  # Keep as is for non-"do" prefixed names

                    # Create frame to hold checkbox and cooldown label together
                    item_frame = ttk.Frame(row_frame)
                    item_frame.pack(side="left", padx=2, pady=0)

                    cb = ttk.Checkbutton(item_frame, text=display_name, variable=var)
                    cb.pack(side="left")

                    # Add cooldown label for functions that have cooldowns
                    # (will be populated/updated by bot loop)
                    cooldown_label = ttk.Label(item_frame, text="", foreground="gray")
                    cooldown_label.pack(side="left", padx=(2, 0))
                    self.cooldown_labels[func_name] = cooldown_label

    def _create_controls_section(self, parent):
        """Create the settings and control buttons section"""
        right_frame = ttk.Frame(parent)
        right_frame.pack(side="right", fill="y", padx=1)

        # Settings
        settings_frame = ttk.LabelFrame(right_frame, text="Settings", padding=2)
        settings_frame.pack(fill="x", pady=1)

        # Sleep time
        sleep_frame = ttk.Frame(settings_frame)
        sleep_frame.pack(fill="x", pady=1)
        ttk.Label(sleep_frame, text="Sleep:", font=("Arial", 7)).pack(anchor="w")
        ttk.Entry(sleep_frame, textvariable=self.sleep_time, width=8).pack(fill="x")

        # Screenshot interval
        screenshot_frame = ttk.Frame(settings_frame)
        screenshot_frame.pack(fill="x", pady=1)
        ttk.Label(screenshot_frame, text="Seconds:", font=("Arial", 7)).pack(anchor="w")
        ttk.Entry(screenshot_frame, textvariable=self.screenshot_interval, width=8).pack(fill="x")

        # Show NO CLICK logs checkbox
        no_click_frame = ttk.Frame(settings_frame)
        no_click_frame.pack(fill="x", pady=1)
        ttk.Checkbutton(no_click_frame, text="Show NO CLICK",
                       variable=self.show_no_click).pack(anchor="w")

        # Control buttons
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill="x", pady=3)

        self.toggle_button = ttk.Button(button_frame, text="Start", command=self.toggle_bot)
        self.toggle_button.pack(fill="x", pady=1)

        # Screenshot button
        self.screenshot_button = ttk.Button(button_frame, text="Screenshot",
                                            command=self.toggle_screenshot)
        self.screenshot_button.pack(fill="x", pady=1)

    def _create_shortcuts_section(self, parent):
        """Create the shortcuts section under Functions"""
        shortcuts_frame = ttk.LabelFrame(parent, text="Shortcuts", padding=2)
        shortcuts_frame.pack(fill="x", padx=1, pady=(2, 0))

        # Create a row of shortcut buttons
        button_row = ttk.Frame(shortcuts_frame)
        button_row.pack(fill="x")

        # 1 fan button
        fan_button = ttk.Button(button_row, text="1 fan", command=self.trigger_assist_one_fan)
        fan_button.pack(side="left", padx=2, pady=1)

    def trigger_assist_one_fan(self):
        """Trigger assist_one_fan to run on next bot loop cycle"""
        self.shortcut_triggers['assist_one_fan'] = True
        self.log("1 fan shortcut triggered - will execute on next bot loop")

    def _create_log_section(self):
        """Create the log window section"""
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=1)
        log_frame.pack(fill="both", expand=True, padx=3, pady=1)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_container, height=1, width=1, wrap=tk.WORD,
                                font=("Courier", 8), state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_container, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Track user scrolling
        self.log_text.bind("<MouseWheel>", self.on_user_scroll)
        self.log_text.bind("<Button-4>", self.on_user_scroll)
        self.log_text.bind("<Button-5>", self.on_user_scroll)

    def on_user_scroll(self, _event):
        """Track when user manually scrolls"""
        self.root.after(100, self.check_scroll_position)
        return

    def check_scroll_position(self):
        """Check if log is scrolled to bottom"""
        try:
            pos = self.log_text.yview()
            # If at bottom (within small threshold), enable auto-scroll
            self.user_scrolling = pos[1] < 0.99
        except:
            pass

    def log(self, message):
        """Add message to log window with 300 line buffer

        Args:
            message: Message string to log

        Note:
            - Adds timestamp to each message
            - Maintains 300 line buffer (FIFO)
            - Auto-scrolls only if user hasn't manually scrolled up
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"

        self.log_buffer.append(log_msg)

        # Keep only last 300 lines (FIFO buffer)
        if len(self.log_buffer) > self.max_log_lines:
            self.log_buffer = self.log_buffer[-self.max_log_lines:]

        # Update text widget
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "\n".join(self.log_buffer))

        # Auto-scroll only if user is at bottom (not manually scrolled up)
        if not self.user_scrolling:
            self.log_text.see(tk.END)

        self.log_text.config(state=tk.DISABLED)

    def update_status(self, status_text, action_text=""):
        """Update status and action labels

        Args:
            status_text: Status text to display (e.g., "Running", "Stopped")
            action_text: Current action description (optional)
        """
        self.status_label.config(text=f"{status_text}")
        if action_text:
            self.current_action_label.config(text=f"Action: {action_text}")

    def toggle_bot(self):
        """Toggle bot on/off

        Starts or stops the bot execution thread. When stopping,
        immediately signals the bot instance to halt execution.

        Note:
            - Sets bot.should_stop flag for immediate stopping
            - Runs bot in daemon thread
            - Updates GUI status indicators
        """
        if self.is_running:
            # Stop the bot immediately
            global bot_running, bot
            self.is_running = False
            bot_running = False

            # Signal the bot instance to stop immediately
            if 'bot' in globals() and bot is not None:
                bot.should_stop = True

            self.toggle_button.config(text="Start")
            self.status_label.config(text="Stopped", foreground="red")
            self.current_action_label.config(text="Action: None")
            self.log("Stop button pressed - halting execution")
        else:
            # Start the bot
            self.is_running = True
            self.toggle_button.config(text="Stop")
            self.status_label.config(text="Running", foreground="green")
            self.bot_thread = threading.Thread(target=run_bot_loop, args=(self,), daemon=True)
            self.bot_thread.start()

    def toggle_screenshot(self):
        """Toggle screenshot capture on/off"""
        if self.screenshot_running:
            # Stop screenshot capture
            self.screenshot_running = False
            self.screenshot_button.config(text="Screenshot")
            self.log("Screenshot capture stopped")
        else:
            # Start screenshot capture
            self.screenshot_running = True
            self.screenshot_button.config(text="Stop Screenshot")
            self.screenshot_thread = threading.Thread(target=self.capture_screenshots, daemon=True)
            self.screenshot_thread.start()
            self.log("Screenshot capture started")

    def capture_screenshots(self):
        """Capture screenshots in a separate thread

        Two modes:
        1. Single capture (interval=0): Takes one screenshot and opens in MS Paint
        2. Continuous capture (interval>0): Takes screenshots at specified interval

        Note:
            - Runs in daemon thread
            - Creates screenshots/ directory automatically
            - Filenames include username and timestamp
        """
        try:
            # Get interval
            try:
                interval = float(self.screenshot_interval.get())
            except ValueError:
                interval = 0

            # Create screenshots directory
            screenshot_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)

            # Get device serial
            user = sys.argv[1] if len(sys.argv) > 1 else "unknown"
            serial = get_serial(user) if len(sys.argv) > 1 else None

            if not serial:
                self.log("ERROR: Cannot get device serial for screenshots")
                self.screenshot_running = False
                self.screenshot_button.config(text="Screenshot")
                return

            # Connect to device
            screenshot_andy = Android(serial)

            # Single or continuous capture
            if interval == 0:
                # Single capture - save and open in mspaint
                filepath = self._save_screenshot(screenshot_andy, user, screenshot_dir)
                if filepath:
                    # Open the screenshot in MS Paint
                    import subprocess
                    subprocess.Popen(['mspaint', filepath])
                    self.log(f"Opened in MS Paint: {os.path.basename(filepath)}")
                self.screenshot_running = False
                self.screenshot_button.config(text="Screenshot")
            else:
                # Continuous capture
                while self.screenshot_running:
                    self._save_screenshot(screenshot_andy, user, screenshot_dir)
                    if self.screenshot_running:  # Check again before sleeping
                        time.sleep(interval)

        except Exception as e:
            self.log(f"Screenshot ERROR: {e}")
            self.screenshot_running = False
            self.screenshot_button.config(text="Screenshot")

    def _save_screenshot(self, andy, user, screenshot_dir):
        """Save a single screenshot with timestamp

        Returns:
            str: Filepath of saved screenshot, or None if error occurred
        """
        try:
            # Capture screenshot
            screenshot = andy.capture_screen()

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{user}_{timestamp}.png"
            filepath = os.path.join(screenshot_dir, filename)

            # Save screenshot
            import cv2 as cv
            cv.imwrite(filepath, screenshot)

            self.log(f"Screenshot saved: {filename}")
            return filepath
        except Exception as e:
            self.log(f"Error saving screenshot: {e}")
            return None


# ============================================================================
# BOT EXECUTION LOOP
# ============================================================================

def run_bot_loop(gui):
    """
    Main bot execution loop with GUI integration

    Args:
        gui: BotGUI instance
    """
    global andy, bot, bot_running, gui_instance

    gui_instance = gui

    try:
        user = sys.argv[1]
        andy = Android(get_serial(user))
        andy.set_gui(gui)  # Set GUI for Android logging
        gui.log(f"Connected to device: {user}")
    except Exception as error:
        gui.update_status("Error", f"Error: {error}")
        gui.log(f"ERROR: {error}")
        return

    bot = BOT(andy)
    bot.set_gui(gui)
    bot.should_stop = False  # Reset stop flag when starting
    bot_running = True

    # Function mapping
    function_map = {
        'doStreet': do_street,
        'doArtists': do_artists,
        'doStudio': do_studio,
        'doTour': do_tour,
        'doGroup': do_group,
        'doConcert': do_concert,
        'doHeal': do_heal,
        'doCoin': do_coin,
        'doHelp': do_help,
        'spamHQ': do_spam_hq,
        'doRally': do_rally
    }

    # Functions that should be unchecked after completion
    auto_uncheck = {'doStudio'}

    # Cooldown system - configure cooldowns for functions (in seconds)
    # Set to 0 or omit to disable cooldown for a function
    function_cooldowns = {
        'doGroup': 300,      # 5 minutes
        'doStreet': 0,       # No cooldown (disabled)
        'doArtists': 0,      # No cooldown (disabled)
        'doStudio': 0,       # No cooldown (disabled)
        'doTour': 0,         # No cooldown (disabled)
        'doConcert': 0,      # No cooldown (disabled)
        'doHeal': 0,         # No cooldown (disabled)
        'doCoin': 0,         # No cooldown (disabled)
        'doHelp': 0,         # No cooldown (disabled)
        'spamHQ': 0,         # No cooldown (disabled)
        'doRally': 0,        # No cooldown (disabled)
    }

    # Track last run time for each function (store in GUI instance)
    gui.last_run_times = {func_name: 0 for func_name in function_map.keys()}

    while gui.is_running and bot_running:
        try:
            # Check for shortcut triggers (run immediately, highest priority)
            if gui.shortcut_triggers['assist_one_fan']:
                gui.shortcut_triggers['assist_one_fan'] = False
                gui.update_status("Running", "assist_one_fan (shortcut)")
                try:
                    assist_one_fan(bot)
                    time.sleep(2)
                    bot.find_and_click("continuemarch")
                except BotStoppedException:
                    gui.log("Stopped during assist_one_fan shortcut")
                    raise
                except Exception as e:
                    gui.log(f"ERROR in assist_one_fan shortcut: {e}")

            # Get settings
            try:
                sleep_time = float(gui.sleep_time.get())
            except ValueError:
                sleep_time = 0

            try:
                studio_stop_val = int(gui.studio_stop.get())
            except ValueError:
                studio_stop_val = 6

            # Execute enabled functions
            for func_name, func in function_map.items():
                # Update cooldown display for this function (if it has a cooldown)
                cooldown = function_cooldowns.get(func_name, 0)
                if cooldown > 0 and func_name in gui.cooldown_labels:
                    current_time = time.time()
                    time_since_last_run = current_time - gui.last_run_times[func_name]
                    remaining = int(cooldown - time_since_last_run)

                    if remaining > 0:
                        # Show cooldown time
                        gui.cooldown_labels[func_name].config(text=f"({format_cooldown_time(remaining)})")
                    else:
                        # Cooldown expired - clear the label
                        gui.cooldown_labels[func_name].config(text="")

                if gui.function_states[func_name].get():
                    # Check cooldown for this function
                    if cooldown > 0:
                        # Cooldown is enabled for this function
                        current_time = time.time()
                        time_since_last_run = current_time - gui.last_run_times[func_name]

                        if time_since_last_run < cooldown:
                            # Still on cooldown - skip this run
                            continue

                    gui.update_status("Running", func_name)

                    try:
                        # Call function with appropriate parameters
                        should_uncheck = False
                        if func_name == 'doStudio':
                            should_uncheck = func(bot, user, studio_stop_val)
                        else:
                            func(bot, user)
                            # Auto-uncheck non-studio functions in the list
                            if func_name in auto_uncheck:
                                should_uncheck = True

                        # Uncheck if function returned True or is in auto_uncheck list
                        if should_uncheck:
                            gui.function_states[func_name].set(False)
                            log(f"{func_name} completed - unchecked")
                    except BotStoppedException:
                        # Bot was stopped by user - exit immediately
                        gui.log(f"Stopped during {func_name}")
                        raise

            # Sleep if configured
            if sleep_time > 0:
                gui.update_status("Running", f"Sleeping {sleep_time}s")
                time.sleep(sleep_time)

            # Note: Keyboard shortcuts disabled when GUI is present
            # Use the Stop button to stop the bot instead

        except BotStoppedException:
            # User clicked stop button - exit gracefully
            gui.log("Bot stopped by user")
            break
        except Exception as e:
            gui.update_status("Error", str(e))
            gui.log(f"ERROR: {e}")
            time.sleep(1)

    gui.update_status("Stopped", "")
    gui.is_running = False
    gui.toggle_button.config(text="Start")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main function - launches the GUI"""
    global gui_root, gui_instance

    # Check for user argument
    if len(sys.argv) < 2:
        print("ERROR: Please provide a user argument")
        print("Usage: python ApexGirlBot.py <username>")
        sys.exit(1)

    username = sys.argv[1]

    # Create and run GUI
    gui_root = tk.Tk()
    gui = BotGUI(gui_root, username)
    gui_instance = gui

    gui.log(f"ApexGirl Bot started for user: {username}")
    gui.log("Use checkboxes to enable functions, then click Start Bot")

    gui_root.mainloop()


if __name__ == "__main__":
    main()
