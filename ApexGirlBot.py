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
from log_database import LogDatabase
from state_manager import StateManager

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

def log(message, screenshot=None):
    """Log message to GUI if available, otherwise print to console

    Args:
        message: Message string to log
        screenshot: Optional screenshot image to associate with log entry

    Note:
        Uses global gui_instance if available, falls back to console print
        If Debug mode is on and screenshot provided, saves to disk
    """
    global gui_instance
    if gui_instance:
        gui_instance.log(message, screenshot=screenshot)
    else:
        print(message)


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def load_config():
    """Load configuration from config.json with caching mechanism

    Args:
        None

    Returns:
        dict: Configuration dictionary containing device settings and layouts

    Note:
        Uses global cache to avoid repeated file I/O operations.
        Cache persists for the lifetime of the process.
    """
    global _cached_config
    if _cached_config is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            _cached_config = json.load(f)
    return _cached_config


def get_device_config(user):
    """Get device configuration for a specific user

    Args:
        user (str): Username identifier from config.json

    Returns:
        dict: Device configuration containing serial, targets, etc.

    Raises:
        KeyError: If user is not found in config
    """
    config = load_config()
    devices = config.get('devices', {})
    if user not in devices:
        raise KeyError(f"Unknown user: {user}")
    return devices[user]


def get_serial(user):
    """Get Android device serial number for a user

    Args:
        user (str): Username identifier from config.json

    Returns:
        str: ADB device serial number
    """
    return get_device_config(user)["serial"]


def get_concert_target(user):
    """Get target concert level for a user

    Args:
        user (str): Username identifier from config.json

    Returns:
        int: Target concert level to search for
    """
    return get_device_config(user)["concerttarget"]


def get_stadium_target(user):
    """Get target stadium level for a user

    Args:
        user (str): Username identifier from config.json

    Returns:
        int: Target stadium level to search for
    """
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
    """Extract 'number/number' ratio pattern from image using multi-strategy OCR

    This function uses multiple image preprocessing techniques and OCR configurations
    to maximize accuracy when reading ratio patterns (e.g., "3/6", "0/4") from
    game UI screenshots.

    Args:
        bot: Bot instance for logging errors
        image: OpenCV image (BGR numpy array) to process
        fallback_used: Default value for 'used' if all OCR attempts fail (default: 0)
        fallback_of: Default value for 'of' if all OCR attempts fail (default: 1)

    Returns:
        dict: {'used': int, 'of': int}
              - 'used': First number in ratio (numerator)
              - 'of': Second number in ratio (denominator)
              - Returns fallback values if OCR fails

    Note:
        Uses 4 preprocessing methods x 3 OCR configs = 12 total attempts
        to find the ratio pattern, prioritizing exact matches over flexible ones.
    """
    try:
        # Convert to grayscale for preprocessing
        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)

        # Try multiple preprocessing approaches to handle different text styles/backgrounds
        processed_images = [
            # Simple binary threshold at midpoint (127) - works for high contrast text
            ('Simple Threshold', cv.threshold(gray, 127, 255, cv.THRESH_BINARY)[1]),

            # Adaptive threshold - adjusts to local brightness variations
            ('Adaptive Threshold', cv.adaptiveThreshold(gray, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY, 11, 2)),

            # Otsu's method - automatically determines optimal threshold value
            ('OTSU Threshold', cv.threshold(gray, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)[1]),
        ]

        # Add morphological closing to remove small noise and connect broken characters
        kernel = np.ones((2, 2), np.uint8)
        morph = cv.morphologyEx(processed_images[2][1], cv.MORPH_CLOSE, kernel)
        processed_images.append(('Morphological', morph))

        # OCR configurations to try (different Page Segmentation Modes)
        configs = [
            r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789/',   # PSM 8: Single word
            r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789/',   # PSM 7: Single line
            r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789/'   # PSM 13: Raw line
        ]

        # Test each preprocessed image with each OCR config (12 combinations total)
        for name, processed_img in processed_images:
            pil_img = Image.fromarray(processed_img)

            for config in configs:
                text = pytesseract.image_to_string(pil_img, config=config).strip()

                # Look for exact number/number pattern (e.g., "3/6")
                match = RATIO_PATTERN.search(text)
                if match:
                    return {
                        'used': int(match.group(1)),
                        'of': int(match.group(2))
                    }

                # Look for flexible pattern with possible spaces (e.g., "3 / 6")
                flexible_match = RATIO_PATTERN_FLEXIBLE.search(text)
                if flexible_match:
                    return {
                        'used': int(flexible_match.group(1)),
                        'of': int(flexible_match.group(2))
                    }

        # All OCR attempts failed - return fallback values
        return {'used': fallback_used, 'of': fallback_of}

    except Exception as e:
        bot.log(f"OCR ERROR: {e}")
        return {'used': fallback_used, 'of': fallback_of}


def get_active_cars(bot):
    """Get the count of active rally cars using OCR on car status area

    Reads the car counter display (e.g., "2/3") from the game UI to determine
    how many cars are currently active in rallies vs total available.

    Returns:
        dict: {'used': int, 'of': int} representing active/total cars
              Special return codes:
              - {'used': -2, 'of': 3} if no cars have been sent yet
              - {'used': 0, 'of': 2} if OCR returns empty text
              - {'used': 0, 'of': 1} if pattern match fails

    Note:
        This function performs sophisticated OCR preprocessing to read white text
        on potentially complex backgrounds. The preprocessing pipeline:
        1. Isolates white pixels (threshold >= 200)
        2. Upscales 6x for better OCR accuracy
        3. Applies morphological operations to clean noise
        4. Inverts to black text on white background (Tesseract preference)
    """
    # Close any open dialogs first
    bot.find_and_click('x')
    sc = bot.screenshot()

    # Crop to status indicator area (left side of car counter)
    # Coordinates: rows 354-371, cols 1-35 (status icon area)
    crop = sc[354:371, 1:35]

    # Check if "no cars sent" indicator is present
    if not bot.find_and_click('nocarssent', screenshot=crop, tap=False):
        # No cars sent indicator found - return special code
        return {"used": -2, "of": 3}

    # Take fresh screenshot and crop to car counter text area
    sc = bot.screenshot()
    # Coordinates: rows 354-371, cols 35-70 (car counter text "X/Y")
    crop = sc[354:371, 35:70]

    # === WHITE TEXT ISOLATION PREPROCESSING ===
    # Game UI has white text that may be on varying backgrounds
    # Goal: Convert all non-white pixels to black, keeping only white text

    white_threshold = 200  # Pixels >= 200 brightness considered "white-ish"

    # Convert to grayscale for thresholding
    gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)

    # Binary threshold: white pixels (>= 200) become 255, rest become 0
    _, white_mask = cv.threshold(gray, white_threshold, 255, cv.THRESH_BINARY)

    # === OCR PREPARATION PIPELINE ===

    # 1. Upscale 6x using cubic interpolation for better OCR accuracy
    #    Small text becomes more recognizable when larger
    resized = cv.resize(white_mask, None, fx=6, fy=6, interpolation=cv.INTER_CUBIC)

    # 2. Apply morphological operations to clean up noise and connect broken characters
    kernel = np.ones((2, 2), np.uint8)
    # MORPH_OPEN: Removes small white noise (erosion then dilation)
    cleaned = cv.morphologyEx(resized, cv.MORPH_OPEN, kernel, iterations=1)
    # MORPH_CLOSE: Fills small black holes (dilation then erosion)
    cleaned = cv.morphologyEx(cleaned, cv.MORPH_CLOSE, kernel, iterations=1)

    # 3. Invert image so text is BLACK on WHITE (Tesseract works better this way)
    processed = cv.bitwise_not(cleaned)

    # === OCR EXECUTION ===
    # PSM 7: Treat image as single text line
    # Whitelist: Only recognize digits 0-9 and forward slash
    text = pytesseract.image_to_string(
        processed,
        config='--psm 7 -c tessedit_char_whitelist=0123456789/'
    )

    text = text.strip()

    # Handle empty OCR result
    if text == "":
        return {"used": 0, "of": 2}

    # Parse the "X/Y" pattern
    result = NUMBER_SLASH_PATTERN.search(text)
    if not result:
        bot.log(f'Rally OCR pattern match failed for: "{text}"')
        return {"used": 0, "of": 1}

    return {
        "used": int(result.group('used')),
        "of": int(result.group('of'))
    }


def get_record_count(bot):
    """Get the count of studio records using OCR

    Reads the record counter from the studio UI to determine how many
    albums are currently being recorded vs the maximum of 6.

    Returns:
        dict: {'used': int, 'of': 6} representing current/max records
              - Normal: {'used': 0-6, 'of': 6}
              - Error: {'used': -1, 'of': 6} if OCR fails

    Note:
        Coordinates: rows 775-800, cols 460-510 (record counter area at bottom)
        Special case: Checks for exact "0/6" image match before attempting OCR
    """
    try:
        sc = bot.screenshot()
        # Crop to record counter area (bottom of studio screen)
        # Coordinates: rows 775-800, cols 460-510
        image = sc[775:800, 460:510]

        # Check for exact image match of "0/6" (faster than OCR)
        if bot.find_and_click("record0", accuracy=0.99, tap=False, screenshot=image):
            return {'used': 0, 'of': 6}

        # Use general ratio extraction with studio-specific fallback
        return extract_ratio_from_image(bot, image, fallback_used=-1, fallback_of=6)

    except Exception as e:
        bot.log(f"ERROR: {e}")
        return {'used': -1, 'of': 6}


def adjust_level(bot, target):
    """Adjust the level selector UI to match target level using OCR and +/- buttons

    This function reads the current level from the UI and clicks the increase/decrease
    buttons until the desired target level is reached.

    Args:
        bot: Bot instance for OCR and clicking
        target: Target level number to reach (-1 to skip adjustment entirely)

    Note:
        - Uses white pixel isolation OCR to read "Level X" text
        - Clicks "search-min" button to decrease level
        - Clicks "search-max" button to increase level
        - Maximum 100 adjustment attempts to prevent infinite loops
        - Crop coordinates: rows 830-850, cols 0-540 (level display area)
    """
    if target == -1:
        return

    was_level_adjusted = True
    level_adjust_count = 0
    max_level_adjustments = 100  # Absolute safety limit to prevent infinite loops

    while was_level_adjusted and level_adjust_count < max_level_adjustments:
        was_level_adjusted = False

        if target != 0:
            sc = bot.screenshot()
            # Crop to level display area at bottom of search screen
            # Coordinates: rows 830-850, cols 0-540
            crop = sc[830:850, 0:540]

            # === WHITE TEXT ISOLATION ===
            # Isolate white pixels for "Level X" text recognition
            white_threshold = np.array([255, 255, 255, 255])  # RGBA format
            tolerance = 40  # Allow pixels within 40 units of pure white

            # Create mask for pixels close to white
            mask = np.all(crop >= white_threshold - np.array([tolerance, tolerance, tolerance, 0]), axis=-1)

            # Create processed image where only near-white pixels are kept
            processed_image = np.zeros_like(crop)
            processed_image[mask] = white_threshold

            # OCR to extract level number from "Level X" text
            # Whitelist: "Levl" (letters) and digits 0-9
            text = pytesseract.image_to_string(bot.prepare_image_for_ocr(processed_image),
                                               config='--psm 7 -c tessedit_char_whitelist="Levl1234567890')
            bot.log(f'Level OCR: {text}')

            # Extract the level number from OCR text
            result = LEVEL_PATTERN.search(text)
            if not result:
                bot.log("Level OCR: No result")
                break

            current_level = int(result.group('level'))
            bot.log(f'Target:{target} Cur:{current_level}')

            # Click decrease button if current level is too high
            if target < current_level:
                bot.find_and_click("search-min", tap=True, accuracy=0.95)
                was_level_adjusted = True
                level_adjust_count += 1
            # Click increase button if current level is too low
            elif target > current_level:
                bot.find_and_click("search-max", tap=True, accuracy=0.95)
                level_adjust_count += 1
                was_level_adjusted = True

            time.sleep(1)  # Wait for UI to update

            # Safety check: if we've adjusted more times than the target level,
            # something is wrong - stop adjusting
            if level_adjust_count > target:
                was_level_adjusted = False

    if level_adjust_count >= max_level_adjustments:
        log(f"WARNING: Reached max level adjustment limit ({max_level_adjustments}) - stopping adjustments")


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
    # Debug logging
    if bot.gui and hasattr(bot.gui, 'debug') and bot.gui.debug.get():
        log(f"DEBUG: do_concert() started for user {user}")

    if not bot.find_and_click("screen-map",accuracy=0.99, tap=False) and not bot.find_and_click("screen-main", accuracy=0.99, tap=False):
        if bot.gui and hasattr(bot.gui, 'debug') and bot.gui.debug.get():
            log("DEBUG: do_concert() - not on map or main screen, exiting")
        return
    
    bot.find_and_click("screen-main")
    time.sleep(1)
    
    counter = 0
    max_concert_loops = 10

    while counter < max_concert_loops:
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
            # Crop coordinates: rows 350-370, cols 1-35 (car status indicator area)
            crop = sc[350:370, 1:35]

            # If no cars sent yet, need to select and send a car
            if not bot.find_and_click('nocarssent', screenshot=crop, tap=False, accuracy=0.97):
                # Tap coordinates (115, 790): Car selection slot in garage
                bot.tap(115, 790)
                time.sleep(0.5)
                # Tap again to confirm car selection
                bot.tap(115, 790)
                time.sleep(1)

                # Tap coordinates (95, 580): "Concert" action button in menu
                bot.tap(95, 580)
                time.sleep(0.5)

                if not bot.find_and_click("search-target", tap=True, accuracy=0.92):
                    continue

                time.sleep(3)
            else:
                # Tap coordinates (270, 460): Concert list/search area
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
                    # Tap coordinates (500, 830): "Confirm" button for teleport dialog
                    bot.tap(500, 830)
                    time.sleep(0.3)
                    # Tap again to double-confirm teleport
                    bot.tap(500, 830)
                    break

                pause = random.randint(1, 100) / 100
        else:
            break

    # Wait for all cars to return before finishing
    # -2 indicates all cars have returned and are ready
    car_wait_counter = 0
    max_car_wait = 300  # 5 minutes (300 seconds)

    while get_active_cars(bot)["used"] != -2 and car_wait_counter < max_car_wait:
        log("Waiting for cars to return...")
        time.sleep(1)
        car_wait_counter += 1

    if car_wait_counter >= max_car_wait:
        log("WARNING: Timeout waiting for cars to return (5 minutes) - proceeding anyway")


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

    if not bot.find_and_click('rallyavailable',tap=False) and not bot.find_and_click('dangerrally',tap=False) and not bot.find_and_click('rallyradiodanger') and not bot.find_and_click('rallynormalrally'):
        return
    # Check car availability
    result = get_active_cars(bot)

    log(f'Rally Cars: {result["used"]}/{result["of"]}')

    # Only proceed if cars are available
    if result["used"] >= result["of"]:
        return

    # Join rally
    if bot.find_and_click('rallyavailable') or bot.find_and_click('dangerrally') or bot.find_and_click('rallyradiodanger') or bot.find_and_click('rallynormalrally'):
        counter=0
        while not bot.find_and_click('rallyjoin') and not bot.find_and_click('rallyradiojoin') and counter<=20:
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

    # Tap coordinates (485, 850): Studio building location on map
    bot.tap(485, 850)
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

    # Safety check: result["used"] should never be >6 from OCR, but protect against bad OCR reads
    record_count_attempts = 0
    while result["used"] > 6 and record_count_attempts < 20:
        time.sleep(0.1)
        result = get_record_count(bot)
        record_count_attempts += 1

    if record_count_attempts >= 20:
        log(f"WARNING: Record count stuck at {result['used']}/6 - possible OCR error, treating as 6/6")
        result = {'used': 6, 'of': 6}  # Force to safe value

    log(f'Records: {result["used"]}/{result["of"]}')

    # Check if we've reached the stop threshold - if so, return True to uncheck
    if bot.find_and_click("record6", tap=False, accuracy=0.92) or result["used"] >= stop:
        if result["used"] >= stop:
            log(f"Studio at {result['used']}/{result['of']} (target: {stop}) - Auto-unchecking")
            return True
        return False

    # Record a new album if slots are available
    if result["used"] < result["of"]:
        studio_counter = 0
        while not bot.find_and_click("studio", tap=True, accuracy=0.99) and studio_counter < 100:
            time.sleep(0.5)
            studio_counter += 1
        if studio_counter >= 100:
            log("WARNING: Studio button not found after 100 attempts")
            return False
        time.sleep(1)

        bot.find_and_click("askhelp", tap=True, accuracy=0.90)
        time.sleep(1)

        record_counter = 0
        while not bot.find_and_click("record", tap=True, accuracy=0.99) and record_counter < 100:
            time.sleep(0.1)
            record_counter += 1
        if record_counter >= 100:
            log("WARNING: Record button not found after 100 attempts")
            return False

        select_counter = 0
        while not bot.find_and_click("select", tap=True, accuracy=0.99) and select_counter < 100:
            time.sleep(0.1)
            select_counter += 1
        if select_counter >= 100:
            log("WARNING: Select button not found after 100 attempts")
            return False

        autoassign_counter = 0
        while not bot.find_and_click("autoassign", tap=True, accuracy=0.99) and autoassign_counter < 100:
            time.sleep(0.1)
            autoassign_counter += 1
        if autoassign_counter >= 100:
            log("WARNING: Autoassign button not found after 100 attempts")
            return False
        time.sleep(1)

        start_counter = 0
        while not bot.find_and_click("start", tap=True, accuracy=0.92) and start_counter < 100:
            time.sleep(0.1)
            start_counter += 1
        if start_counter >= 100:
            log("WARNING: Start button not found after 100 attempts")
            return False
        time.sleep(1)

        skip1_counter = 0
        while not bot.find_and_click("skip", tap=True, accuracy=0.99) and skip1_counter < 100:
            time.sleep(0.1)
            skip1_counter += 1
        if skip1_counter >= 100:
            log("WARNING: Skip button (1) not found after 100 attempts")
            return False
        time.sleep(1)

        skip2_counter = 0
        while not bot.find_and_click("skip", tap=True, accuracy=0.92) and skip2_counter < 100:
            time.sleep(0.1)
            skip2_counter += 1
        if skip2_counter >= 100:
            log("WARNING: Skip button (2) not found after 100 attempts")
            return False
        time.sleep(1)

        claim_counter = 0
        while not bot.find_and_click("claim", tap=True, accuracy=0.99) and claim_counter < 100:
            time.sleep(0.1)
            claim_counter += 1
        if claim_counter >= 100:
            log("WARNING: Claim button not found after 100 attempts")
            return False
        time.sleep(1)

    # Return False - continue checking, not at 6/6 yet
    return False


# ============================================================================
# GAME ACTION FUNCTIONS - GROUP ACTIVITIES
# ============================================================================

def assist(bot, use_min_fans=True):
    """Assist one group building by selecting and driving a character

    This function handles the process of:
    1. Finding and clicking the min/max slider settings
    2. Configuring character selection settings
    3. Selecting a random SSR character
    4. Driving to the building location

    Args:
        bot: BOT instance for game interactions
        use_min_fans: If True, clicks 'min' button; if False, clicks 'max' button (default: True)

    Note:
        - Uses random offsets for human-like clicking
        - Maximum 10 retries for finding settings
        - Logs which fan level is being used (min/max)
    """
    # Log which mode we're using
    fan_mode = "min" if use_min_fans else "max"
    log(f"assist() started - using {fan_mode} fans")

    # Smart fan selection: check which button is visible first
    log(f"Checking current fan mode selection")

    # Check if min button is visible
    min_visible = bot.find_and_click("min", tap=False)
    # Check if max button is visible
    max_visible = bot.find_and_click("max", tap=False)

    if use_min_fans:
        # We want min fans
        if min_visible:
            # Min button visible means min is NOT selected, need to click it
            log("Min button visible - clicking to select min fans")
            if bot.find_and_click("min"):
                log("'min' button clicked successfully")
            else:
                log("WARNING: Failed to click 'min' button")
        elif max_visible:
            # Max button visible means max IS selected, min is already selected - do nothing
            log("Max button visible - min fans already selected, no action needed")
        else:
            # Neither visible - wait and retry
            log("Neither min nor max button visible - waiting and retrying (max 5 attempts)")
            counter = 0
            while not bot.find_and_click("min") and counter <= 5:
                counter += 1
                time.sleep(1)
            if counter > 5:
                log("WARNING: 'min' button not found after 5 attempts")
            else:
                log(f"'min' button clicked successfully (attempt {counter})")
    else:
        # We want max fans
        if max_visible:
            # Max button visible means max is NOT selected, need to click it
            log("Max button visible - clicking to select max fans")
            if bot.find_and_click("max"):
                log("'max' button clicked successfully")
            else:
                log("WARNING: Failed to click 'max' button")
        elif min_visible:
            # Min button visible means min IS selected, max is already selected - do nothing
            log("Min button visible - max fans already selected, no action needed")
        else:
            # Neither visible - wait and retry
            log("Neither min nor max button visible - waiting and retrying (max 5 attempts)")
            counter = 0
            while not bot.find_and_click("max") and counter <= 5:
                counter += 1
                time.sleep(1)
            if counter > 5:
                log("WARNING: 'max' button not found after 5 attempts")
            else:
                log(f"'max' button clicked successfully (attempt {counter})")

    # Find and click settings button
    log("Looking for 'settings' button (max 10 attempts)")
    counter = 0
    while not bot.find_and_click("settings") and counter <= 10:
        counter += 1
        time.sleep(0.1)

    if counter > 10:
        log("WARNING: 'settings' button not found after 10 attempts")
    else:
        log(f"'settings' button found (attempt {counter})")

    # Keep clicking settings until it's gone (or brokensettings appears)
    log("Clicking 'settings' until dialog opens")
    settings_timeout = 0
    max_settings_timeout = 300  # 30 seconds (300 * 0.1s)

    while (bot.find_and_click("settings") or bot.find_and_click("brokensettings", offset_y=5)) and settings_timeout < max_settings_timeout:
        time.sleep(0.1)
        settings_timeout += 1

    if settings_timeout >= max_settings_timeout:
        log("WARNING: Settings button timeout (30s) - dialog may not have opened properly")

    time.sleep(2)
    log("Settings dialog opened - configuring character selection")

    # Uncheck all checkboxes
    offset_x = random.randint(1, 15)
    offset_y = random.randint(1, 10)

    log("Unchecking all character filters")
    check_count = 0
    max_uncheck = 10  # Prevent infinite clicking

    while bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y) and check_count < max_uncheck:
        check_count += 1
        time.sleep(0.1)
        offset_x = random.randint(1, 15)
        offset_y = random.randint(1, 10)
    log(f"Unchecked {check_count} character filters")

    if check_count >= max_uncheck:
        log("WARNING: Reached max uncheck limit (10) - may still have checked filters")

    # Click twice more to ensure all are unchecked
    time.sleep(1)
    bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y)
    time.sleep(1)
    bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y)

    # Swipe to reveal SSR characters
    log("Swiping to reveal SSR characters")
    # Swipe coordinates: from (270, 630) to (270, -700) - vertical swipe down to scroll character list
    bot.swipe(270, 630, 270, -700)

    time.sleep(3)
    log("Selecting random SSR character")
    if bot.find_and_click("randomssr"):
        log("Random SSR character selected successfully")
    else:
        log("WARNING: 'randomssr' not found - selection may have failed")

    # Find and click drive to button
    time.sleep(0.5)
    log("Looking for 'settingsdriveto' button (max 10 attempts)")
    counter = 0
    while not bot.find_and_click("settingsdriveto"):
        counter += 1
        if counter >= 10:
            log("ERROR: 'settingsdriveto' button not found after 10 attempts - returning early")
            return
        time.sleep(0.1)
    log(f"'settingsdriveto' button clicked (attempt {counter})")

    time.sleep(2)
    log("Clicking 'continuemarch' to complete assist")
    if bot.find_and_click("continuemarch"):
        log("assist() completed successfully")
    else:
        log("WARNING: 'continuemarch' button not found - assist may not have completed properly")


def send_assist(bot, use_min_fans=True):
    """Send assistance to group buildings with pre-processing steps

    This function handles the complete assist workflow:
    1. Checks if already in settings window, assist screen, or join screen
    2. If not, taps building location to open menu
    3. Handles acceleration popup if present
    4. Clicks assist and join buttons in sequence
    5. Calls assist() function with appropriate fan parameter

    Args:
        bot: BOT instance for game interactions
        use_min_fans: If True, uses minimum fans; if False, uses maximum fans (default: True)

    Note:
        - Performs pre-processing before calling assist()
        - Logs each major step for debugging
        - Handles acceleration popup automatically
    """
    fan_type = "minimum" if use_min_fans else "maximum"
    log(f"send_assist started with {fan_type} fans")

    # Check if we're already in the settings/assist/join screens
    in_settings = bot.find_and_click("settingswindow", accuracy=0.99, tap=False)
    in_assist = bot.find_and_click("sendassist", accuracy=0.99, tap=False)
    in_join = bot.find_and_click("sendjoin", accuracy=0.99, tap=False)

    if not (in_settings or in_assist or in_join):
        log("Not in settings/assist/join screen - tapping building location")
        # Tap coordinates (270, 470): Building location on zone map to open menu
        bot.tap(270, 470)
        time.sleep(1.5)

        # Handle acceleration popup if it appears
        if bot.find_and_click("sendaccelerate", accuracy=0.99, tap=True):
            log("Acceleration popup found - clicked to proceed")
            time.sleep(1)
        else:
            log("No acceleration popup detected")

        # Click assist and join buttons in sequence
        log("Looking for assist and join buttons")
        clicked_assist = False
        clicked_join = False
        loop_counter = 0

        while not (clicked_assist and clicked_join):
            loop_counter += 1

            # Safety check to prevent infinite loop
            if loop_counter > 20:
                log("WARNING: Exceeded max loops (20) waiting for assist/join buttons")
                break

            if not clicked_assist and bot.find_and_click("sendassist", accuracy=0.99,tap=False):
                # Keep clicking until button disappears (indicating it was successfully clicked)
                assist_click_counter = 0
                while bot.find_and_click("sendassist", accuracy=0.99) and assist_click_counter < 100:
                    time.sleep(0.1)
                    assist_click_counter += 1
                if assist_click_counter >= 100:
                    log("WARNING: Send assist button click limit reached (100)")
                clicked_assist = True
                log("Successfully clicked 'assist' button")

            if not clicked_join and bot.find_and_click("sendjoin", accuracy=0.99,tap=False):
                # Keep clicking until button disappears
                join_click_counter = 0
                while bot.find_and_click("sendjoin", accuracy=0.99) and join_click_counter < 100:
                    time.sleep(1)
                    join_click_counter += 1
                if join_click_counter >= 100:
                    log("WARNING: Send join button click limit reached (100)")
                clicked_join = True
                log("Successfully clicked 'join' button")

            time.sleep(0.1)

        if clicked_assist and clicked_join:
            log("Pre-processing complete - both buttons clicked successfully")
        else:
            log(f"WARNING: Pre-processing incomplete - assist:{clicked_assist}, join:{clicked_join}")

        time.sleep(2)
    else:
        log(f"Already in correct screen - settings:{in_settings}, assist:{in_assist}, join:{in_join}")

    # Call the main assist function with the appropriate parameter
    log(f"Calling assist() with use_min_fans={use_min_fans}")
    assist(bot, use_min_fans=use_min_fans)

    log(f"send_assist completed for {fan_type} fans")


def do_recover(bot, user):
    """Perform recovery and screen validation operations

    This function is called at the end of each bot loop iteration to:
    - Validate screen state (should be on map or main screen)
    - Close any unwanted popups or dialogs
    - Handle maintenance notifications
    - Navigate back to correct screen if lost

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups (currently unused)

    Note:
        - Called automatically at end of each bot loop (if enabled)
        - Can be disabled via GUI checkbox
        - Helps prevent bot from getting stuck in wrong screens
        - Handles maintenance mode with 5-minute wait
    """
    _ = user  # Unused parameter

    # Check if we're on the correct screen
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if on_map or on_main:
        # Already on correct screen, no recovery needed
        if bot.find_and_click("fixmapassist", accuracy=0.99,tap=False):
            # Tap coordinates (250, 880): Click away from assist dialog on map
            bot.tap(250, 880)
            log("Recovery: Clicked away from Assist")
        if bot.find_and_click("fixratingpopup", accuracy=0.99):
            log("Recovery: Exiting Rating Pop-up")
        return

    # Not on correct screen - attempt recovery
    log("Recovery: Not on map/main screen - attempting navigation fixes")

    recovery_attempts = 0
    max_attempts = 20  # Prevent infinite loop

    while not (on_map or on_main) and recovery_attempts < max_attempts:
        recovery_attempts += 1

        # Check if Fix checkbox was unchecked (exit early if disabled)
        if bot.gui and hasattr(bot.gui, 'fix_enabled') and not bot.gui.fix_enabled.get():
            log("Recovery: Fix checkbox disabled - exiting recovery loop")
            return

        # Try various close/back buttons
        if bot.find_and_click("fixgroupgiftx", accuracy=0.99):
            log("Recovery: Closed group gift screen")
        if bot.find_and_click("fixgroupback", accuracy=0.99):
            log("Recovery: Clicked group back button")
        if bot.find_and_click("fixmainad"):
            log("Recovery: Closed ad popup")
        if bot.find_and_click("fixgrouprallyback", accuracy=0.99):
            log("Recovery: Clicked rally back button")
        if bot.find_and_click("fixgameclosed", accuracy=0.99):
            log("Recovery: Clicked open game")
        if bot.find_and_click("fixceocard",accuracy=0.99,tap=False):
            # Tap coordinates (250, 880): Click away from CEO card popup
            bot.tap(250, 880)
            log("Recovery: Clicked away on CEO card")
        if bot.find_and_click("fixgenericback",accuracy=0.91):
            log("Recovery: Clicked Back")

        

        # Handle maintenance notification (wait 5 minutes if found)
        if bot.find_and_click("fixmaintenanceconfirm", accuracy=0.99):
            log("Recovery: Maintenance detected - waiting 5 minutes")
            # Wait in 10-second intervals to allow early exit if Fix is unchecked
            for _ in range(30):  # 30 iterations * 10 seconds = 300 seconds (5 minutes)
                time.sleep(10)
                # Check if Fix checkbox was unchecked during wait
                if bot.gui and hasattr(bot.gui, 'fix_enabled') and not bot.gui.fix_enabled.get():
                    log("Recovery: Fix checkbox disabled during maintenance wait - exiting")
                    return

        time.sleep(0.1)

        # Check screen state again
        on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
        on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if on_map or on_main:
        log(f"Recovery: Successfully returned to correct screen (attempts: {recovery_attempts})")
    else:
        log(f"WARNING: Recovery failed after {max_attempts} attempts - still not on map/main screen")


def do_group(bot, user):
    """Perform comprehensive group-related activities

    Executes a complete workflow for group activities:
    1. Navigation: Verifies correct screen and navigates to group menu
    2. Gifts: Collects available gifts and claims rewards
    3. Investments: Makes investments in group plans
    4. Zone: Participates in zone activities and claims rewards
    5. Assist: Finds and assists group buildings with characters

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups (currently unused)

    Returns:
        None - Exits early if navigation fails or timeouts occur

    Note:
        - Starts cooldown timer only on successful completion
        - Uses human-like random offsets for clicking
        - Maximum retry limits on all wait loops to prevent hanging
        - Comprehensive logging for debugging each phase
    """
    _ = user  # Unused parameter
    log("do_group started")

    # ========== PHASE 1: NAVIGATION ==========
    log("Phase 1: Verifying screen state")
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if not (on_map or on_main):
        log("ERROR: Not on map or main screen - aborting do_group")
        return
    log(f"Screen verified - map:{on_map}, main:{on_main}")

    # Navigate to group menu
    log("Navigating to group menu")
    while bot.find_and_click("group", accuracy=0.99) or bot.find_and_click("help", accuracy=0.99):
        time.sleep(0.2)

    # Wait for gift button to appear (indicates group menu loaded)
    log("Waiting for group menu to load")
    while not bot.find_and_click("gift") and bot.find_and_click("group", accuracy=0.99):
        time.sleep(0.3)

    # Wait for group screen to fully load
    log("Waiting for group screen to fully load (max 10 attempts)")
    counter = 0
    while not bot.find_and_click("groupfullyloaded", tap=False):
        counter += 1
        time.sleep(0.2)
        if counter > 10:
            log("ERROR: Group screen failed to load after 10 attempts - aborting")
            return
    log(f"Group screen loaded successfully (attempt {counter})")

    # ========== PHASE 2: GIFTS ==========
    log("Phase 2: Processing gifts")

    # Click gift button to open gift screen
    offset_x = random.randint(1, 5)
    offset_y = random.randint(1, 5)
    gift_clicks = 0
    while bot.find_and_click("gift", offset_x=offset_x, offset_y=offset_y, accuracy=0.98):
        gift_clicks += 1
        time.sleep(0.3)
    log(f"Gift button clicked {gift_clicks} times")

    time.sleep(1)

    # Ensure we're on gift screen
    while not bot.find_and_click("giftscreen", accuracy=0.99, tap=False) and bot.find_and_click("gift"):
        time.sleep(0.3)

    # Collect and claim gifts
    gifts_collected = False
    if bot.find_and_click("giftcollect"):
        log("Collecting gifts")
        time.sleep(1)
        # Tap coordinates (250, 880): Close gift collection dialog
        bot.tap(250, 880)
        time.sleep(2)
        gifts_collected = True

    if bot.find_and_click("claimall"):
        log("Claiming all rewards")
        time.sleep(1)
        # Tap coordinates (250, 880): Confirm claim
        bot.tap(250, 880)
        time.sleep(1)
        # Tap again to close rewards dialog
        bot.tap(250, 880)
        time.sleep(2)
        gifts_collected = True

    if not gifts_collected:
        log("No gifts to collect or claim")

    # Close gift screen
    if bot.find_and_click("giftscreenx", accuracy=0.99):
        log("Gift screen closed")

    # ========== PHASE 3: INVESTMENTS ==========
    log("Phase 3: Processing investments")

    # Navigate back to group menu and wait for plan button
    counter = 0
    while not bot.find_and_click("plan", tap=False):
        counter += 1
        # Tap coordinates (250, 880): Close current dialog/return to group menu
        bot.tap(250, 880)
        time.sleep(0.5)
        if counter == 10:
            log("ERROR: Plan button not found after 10 attempts - aborting")
            return
    log(f"Plan button found (attempt {counter})")

    # Click plan and make investments
    bot.find_and_click("plan")
    time.sleep(1)

    invest_count = 0
    while not bot.find_and_click("grouppaidinvest", accuracy=0.99, tap=False):
        if bot.find_and_click("invest", accuracy=0.99):
            invest_count += 1
        time.sleep(0.2)
    log(f"Made {invest_count} investments")

    # ========== PHASE 4: ZONE ACTIVITIES ==========
    log("Phase 4: Processing zone activities")

    # Navigate to zone
    while not bot.find_and_click("zone", accuracy=0.99):
        time.sleep(0.2)
        # Tap coordinates (250, 880): Close dialogs/return to group menu
        bot.tap(250, 880)
        bot.find_and_click("rallyback")

    # Click zone until screen opens
    offset_x = random.randint(1, 5)
    offset_y = random.randint(1, 5)
    zone_clicks = 0
    while bot.find_and_click("zone", offset_x=offset_x, offset_y=offset_y, accuracy=0.98):
        zone_clicks += 1
        time.sleep(0.5)
    log(f"Zone button clicked {zone_clicks} times")

    time.sleep(1.5)

    # Claim zone rewards
    if bot.find_and_click("groupclaim"):
        log("Zone rewards claimed")
    else:
        log("No zone rewards to claim")

    time.sleep(0.3)

    # ========== PHASE 5: ASSIST BUILDINGS ==========
    log("Phase 5: Looking for buildings to assist")

    counter = 0
    offset_x = random.randint(1, 30)
    offset_y = random.randint(1, 35)
    buildings_found = True

    # Search for assist button (with swipe to reveal more buildings)
    while not bot.find_and_click("assist", accuracy=0.92, offset_x=offset_x, offset_y=offset_y) and counter <= 10:
        # Check if zone is in normal state (no buildings to assist)
        if bot.find_and_click("groupzonenormal", accuracy=0.95, tap=False):
            log("Zone in normal state - no buildings need assistance")
            counter = 10
            buildings_found = False
        counter += 1
        time.sleep(0.1)
        # Swipe coordinates: from (270, 490) to (400, 490) - horizontal swipe to reveal more buildings
        bot.swipe(270, 490, 400, 490)

    if buildings_found and counter <= 6:
        log(f"Building found requiring assistance (search attempts: {counter})")
        bot.find_and_click("assist")
        time.sleep(2)
        assist(bot, use_min_fans=True)
    elif buildings_found:
        log(f"Building found but took too many attempts ({counter}) - backing out")
        offset_x = random.randint(1, 30)
        offset_y = random.randint(1, 35)
        back_count = 0
        while bot.find_and_click("back", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            back_count += 1
            time.sleep(1)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)
        log(f"Backed out of assist screen ({back_count} backs)")
    else:
        log("No buildings found requiring assistance")
        back_count = 0  # Initialize back_count
        while bot.find_and_click("back", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            back_count += 1
            time.sleep(1)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)
        if back_count > 0:
            log(f"Backed out of zone screen ({back_count} backs)")

    # ========== COOLDOWN TIMER ==========
    # Start cooldown timer only if no buildings were found (successfully completed all tasks)
    if not buildings_found:
        log("do_group completed successfully - starting cooldown timer")
        global gui_instance
        if gui_instance:
            gui_instance.last_run_times['doGroup'] = time.time()
    else:
        log("do_group completed - cooldown NOT started (assisted building)")




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
    time.sleep(2)

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
        time.sleep(2)
        # Tap coordinates (250, 880): Close XP collection reward dialog
        bot.tap(250, 880)
        time.sleep(1)
        # Tap again to close any follow-up dialogs
        bot.tap(250, 880)
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

    Attempts to find and click the heal assist button on the main screen.
    If not immediately visible, scrolls down to reveal it.

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups (unused)

    Note:
        Swipe coordinates: from (230, 830) to (230, 700) - vertical swipe up to scroll down
    """
    _ = user  # Unused parameter
    if not bot.find_and_click("healassist", accuracy=0.91):
        bot.log("Dragging to find heal assist")
        # Swipe coordinates: from (230, 830) to (230, 700) - swipe up to reveal heal button
        bot.swipe(230, 830, 230, 700)
        time.sleep(3)
    time.sleep(0.5)


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


def do_parking(bot, user):
    """Perform parking-related activities

    Placeholder function for parking functionality.
    Implementation to be added.

    Args:
        bot: BOT instance for game interactions
        user: Username for configuration lookups

    Note:
        This is a placeholder function
    """
    _ = user  # Unused parameter

    # ========== PHASE 1: NAVIGATION ==========
    log("Phase 1: Verifying screen state")
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if not (on_map or on_main):
        log("ERROR: Not on map or main screen - aborting do_group")
        return
    log(f"Screen verified - map:{on_map}, main:{on_main}")

    if on_map:
        bot.find_and_click('screen-map')
    time.sleep(0.3)

    # ========== PHASE 2: COLLECT ==========
    # Search region: (x=10, y=570, width=85, height=20) - parking spot indicator area on main screen
    first_check=bot.find_all('main-parking-activespot',accuracy=0.99,search_region=(10, 570, 85, 20))
    time.sleep(0.3)
    second_check=bot.find_all('main-parking-activespot',accuracy=0.99,search_region=(10, 570, 85, 20))
    if first_check['count']==6 and second_check['count']==6:
        log("Parking - All parking spots are currently active!")
        return
    else:
        log(f'First: {first_check}')
        log(f'Second: {second_check}')
        bot.find_and_click('main-parking-button')
        time.sleep(2)
        log(bot.find_all('parking-main-claim'))
        while bot.find_and_click('parking-main-claim'):
            while not bot.find_and_click('parking-main-coin', accuracy=0.99,tap=False):
                time.sleep(0.1)

            while bot.find_and_click('parking-main-coin', tap=False):
                # Tap coordinates (420, 90): Close coin collection popup
                bot.tap(420, 90)
                time.sleep(1)
                
            time.sleep(1)
        # ========== PHASE 3: PARK ==========
        # Swipe coordinates: from (270, 630) to (270, -700) - vertical swipe to scroll parking lot list
        bot.swipe(270, 630, 270, -700)
        if bot.find_and_click('parking-main-gardencarpark'):
            time.sleep(2)

        # Park cars in up to 6 available spots
        for counter in range(6):
            bot.find_and_click('parking-lot-findspot')
            time.sleep(2)

            
        else:
            return
        log("Finished Parking!")
        time.sleep(100000)


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
        # Order: Row 1: Street, Studio, Group
        #        Row 2: Concert, Help, Coin, Heal
        #        Row 3: Rally, Parking
        self.function_states = {
            'doStreet': tk.BooleanVar(value=False),
            'doStudio': tk.BooleanVar(value=False),
            'doGroup': tk.BooleanVar(value=False),
            'doConcert': tk.BooleanVar(value=False),
            'doHelp': tk.BooleanVar(value=False),
            'doCoin': tk.BooleanVar(value=False),
            'doHeal': tk.BooleanVar(value=False),
            'doRally': tk.BooleanVar(value=False),
            'doParking': tk.BooleanVar(value=False)
        }

        # Special function states (moved to settings)
        self.fix_enabled = tk.BooleanVar(value=True)  # Fix/Recover function - checked by default

        # Settings
        self.sleep_time = tk.StringVar(value="1")
        self.studio_stop = tk.StringVar(value="6")
        self.screenshot_interval = tk.StringVar(value="0")
        self.debug = tk.BooleanVar(value=False)

        # Bot state
        self.is_running = False
        self.bot_thread = None

        # Screenshot state
        self.screenshot_running = False
        self.screenshot_thread = None

        # Live screenshot updater for remote monitoring (high frequency)
        self.live_screenshot_running = False
        self.live_screenshot_thread = None

        # Remote command monitoring (runs independently of bot loop)
        self.remote_monitoring_running = False
        self.remote_monitoring_thread = None

        # Log buffer
        self.log_buffer = []
        self.detailed_log_buffer = []  # Stores (timestamp, message, screenshot_path) tuples

        # Cooldown display labels (for functions with cooldowns)
        self.cooldown_labels = {}
        self.max_log_lines = 300
        self.user_scrolling = False

        # Track last run times for cooldown system
        self.last_run_times = {}

        # Shortcut triggers (for immediate execution on next bot loop)
        self.shortcut_triggers = {
            'assist_min_fans': False,
            'assist_max_fans': False
        }

        # Debug logging setup
        self.log_db = None
        if self.debug.get():
            self.log_db = LogDatabase(self.username)

        # State monitoring setup
        self.state_manager = StateManager(self.username)
        self._state_update_counter = 0  # Counter to throttle state updates

        self.create_widgets()

        # Enable debug callback to initialize database when checkbox is toggled
        self.debug.trace_add('write', self._on_debug_toggle)

        # Setup state update callbacks for checkboxes and settings
        self._setup_state_callbacks()

        # Start remote monitoring thread (runs independently of bot loop)
        self.start_remote_monitoring()

    def _on_debug_toggle(self, *_):
        """Handle debug checkbox toggle - initialize/close database

        This is called whenever the Debug checkbox state changes, regardless of
        whether the bot is running or stopped. It immediately starts/stops
        database logging.
        """
        if self.debug.get():
            # Debug enabled - create database connection
            if self.log_db is None:
                try:
                    self.log_db = LogDatabase(self.username)
                    self.log("Debug mode enabled - logging to database")
                except Exception as e:
                    self.log(f"ERROR: Failed to enable debug mode: {e}")
                    self.log_db = None
        else:
            # Debug disabled - close database connection
            if self.log_db is not None:
                try:
                    self.log("Debug mode disabled - stopping database logging")
                    self.log_db.close()
                except Exception as e:
                    # Log error but continue cleanup
                    print(f"Error closing database: {e}")
                finally:
                    self.log_db = None

    def _setup_state_callbacks(self):
        """Setup callbacks to update state manager when GUI changes

        Attaches trace callbacks to all GUI variables so that changes are
        automatically synchronized to the state manager (for remote monitoring).

        Note:
            - Monitors all function checkboxes
            - Monitors all settings (Fix, Debug, Sleep time, Studio stop, Screenshot interval)
            - Performs initial state sync after setup
        """
        # Add trace callbacks for all checkboxes
        for func_name, var in self.function_states.items():
            var.trace_add('write', lambda *args, fn=func_name: self._on_checkbox_change(fn))

        # Add trace callbacks for settings
        self.fix_enabled.trace_add('write', self._on_settings_change)
        self.debug.trace_add('write', self._on_settings_change)
        self.sleep_time.trace_add('write', self._on_settings_change)
        self.studio_stop.trace_add('write', self._on_settings_change)
        self.screenshot_interval.trace_add('write', self._on_settings_change)

        # Initial state update
        self._update_full_state()

    def _on_checkbox_change(self, checkbox_name):
        """Handle checkbox state change - update state manager

        Called automatically when any function checkbox is toggled.
        Synchronizes the change to the state manager for remote monitoring.

        Args:
            checkbox_name (str): Name of the checkbox that changed (e.g., 'doConcert')
        """
        try:
            enabled = self.function_states[checkbox_name].get()
            self.state_manager.update_checkbox_state(checkbox_name, enabled)
        except Exception as e:
            print(f"Error updating checkbox state: {e}")

    def _on_settings_change(self, *args):
        """Handle settings change - update state manager

        Called automatically when any setting variable changes.
        Synchronizes all settings to the state manager for remote monitoring.

        Args:
            *args: Unused trace callback arguments
        """
        try:
            self.state_manager.update_settings(
                fix_enabled=self.fix_enabled.get(),
                debug_enabled=self.debug.get(),
                sleep_time=float(self.sleep_time.get()) if self.sleep_time.get() else 1.0,
                studio_stop=int(self.studio_stop.get()) if self.studio_stop.get() else 6,
                screenshot_interval=int(self.screenshot_interval.get()) if self.screenshot_interval.get() else 0
            )
        except Exception as e:
            print(f"Error updating settings state: {e}")

    def _update_full_state(self):
        """Update all state in state manager - performs full synchronization

        This method performs a complete state sync of all checkboxes and settings
        to the state manager. Called during initialization.
        """
        try:
            # Update all checkboxes
            self.state_manager.update_all_checkbox_states(self.function_states)

            # Update all settings
            self._on_settings_change()
        except Exception as e:
            print(f"Error updating full state: {e}")

    def _get_timestamp(self, with_milliseconds=False):
        """Get formatted timestamp

        Args:
            with_milliseconds: If True, includes .SSS milliseconds

        Returns:
            str: Formatted timestamp
        """
        now = datetime.now()
        if with_milliseconds:
            return now.strftime("%H:%M:%S.%f")[:-3]  # Keep only 3 digits of microseconds
        return now.strftime("%H:%M:%S")

    def create_widgets(self):
        """Create all GUI widgets and layout the interface

        Builds the complete GUI structure including:
        - Top bar with username and status
        - Functions section with checkboxes
        - Shortcuts section with quick action buttons
        - Settings and controls section
        - Log window at bottom
        """
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
        """Create the functions checkboxes section

        Builds a grid of checkboxes for bot functions based on layout from config.json.
        Each checkbox controls whether a specific function is enabled in the bot loop.

        Args:
            parent: Parent tkinter widget to attach this section to
        """
        functions_frame = ttk.LabelFrame(parent, text="Functions", padding=1)
        functions_frame.pack(fill="x", padx=1)

        # Load function layout from config.json
        config = load_config()
        row_layout = config.get('function_layout', [
            ['doStreet', 'doStudio', 'doGroup'],
            ['doHelp', 'doCoin', 'doHeal'],
            ['doRally', 'doConcert', 'doParking']
        ])

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
        """Create the settings and control buttons section

        Builds the right-side panel containing:
        - Bot loop sleep time setting
        - Screenshot interval setting
        - Debug and Fix checkboxes
        - Screenshot button
        - Open Log Viewer button
        - Start/Stop button

        Args:
            parent: Parent tkinter widget to attach this section to
        """
        right_frame = ttk.Frame(parent)
        right_frame.pack(side="right", fill="y", padx=1)

        # Settings
        settings_frame = ttk.LabelFrame(right_frame, text="Settings", padding=2)
        settings_frame.pack(fill="x", pady=1)

        # Bot loop sleep time - label and entry on same line with 's' suffix
        sleep_frame = ttk.Frame(settings_frame)
        sleep_frame.pack(fill="x", pady=1)
        ttk.Label(sleep_frame, text="Bot loop:", font=("Arial", 7)).pack(side="left")
        ttk.Entry(sleep_frame, textvariable=self.sleep_time, width=2).pack(side="left", padx=(2, 0))
        ttk.Label(sleep_frame, text="s", font=("Arial", 7)).pack(side="left", padx=(1, 0))

        # Screenshot interval - label and entry on same line with 's' suffix
        screenshot_frame = ttk.Frame(settings_frame)
        screenshot_frame.pack(fill="x", pady=1)
        ttk.Label(screenshot_frame, text="Screenshot:", font=("Arial", 7)).pack(side="left")
        ttk.Entry(screenshot_frame, textvariable=self.screenshot_interval, width=2).pack(side="left", padx=(2, 0))
        ttk.Label(screenshot_frame, text="s", font=("Arial", 7)).pack(side="left", padx=(1, 0))

        # Debug and Fix checkboxes on same line
        debug_fix_frame = ttk.Frame(settings_frame)
        debug_fix_frame.pack(fill="x", pady=1)
        ttk.Checkbutton(debug_fix_frame, text="Debug",
                       variable=self.debug).pack(side="left")
        ttk.Checkbutton(debug_fix_frame, text="Fix",
                       variable=self.fix_enabled).pack(side="left", padx=(10, 0))

        # Screenshot button
        screenshot_button_frame = ttk.Frame(settings_frame)
        screenshot_button_frame.pack(fill="x", pady=(4, 1))
        self.screenshot_button = ttk.Button(screenshot_button_frame, text="Screenshot",
                                            command=self.toggle_screenshot)
        self.screenshot_button.pack(fill="x")

        # Open Log Viewer button
        open_log_button_frame = ttk.Frame(settings_frame)
        open_log_button_frame.pack(fill="x", pady=(1, 1))
        self.open_log_button = ttk.Button(open_log_button_frame, text="Open Log Viewer",
                                          command=self.open_log_viewer)
        self.open_log_button.pack(fill="x")

        # Start/Stop button at bottom
        button_frame = ttk.Frame(settings_frame)
        button_frame.pack(fill="x", pady=(1, 2))
        self.toggle_button = ttk.Button(button_frame, text="Start", command=self.toggle_bot)
        self.toggle_button.pack(fill="x")

    def _create_shortcuts_section(self, parent):
        """Create the shortcuts section under Functions

        Builds quick-action buttons for immediate execution of specific tasks:
        - Min Fans: Send assist with minimum fans
        - Max Fans: Send assist with maximum fans

        These shortcuts execute immediately on the next bot loop iteration,
        bypassing the normal function enable/disable checkboxes.

        Args:
            parent: Parent tkinter widget to attach this section to
        """
        shortcuts_frame = ttk.LabelFrame(parent, text="Shortcuts", padding=2)
        shortcuts_frame.pack(fill="x", padx=1, pady=(2, 0))

        # Create a row of shortcut buttons
        button_row = ttk.Frame(shortcuts_frame)
        button_row.pack(fill="x")

        # Min fans button
        min_fan_button = ttk.Button(button_row, text="Min Fans", command=self.trigger_assist_min_fans)
        min_fan_button.pack(side="left", padx=2, pady=1)

        # Max fans button
        max_fan_button = ttk.Button(button_row, text="Max Fans", command=self.trigger_assist_max_fans)
        max_fan_button.pack(side="left", padx=2, pady=1)

    def trigger_assist_min_fans(self):
        """Trigger assist with minimum fans on next bot loop cycle

        This is a shortcut button handler that sets a trigger flag to execute
        send_assist(bot, use_min_fans=True) on the next bot loop iteration.

        Note:
            - Executes immediately on next bot loop (high priority)
            - Logs the trigger event for tracking
        """
        self.shortcut_triggers['assist_min_fans'] = True
        self.log("Min fans shortcut triggered - will execute on next bot loop")

    def trigger_assist_max_fans(self):
        """Trigger assist with maximum fans on next bot loop cycle

        This is a shortcut button handler that sets a trigger flag to execute
        send_assist(bot, use_min_fans=False) on the next bot loop iteration.

        Note:
            - Executes immediately on next bot loop (high priority)
            - Logs the trigger event for tracking
        """
        self.shortcut_triggers['assist_max_fans'] = True
        self.log("Max fans shortcut triggered - will execute on next bot loop")

    def _create_log_section(self):
        """Create the log window section

        Builds the scrollable text widget that displays bot activity logs.
        - Maintains a 300-line buffer (FIFO)
        - Auto-scrolls to bottom unless user has manually scrolled up
        - Shows timestamps for each log entry
        """
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
        """Track when user manually scrolls the log window

        Called on mouse wheel or scroll events. Schedules a check to determine
        if the user has scrolled away from the bottom (disabling auto-scroll).

        Args:
            _event: Mouse event (unused)
        """
        self.root.after(100, self.check_scroll_position)
        return

    def check_scroll_position(self):
        """Check if log is scrolled to bottom to enable/disable auto-scroll

        If user is at the bottom (within 1%), auto-scrolling is enabled.
        If user has scrolled up, auto-scrolling is disabled to preserve position.
        """
        try:
            pos = self.log_text.yview()
            # If at bottom (within small threshold), enable auto-scroll
            self.user_scrolling = pos[1] < 0.99
        except:
            pass

    def log(self, message, screenshot=None):
        """Add message to log window with 300 line buffer

        Args:
            message: Message string to log
            screenshot: Optional screenshot numpy array to save (if Debug mode on)

        Note:
            - Adds timestamp to each message
            - Maintains 300 line buffer (FIFO)
            - Auto-scrolls only if user hasn't manually scrolled up
            - In Debug mode: saves to database with milliseconds and screenshots
            - Updates state manager with log and screenshot
        """
        # Determine if debug mode is on
        debug_mode = self.debug.get()

        # Get appropriate timestamp
        timestamp = self._get_timestamp(with_milliseconds=debug_mode)
        log_msg = f"[{timestamp}] {message}"

        # Save to database if debug mode is on
        entry_id = None
        if debug_mode and self.log_db:
            entry_id = self.log_db.add_log_entry(message, screenshot)

        # Add to detailed log buffer for debug viewer (stores entry_id instead of path)
        self.detailed_log_buffer.append((timestamp, message, entry_id))
        if len(self.detailed_log_buffer) > self.max_log_lines:
            self.detailed_log_buffer = self.detailed_log_buffer[-self.max_log_lines:]

        # Add to GUI log buffer
        self.log_buffer.append(log_msg)

        # Keep only last 300 lines (FIFO buffer)
        if len(self.log_buffer) > self.max_log_lines:
            self.log_buffer = self.log_buffer[-self.max_log_lines:]

        # Update text widget
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "\n".join(self.log_buffer))

        # Update state manager with log and screenshot
        # Throttle updates - only update every 5th log entry to reduce DB load
        self._state_update_counter += 1
        if self._state_update_counter >= 5 or screenshot is not None:
            self._state_update_counter = 0
            try:
                self.state_manager.add_log(message, screenshot)
            except Exception as e:
                print(f"Error updating state manager: {e}")

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
            - Updates state manager with running status
        """
        if self.is_running:
            # Stop the bot immediately
            global bot_running, bot
            self.is_running = False
            bot_running = False

            # Signal the bot instance to stop immediately
            if 'bot' in globals() and bot is not None:
                bot.should_stop = True

            # Stop live screenshot updater
            self.stop_live_screenshot_updater()

            self.toggle_button.config(text="Start")
            self.status_label.config(text="Stopped", foreground="red")
            self.current_action_label.config(text="Action: None")
            self.log("Stop button pressed - halting execution")

            # Mark as stopped in state manager
            try:
                self.state_manager.mark_stopped()
            except Exception as e:
                print(f"Error marking bot as stopped in state manager: {e}")
        else:
            # Start the bot
            self.is_running = True
            self.toggle_button.config(text="Stop")
            self.status_label.config(text="Running", foreground="green")
            self.bot_thread = threading.Thread(target=run_bot_loop, args=(self,), daemon=True)
            self.bot_thread.start()

            # Mark as running in state manager
            try:
                self.state_manager.mark_running()
            except Exception as e:
                print(f"Error marking bot as running in state manager: {e}")

            # Start live screenshot updater for remote monitoring
            self.start_live_screenshot_updater()

    def start_live_screenshot_updater(self):
        """Start background thread to update screenshots at high frequency for live feed

        Updates screenshots every 200ms (~5 FPS) independent of bot loop.
        This provides a near-live feed for the web interface.
        """
        if self.live_screenshot_running:
            return

        self.live_screenshot_running = True

        def screenshot_update_loop():
            """Background loop that captures and updates screenshots frequently"""
            global bot

            while self.live_screenshot_running and self.is_running:
                try:
                    # Capture screenshot from device
                    if 'bot' in globals() and bot is not None and hasattr(bot, 'andy'):
                        screenshot = bot.andy.screencap()
                        if screenshot is not None:
                            # Update state manager with JPEG encoding (fast)
                            self.state_manager.update_screenshot(screenshot, quality=85)
                except Exception as e:
                    # Silently continue on errors to avoid disrupting bot
                    pass

                # Update every 200ms for ~5 FPS live feed
                time.sleep(0.2)

        self.live_screenshot_thread = threading.Thread(
            target=screenshot_update_loop,
            daemon=True,
            name=f"LiveScreenshot-{self.username}"
        )
        self.live_screenshot_thread.start()

    def stop_live_screenshot_updater(self):
        """Stop the live screenshot updater thread"""
        self.live_screenshot_running = False
        if self.live_screenshot_thread:
            self.live_screenshot_thread.join(timeout=1.0)

    def start_remote_monitoring(self):
        """Start background thread to monitor remote commands

        This thread runs independently of the bot loop, allowing remote
        commands to be processed even when the bot is stopped.
        """
        if self.remote_monitoring_running:
            return

        self.remote_monitoring_running = True

        def remote_monitor_loop():
            """Background loop that checks for remote commands"""
            global bot

            while self.remote_monitoring_running:
                try:
                    # Only process commands if we have a state manager
                    if hasattr(self, 'state_manager'):
                        # Get pending commands for this device
                        commands = self.state_manager.get_pending_commands()

                        for cmd in commands:
                            cmd_type = cmd['command_type']
                            cmd_data = cmd['command_data']

                            if cmd_type == 'checkbox' and cmd_data:
                                # Update checkbox state
                                checkbox_name = cmd_data.get('name')
                                enabled = cmd_data.get('enabled')

                                if checkbox_name in self.function_states:
                                    self.function_states[checkbox_name].set(enabled)
                                    self.log(f"Remote: {checkbox_name} set to {enabled}")

                            elif cmd_type == 'setting' and cmd_data:
                                # Update setting
                                setting_name = cmd_data.get('name')
                                value = cmd_data.get('value')

                                if setting_name == 'sleep_time':
                                    self.sleep_time.set(str(value))
                                    self.log(f"Remote: Sleep time set to {value}")
                                elif setting_name == 'studio_stop':
                                    self.studio_stop.set(str(value))
                                    self.log(f"Remote: Studio stop set to {value}")
                                elif setting_name == 'fix_enabled':
                                    self.fix_enabled.set(bool(value))
                                    self.log(f"Remote: Fix enabled set to {value}")
                                elif setting_name == 'debug_enabled':
                                    self.debug.set(bool(value))
                                    self.log(f"Remote: Debug enabled set to {value}")

                            elif cmd_type == 'tap' and cmd_data:
                                # Execute tap command (only if bot is running and connected)
                                if self.is_running and 'bot' in globals() and bot is not None:
                                    x = cmd_data.get('x')
                                    y = cmd_data.get('y')
                                    if x is not None and y is not None:
                                        bot.tap(x, y)
                                        self.log(f"Remote: Tap executed at ({x}, {y})")

                            elif cmd_type == 'swipe' and cmd_data:
                                # Execute swipe command (only if bot is running and connected)
                                if self.is_running and 'bot' in globals() and bot is not None:
                                    x1 = cmd_data.get('x1')
                                    y1 = cmd_data.get('y1')
                                    x2 = cmd_data.get('x2')
                                    y2 = cmd_data.get('y2')
                                    if all(v is not None for v in [x1, y1, x2, y2]):
                                        bot.swipe(x1, y1, x2, y2)
                                        self.log(f"Remote: Swipe executed from ({x1}, {y1}) to ({x2}, {y2})")

                            elif cmd_type == 'stop_bot':
                                # Stop the bot
                                if self.is_running:
                                    self.root.after(0, self.toggle_bot)
                                    self.log("Remote: Stop command received")

                            elif cmd_type == 'start_bot':
                                # Start the bot
                                if not self.is_running:
                                    self.root.after(0, self.toggle_bot)
                                    self.log("Remote: Start command received")

                            elif cmd_type == 'assist_shortcut' and cmd_data:
                                # Execute assist shortcuts (only if bot is running)
                                if self.is_running:
                                    shortcut_name = cmd_data.get('name')
                                    if shortcut_name == 'min_fans':
                                        self.root.after(0, self.trigger_assist_min_fans)
                                        self.log("Remote: Min Fans shortcut triggered")
                                    elif shortcut_name == 'max_fans':
                                        self.root.after(0, self.trigger_assist_max_fans)
                                        self.log("Remote: Max Fans shortcut triggered")

                            # Mark command as processed
                            self.state_manager.mark_command_processed(cmd['id'])

                except Exception:
                    # Silently ignore errors to prevent disrupting bot operation
                    pass

                # Check for commands every 0.5 seconds
                time.sleep(0.5)

        self.remote_monitoring_thread = threading.Thread(
            target=remote_monitor_loop,
            daemon=True,
            name=f"RemoteMonitor-{self.username}"
        )
        self.remote_monitoring_thread.start()

    def stop_remote_monitoring(self):
        """Stop the remote monitoring thread"""
        self.remote_monitoring_running = False
        if self.remote_monitoring_thread:
            self.remote_monitoring_thread.join(timeout=1.0)

    def toggle_screenshot(self):
        """Toggle screenshot capture on/off

        Two modes based on screenshot_interval setting:
        - Interval = 0: Takes single screenshot and opens in MS Paint
        - Interval > 0: Continuously captures screenshots at specified interval

        Screenshots are saved to screenshots/ directory with timestamps.
        """
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

    def open_log_viewer(self):
        """Open LogViewer.py with current device and session selected

        Launches the LogViewer application in a separate process, automatically
        selecting the current device and session (if debug mode is active).

        Note:
            - Requires debug mode to be enabled for session tracking
            - Opens in separate window for viewing detailed logs with screenshots
        """
        import subprocess
        import sys

        # Get the path to LogViewer.py
        log_viewer_path = os.path.join(os.path.dirname(__file__), 'LogViewer.py')

        # Launch LogViewer.py with device and session parameters
        # Get current session from database
        current_session = None
        if self.log_db:
            current_session = self.log_db.session_id

        # Build command
        cmd = [sys.executable, log_viewer_path, self.username]
        if current_session:
            cmd.append(str(current_session))

        # Launch as separate process
        subprocess.Popen(cmd)
        self.log(f"Opening Log Viewer for {self.username}...")

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

        Captures and saves a screenshot from the Android device to the screenshots directory.

        Args:
            andy: Android device instance
            user: Username for filename prefix
            screenshot_dir: Directory path where screenshots are saved

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
    """Main bot execution loop with GUI integration

    This is the core bot loop that runs continuously while the bot is active.
    It executes enabled functions in sequence, handles shortcuts, manages cooldowns,
    and processes remote commands.

    Loop behavior:
    1. Check and execute any pending shortcut triggers (highest priority)
    2. Execute all enabled functions in sequence
    3. Run Fix/Recover function if enabled
    4. Update state manager heartbeat
    5. Sleep for configured duration
    6. Repeat

    Args:
        gui: BotGUI instance containing configuration and state

    Note:
        - Pressing Ctrl key during loop skips remaining functions for that iteration
        - BotStoppedException is raised when user clicks Stop button
        - Cooldowns prevent functions from running too frequently
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
        'doStudio': do_studio,
        'doGroup': do_group,
        'doConcert': do_concert,
        'doHeal': do_heal,
        'doCoin': do_coin,
        'doHelp': do_help,
        'doRally': do_rally,
        'doParking': do_parking
    }

    # Functions that should be unchecked after completion
    auto_uncheck = {'doStudio'}

    # Cooldown system - configure cooldowns for functions (in seconds)
    # Set to 0 or omit to disable cooldown for a function
    function_cooldowns = {
        'doGroup': 300,      # 5 minutes
        'doStreet': 0,       # No cooldown (disabled)
        'doStudio': 0,       # No cooldown (disabled)
        'doConcert': 0,      # No cooldown (disabled)
        'doHeal': 0,         # No cooldown (disabled)
        'doCoin': 0,         # No cooldown (disabled)
        'doHelp': 0,         # No cooldown (disabled)
        'doRally': 0,        # No cooldown (disabled)
        'doParking': 0,      # No cooldown (disabled)
    }

    # Track last run time for each function (store in GUI instance)
    gui.last_run_times = {func_name: 0 for func_name in function_map.keys()}

    # Import keyboard library once at start
    import keyboard

    while gui.is_running and bot_running:
        try:
            # Check for shortcut triggers (run immediately, highest priority)
            if gui.shortcut_triggers['assist_min_fans']:
                gui.shortcut_triggers['assist_min_fans'] = False
                gui.update_status("Running", "send_assist - min fans (shortcut)")
                try:
                    send_assist(bot, use_min_fans=True)
                    time.sleep(2)
                    bot.find_and_click("continuemarch")
                except BotStoppedException:
                    gui.log("Stopped during send_assist (min fans) shortcut")
                    raise
                except Exception as e:
                    gui.log(f"ERROR in send_assist (min fans) shortcut: {e}")

            if gui.shortcut_triggers['assist_max_fans']:
                gui.shortcut_triggers['assist_max_fans'] = False
                gui.update_status("Running", "send_assist - max fans (shortcut)")
                try:
                    send_assist(bot, use_min_fans=False)
                    time.sleep(2)
                    bot.find_and_click("continuemarch")
                except BotStoppedException:
                    gui.log("Stopped during send_assist (max fans) shortcut")
                    raise
                except Exception as e:
                    gui.log(f"ERROR in send_assist (max fans) shortcut: {e}")

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
                # Check if Control key is held down before each function
                if keyboard.is_pressed('ctrl'):
                    # Show which function we're about to skip
                    if gui.function_states[func_name].get():
                        gui.update_status("Running", f"CTRL held - skipping {func_name}")
                    break  # Exit the for loop to skip remaining functions

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

            # Call recover function at end of each loop iteration (if Fix is enabled)
            # Check if Control key is held down before Fix
            if keyboard.is_pressed('ctrl'):
                gui.update_status("Running", "CTRL held - skipping Fix")
            elif gui.fix_enabled.get():
                try:
                    gui.update_status("Running", "Fix/Recover")
                    do_recover(bot, user)
                except BotStoppedException:
                    gui.log("Stopped during Fix/Recover")
                    raise
                except Exception as e:
                    gui.log(f"ERROR in Fix/Recover: {e}")

            # Update state manager heartbeat (shows bot is alive)
            try:
                gui.state_manager.heartbeat()
            except Exception as e:
                print(f"Error updating heartbeat: {e}")

            # Capture and update screenshot for web interface monitoring
            try:
                screenshot = bot.screenshot()
                gui.state_manager.update_screenshot(screenshot)
            except Exception as e:
                print(f"Error updating screenshot: {e}")

            # Note: Remote command monitoring now runs in separate thread
            # (see start_remote_monitoring method)

            # Sleep if configured
            if sleep_time > 0:
                # Check if Control is held during sleep
                if keyboard.is_pressed('ctrl'):
                    gui.update_status("Running", "CTRL held - override active")
                else:
                    gui.update_status("Running", f"Sleeping {sleep_time}s")
                time.sleep(sleep_time)

            # Note: Keyboard shortcuts disabled when GUI is present
            # Use the Stop button to stop the bot instead

        except BotStoppedException:
            # User clicked stop button - exit gracefully
            gui.log("Bot stopped by user")
            break
        except Exception as e:
            # Check if bot is still supposed to be running before continuing
            if not gui.is_running or not bot_running:
                gui.log(f"ERROR during shutdown: {e}")
                break

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
    """Main entry point - launches the GUI and bot

    Parses command line arguments, creates the GUI window, and auto-starts the bot.

    Usage:
        python ApexGirlBot.py <username>

    Args:
        username: Device username from config.json (passed as sys.argv[1])

    Note:
        - Bot auto-starts 100ms after GUI initialization
        - GUI windows are positioned based on device order in config.json
        - Each device gets its own independent GUI window
    """
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
    gui.log("Auto-starting bot...")

    # Auto-start the bot after GUI initializes (100ms delay)
    gui_root.after(100, gui.toggle_bot)

    gui_root.mainloop()


if __name__ == "__main__":
    main()
