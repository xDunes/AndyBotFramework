"""
ApexGirl Game Functions - Headless game-specific implementations

This module contains all game-specific functions for ApexGirl.
Functions are pure implementations with no GUI dependencies.

Function naming convention:
- Config uses camelCase: "doConcert", "doRally"
- Python uses snake_case: "do_concert", "do_rally"

All functions take (bot, device) as standard parameters.
Some functions have additional parameters (e.g., do_studio has 'stop').
"""

import time
import random
import cv2 as cv
import numpy as np
import pytesseract

# Import core utilities
from core.ocr import (
    extract_ratio_from_image,
    RATIO_PATTERN,
    NUMBER_SLASH_PATTERN,
    LEVEL_PATTERN
)
from core.utils import log

# Rate limit tracking for maintenance-confirm
_last_maintenance_confirm_time = 0


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def wait_and_click(bot, needle_name, max_attempts=100, delay=0.1, accuracy=0.99):
    """Wait for a needle to appear and click it

    Args:
        bot: Bot instance
        needle_name: Name of needle image to find and click
        max_attempts: Maximum number of attempts (default: 100)
        delay: Delay between attempts in seconds (default: 0.1)
        accuracy: Match accuracy threshold (default: 0.99)

    Returns:
        bool: True if needle was found and clicked, False if max_attempts reached
    """
    for _ in range(max_attempts):
        if bot.find_and_click(needle_name, tap=True, accuracy=accuracy):
            return True
        time.sleep(delay)
    return False


def get_active_cars(bot):
    """Get the count of active rally cars using OCR on car status area

    Returns:
        dict: {'used': int, 'of': int} representing active/total cars
    """
    bot.find_and_click('x')
    sc = bot.screenshot()
    crop = sc[354:371, 1:35]

    if not bot.find_and_click('nocarssent', screenshot=crop, tap=False):
        return {"used": -2, "of": 3}

    sc = bot.screenshot()
    crop = sc[354:371, 35:70]

    white_threshold = 200
    gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)
    _, white_mask = cv.threshold(gray, white_threshold, 255, cv.THRESH_BINARY)
    resized = cv.resize(white_mask, None, fx=6, fy=6, interpolation=cv.INTER_CUBIC)
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv.morphologyEx(resized, cv.MORPH_OPEN, kernel, iterations=1)
    cleaned = cv.morphologyEx(cleaned, cv.MORPH_CLOSE, kernel, iterations=1)
    processed = cv.bitwise_not(cleaned)

    text = pytesseract.image_to_string(
        processed,
        config='--psm 7 -c tessedit_char_whitelist=0123456789/'
    ).strip()

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
    """Get the count of studio records using OCR"""
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
    """Adjust the level selector UI to match target level"""
    if target == -1:
        return

    was_level_adjusted = True
    level_adjust_count = 0
    max_level_adjustments = 100

    while was_level_adjusted and level_adjust_count < max_level_adjustments:
        was_level_adjusted = False

        if target != 0:
            sc = bot.screenshot()
            crop = sc[830:850, 0:540]

            white_threshold = np.array([255, 255, 255, 255])
            tolerance = 40
            mask = np.all(crop >= white_threshold - np.array([tolerance, tolerance, tolerance, 0]), axis=-1)
            processed_image = np.zeros_like(crop)
            processed_image[mask] = white_threshold

            text = pytesseract.image_to_string(
                bot.prepare_image_for_ocr(processed_image),
                config='--psm 7 -c tessedit_char_whitelist="Levl1234567890'
            )
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

    if level_adjust_count >= max_level_adjustments:
        log(f"WARNING: Reached max level adjustment limit ({max_level_adjustments})")


# ============================================================================
# GAME ACTION FUNCTIONS - CONCERTS & EVENTS
# ============================================================================

def do_concert(bot, device):
    """Send cars to concerts until all are sent or limit reached"""
    _ = device
    log("do_concert() started")

    if not bot.find_and_click("screen-map", accuracy=0.99, tap=False) and not bot.find_and_click("screen-main", accuracy=0.99, tap=False):
        log("ERROR: Not on map or main screen - exiting")
        return

    bot.find_and_click("screen-main")
    time.sleep(1)

    counter = 0
    max_concert_loops = 10
    log(f"Starting concert loop (max {max_concert_loops} iterations)")

    while counter < max_concert_loops:
        counter += 1
        result = get_active_cars(bot)
        log(f'Cars: {result["used"]}/{result["of"]}')

        # Check if all cars are already sent
        if result["used"] >= result["of"]:
            log("All cars already sent - exiting concert loop")
            break

        if result["used"] < result["of"]:
            if bot.find_and_click('outofenergy', tap=False, accuracy=0.99):
                log("Out of energy - stopping concert runs")
                if hasattr(bot, 'gui') and bot.gui:
                    bot.gui.function_states['doConcert'].set(False)
                    bot.gui.root.after(0, bot.gui._update_full_state)
                return

            sc = bot.screenshot()
            crop = sc[350:370, 1:35]

            if not bot.find_and_click('nocarssent', screenshot=crop, tap=False, accuracy=0.97):
                bot.tap(115, 790)
                time.sleep(0.5)
                bot.tap(115, 790)
                time.sleep(1)
                bot.tap(95, 580)
                time.sleep(0.5)

                if not bot.find_and_click("search-target", tap=True, accuracy=0.92):
                    continue
                time.sleep(3)
            else:
                bot.tap(270, 460)

            pause = random.randint(1, 100) / 100
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)
            time.sleep(1)

            loop_count = 0
            while bot.find_and_click("perform", tap=True, accuracy=0.99, click_delay=1):
                loop_count += 1
                if loop_count > 20:
                    break
                pause = random.randint(50, 100) / 100
                time.sleep(pause)

            time.sleep(1)

            loop_count = 0
            while bot.find_and_click("driveto", tap=True, accuracy=0.99, click_delay=1, offset_x=offset_x, offset_y=offset_y):
                loop_count += 1
                if loop_count > 20:
                    break
                time.sleep(pause)

                if bot.find_and_click("teleportx", tap=True, accuracy=0.99):
                    time.sleep(0.5)
                    bot.tap(500, 830)
                    time.sleep(0.3)
                    bot.tap(500, 830)
                    break

                pause = random.randint(1, 100) / 100
        else:
            break

    log("Concert loop completed - checking if cars need to return")
    car_wait_counter = 0
    max_car_wait = 300

    while car_wait_counter < max_car_wait:
        # Check car status every 5 seconds to reduce spam
        if car_wait_counter % 5 == 0:
            result = get_active_cars(bot)
            if result["used"] == -2:
                log("All cars returned (no cars out)")
                break

        if car_wait_counter % 30 == 0:  # Log progress every 30 seconds
            log(f"Waiting for cars to return... ({car_wait_counter}/{max_car_wait}s)")

        time.sleep(1)
        car_wait_counter += 1

    if car_wait_counter >= max_car_wait:
        log("WARNING: Timeout waiting for cars to return (5 minutes)")
    elif car_wait_counter > 0:
        log(f"Cars returned after {car_wait_counter} seconds")

    log("do_concert() completed")


def do_rally(bot, device):
    """Join rally if cars are available"""
    _ = device
    if not bot.find_and_click('rallyavailable', tap=False) and not bot.find_and_click('dangerrally', tap=False) and not bot.find_and_click('rallyradiodanger') and not bot.find_and_click('rallynormalrally'):
        return

    result = get_active_cars(bot)
    log(f'Rally Cars: {result["used"]}/{result["of"]}')

    if result["used"] >= result["of"]:
        return

    if bot.find_and_click('rallyavailable') or bot.find_and_click('dangerrally') or bot.find_and_click('rallyradiodanger') or bot.find_and_click('rallynormalrally'):
        counter = 0
        while not bot.find_and_click('rallyjoin') and not bot.find_and_click('rallyradiojoin') and counter <= 20:
            counter += 1
            time.sleep(0.5)
            if counter > 20:
                bot.find_and_click('rallyback')
                return

        offset_x = random.randint(1, 30)
        offset_y = random.randint(1, 35)
        counter2 = 0
        while not bot.find_and_click("driveto", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            counter2 += 1
            bot.find_and_click('rallyjoin')
            time.sleep(0.1)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)
            if counter2 > 30:
                bot.find_and_click('rallyback')
                return


# ============================================================================
# GAME ACTION FUNCTIONS - STUDIO & RECORDING
# ============================================================================

def do_studio(bot, device, stop=6):
    """Record albums in studio until reaching stop threshold

    Returns:
        bool: True if should uncheck (stop threshold reached), False otherwise
    """
    _ = device
    if not bot.find_and_click("screen-map", accuracy=0.99, tap=False) and not bot.find_and_click("screen-main", accuracy=0.99, tap=False):
        return False

    bot.find_and_click("screen-map")
    time.sleep(1)
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

    record_count_attempts = 0
    while result["used"] > 6 and record_count_attempts < 20:
        time.sleep(0.1)
        result = get_record_count(bot)
        record_count_attempts += 1

    if record_count_attempts >= 20:
        log(f"WARNING: Record count stuck at {result['used']}/6 - treating as 6/6")
        result = {'used': 6, 'of': 6}

    log(f'Records: {result["used"]}/{result["of"]}')

    if bot.find_and_click("record6", tap=False, accuracy=0.92) or result["used"] >= stop:
        if result["used"] >= stop:
            log(f"Studio at {result['used']}/{result['of']} (target: {stop}) - Auto-unchecking")
            return True
        return False

    if result["used"] < result["of"]:
        if not wait_and_click(bot, "studio", delay=0.5):
            log("WARNING: Studio button not found after 100 attempts")
            return False
        time.sleep(1)

        bot.find_and_click("askhelp", tap=True, accuracy=0.90)
        time.sleep(1)

        # Studio recording sequence - each step must complete before next
        steps = [
            ("record", 0.99),
            ("select", 0.99),
            ("autoassign", 0.99),
        ]
        for needle, acc in steps:
            if not wait_and_click(bot, needle, accuracy=acc):
                return False

        time.sleep(1)
        if not wait_and_click(bot, "start", accuracy=0.92):
            return False
        time.sleep(1)

        # Skip and claim sequence
        if not wait_and_click(bot, "skip"):
            return False
        time.sleep(1)
        if not wait_and_click(bot, "skip", accuracy=0.92):
            return False
        time.sleep(1)
        if not wait_and_click(bot, "claim"):
            return False
        time.sleep(1)

    return False


# ============================================================================
# GAME ACTION FUNCTIONS - GROUP ACTIVITIES
# ============================================================================

def assist(bot, use_min_fans=True):
    """Assist one group building by selecting and driving a character"""
    fan_mode = "min" if use_min_fans else "max"
    log(f"assist() started - using {fan_mode} fans")

    log(f"Checking current fan mode selection")
    min_visible = bot.find_and_click("min", tap=False)
    max_visible = bot.find_and_click("max", tap=False)

    if use_min_fans:
        if min_visible:
            log("Min button visible - clicking to select min fans")
            bot.find_and_click("min")
        elif max_visible:
            log("Max button visible - min fans already selected")
        else:
            counter = 0
            while not bot.find_and_click("min") and counter <= 5:
                counter += 1
                time.sleep(1)
    else:
        if max_visible:
            log("Max button visible - clicking to select max fans")
            bot.find_and_click("max")
        elif min_visible:
            log("Min button visible - max fans already selected")
        else:
            counter = 0
            while not bot.find_and_click("max") and counter <= 5:
                counter += 1
                time.sleep(1)

    log("Looking for 'settings' button")
    counter = 0
    while not bot.find_and_click("settings") and counter <= 10:
        counter += 1
        time.sleep(0.1)

    log("Clicking 'settings' until dialog opens")
    settings_timeout = 0
    max_settings_timeout = 300

    while (bot.find_and_click("settings") or bot.find_and_click("brokensettings", offset_y=5)) and settings_timeout < max_settings_timeout:
        time.sleep(0.1)
        settings_timeout += 1

    time.sleep(2)
    log("Settings dialog opened")

    offset_x = random.randint(1, 15)
    offset_y = random.randint(1, 10)

    log("Unchecking all character filters")
    check_count = 0
    max_uncheck = 10

    while bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y) and check_count < max_uncheck:
        check_count += 1
        time.sleep(0.1)
        offset_x = random.randint(1, 15)
        offset_y = random.randint(1, 10)

    time.sleep(1)
    bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y)
    time.sleep(1)
    bot.find_and_click("checked", accuracy=0.92, offset_x=offset_x, offset_y=offset_y)

    log("Swiping to reveal SSR characters")
    bot.swipe(270, 630, 270, -700)

    time.sleep(3)
    log("Selecting random SSR character")
    bot.find_and_click("randomssr")

    time.sleep(0.5)
    log("Looking for 'settingsdriveto' button")
    counter = 0
    while not bot.find_and_click("settingsdriveto"):
        counter += 1
        if counter >= 10:
            log("ERROR: 'settingsdriveto' not found")
            return
        time.sleep(0.1)

    time.sleep(2)
    log("Clicking 'continuemarch'")
    bot.find_and_click("continuemarch")


def send_assist(bot, use_min_fans=True):
    """Send assistance to group buildings with pre-processing steps"""
    fan_type = "minimum" if use_min_fans else "maximum"
    log(f"send_assist started with {fan_type} fans")

    in_settings = bot.find_and_click("settingswindow", accuracy=0.99, tap=False)
    in_assist = bot.find_and_click("sendassist", accuracy=0.99, tap=False)
    in_join = bot.find_and_click("sendjoin", accuracy=0.99, tap=False)

    if not (in_settings or in_assist or in_join):
        log("Not in settings/assist/join screen - tapping building location")
        bot.tap(270, 470)
        time.sleep(1.5)

        if bot.find_and_click("sendaccelerate", accuracy=0.99, tap=True):
            log("Acceleration popup found - clicked")
            time.sleep(1)

        log("Looking for assist and join buttons")
        clicked_assist = False
        clicked_join = False
        loop_counter = 0

        while not (clicked_assist and clicked_join):
            loop_counter += 1
            if loop_counter > 20:
                log("WARNING: Exceeded max loops waiting for buttons")
                break

            if not clicked_assist and bot.find_and_click("sendassist", accuracy=0.99, tap=False):
                assist_click_counter = 0
                while bot.find_and_click("sendassist", accuracy=0.99) and assist_click_counter < 100:
                    time.sleep(0.1)
                    assist_click_counter += 1
                clicked_assist = True
                log("Successfully clicked 'assist' button")

            if not clicked_join and bot.find_and_click("sendjoin", accuracy=0.99, tap=False):
                join_click_counter = 0
                while bot.find_and_click("sendjoin", accuracy=0.99) and join_click_counter < 100:
                    time.sleep(1)
                    join_click_counter += 1
                clicked_join = True
                log("Successfully clicked 'join' button")

            time.sleep(0.1)

        time.sleep(2)

    log(f"Calling assist() with use_min_fans={use_min_fans}")
    assist(bot, use_min_fans=use_min_fans)
    log(f"send_assist completed for {fan_type} fans")


def do_recover(bot, device):
    """Perform recovery and screen validation operations"""
    global _last_maintenance_confirm_time
    _ = device

    screenshot = bot.screenshot()
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False, sqdiff=True, screenshot=screenshot)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False, sqdiff=True, screenshot=screenshot)

    if on_map or on_main:
        if bot.find_and_click("fixmapassist", accuracy=0.99, tap=False, screenshot=screenshot):
            bot.tap(250, 880)
            log("Recovery: Clicked away from Assist")
        if bot.find_and_click("fixratingpopup", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Exiting Rating Pop-up")
        return

    log("Recovery: Not on map/main screen - attempting fixes")

    recovery_attempts = 0
    max_attempts = 20

    while not (on_map or on_main) and recovery_attempts < max_attempts:
        recovery_attempts += 1
        screenshot = bot.screenshot()

        if bot.gui and hasattr(bot.gui, 'fix_enabled') and not bot.gui.fix_enabled.get():
            log("Recovery: Fix checkbox disabled - exiting")
            return

        if bot.find_and_click("fixgroupgiftx", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Closed group gift screen")
        if bot.find_and_click("fixdecree", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Closed Decree")
        if bot.find_and_click("fixgroupback", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked group back button")
        if bot.find_and_click("fixmainad", screenshot=screenshot):
            log("Recovery: Closed ad popup")
        if bot.find_and_click("fixgrouprallyback", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked rally back button")
        if bot.find_and_click("fixgameclosed", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked open game")
        if bot.find_and_click("fixcellphoneback", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked Back on cellphone")
        if bot.find_and_click("skip", tap=True, accuracy=0.92, screenshot=screenshot):
            log("Recovery: Clicked skip in studio")
        if bot.find_and_click("claim", tap=True, accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked claim in studio")
        if bot.find_and_click("fixlater", tap=True, accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked Later")
        if bot.find_and_click("maintenanace-downloadnow", tap=True, accuracy=0.99, screenshot=screenshot):
            log("Recovery: Clicked Maintenance Download Now")

        current_time = time.time()
        if current_time - _last_maintenance_confirm_time >= 60:
            if bot.find_and_click("maintenanace-confirm", tap=True, accuracy=0.98, screenshot=screenshot):
                log("Recovery: Clicked Recovery Confirm")
                _last_maintenance_confirm_time = current_time

        if bot.find_and_click("fixceocard", accuracy=0.99, tap=False, screenshot=screenshot) or bot.find_and_click('settingswindow', accuracy=0.99, tap=False, screenshot=screenshot) or bot.find_and_click('fixdecree', accuracy=0.99, tap=False, screenshot=screenshot):
            if bot.find_and_click("fixceocardsettings", accuracy=0.99, screenshot=screenshot):
                time.sleep(1)
            bot.tap(450, 855)
            log("Recovery: Clicked away on CEO card or Send card window")
        if bot.find_and_click("fixgenericback", accuracy=0.91, screenshot=screenshot):
            log("Recovery: Clicked Back")

        if bot.find_and_click("fixmaintenanceconfirm", accuracy=0.99, screenshot=screenshot):
            log("Recovery: Maintenance detected - waiting 5 minutes")
            for _ in range(30):
                time.sleep(10)
                if bot.gui and hasattr(bot.gui, 'fix_enabled') and not bot.gui.fix_enabled.get():
                    log("Recovery: Fix checkbox disabled during wait - exiting")
                    return

        time.sleep(0.1)

        screenshot = bot.screenshot()
        on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False, screenshot=screenshot)
        on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False, screenshot=screenshot)

    if on_map or on_main:
        log(f"Recovery: Successfully returned (attempts: {recovery_attempts})")
    else:
        log(f"WARNING: Recovery failed after {max_attempts} attempts")


def do_group(bot, device):
    """Perform comprehensive group-related activities

    Returns:
        False if function aborts early (cooldown will NOT start)
        None on normal completion (cooldown will start)
    """
    _ = device
    log("do_group started")

    # Phase 1: Navigation
    log("Phase 1: Verifying screen state")
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if not (on_map or on_main):
        log("ERROR: Not on map or main screen - aborting")
        return False

    log("Navigating to group menu")
    loop_count = 0
    while bot.find_and_click("group", accuracy=0.99) or bot.find_and_click("help", accuracy=0.99):
        loop_count += 1
        if loop_count > 20:
            break
        time.sleep(0.2)

    log("Waiting for group menu to load")
    loop_count = 0
    while not bot.find_and_click("gift",tap=False) and bot.find_and_click("group", accuracy=0.99):
        loop_count += 1
        if loop_count > 20:
            log("ERROR: Group menu failed to load")
            return False
        time.sleep(0.3)

    counter = 0
    while not bot.find_and_click("groupfullyloaded", tap=False,accuracy=0.8):
        counter += 1
        time.sleep(0.2)
        if counter > 10:
            log("ERROR: Group screen failed to load")
            return False

    # Phase 2: Gifts
    log("Phase 2: Processing gifts")
    offset_x = random.randint(1, 5)
    offset_y = random.randint(1, 5)
    gift_clicks = 0
    while bot.find_and_click("gift", offset_x=offset_x, offset_y=offset_y, accuracy=0.98):
        gift_clicks += 1
        if gift_clicks > 20:
            break
        time.sleep(0.3)

    time.sleep(1)

    loop_count = 0
    while not bot.find_and_click("giftscreen", accuracy=0.99, tap=False) and bot.find_and_click("gift"):
        loop_count += 1
        if loop_count > 20:
            break
        time.sleep(0.3)

    if bot.find_and_click("giftcollect"):
        log("Collecting gifts")
        time.sleep(1)
        bot.tap(250, 880)
        time.sleep(2)

    if bot.find_and_click("claimall"):
        log("Claiming all rewards")
        time.sleep(1)
        bot.tap(250, 880)
        time.sleep(1)
        bot.tap(250, 880)
        time.sleep(2)

    if bot.find_and_click("giftscreenx", accuracy=0.99):
        log("Gift screen closed")

    # Phase 3: Investments
    log("Phase 3: Processing investments")
    counter = 0
    while not bot.find_and_click("plan", tap=False):
        counter += 1
        bot.tap(250, 880)
        time.sleep(0.5)
        if counter == 10:
            log("ERROR: Plan button not found")
            return False

    bot.find_and_click("plan")
    time.sleep(1)

    invest_count = 0
    loop_count = 0
    while not bot.find_and_click("grouppaidinvest", accuracy=0.99, tap=False):
        loop_count += 1
        if loop_count > 20:
            break
        if bot.find_and_click("invest", accuracy=0.99):
            invest_count += 1
        time.sleep(0.2)
    log(f"Made {invest_count} investments")

    # Phase 4: Zone Activities
    log("Phase 4: Processing zone activities")
    loop_count = 0
    while not bot.find_and_click("zone", accuracy=0.99):
        loop_count += 1
        if loop_count > 20:
            log("ERROR: Zone button not found")
            return False
        time.sleep(0.2)
        bot.tap(250, 880)
        bot.find_and_click("rallyback")

    offset_x = random.randint(1, 5)
    offset_y = random.randint(1, 5)
    zone_clicks = 0
    while bot.find_and_click("zone", offset_x=offset_x, offset_y=offset_y, accuracy=0.98):
        zone_clicks += 1
        if zone_clicks > 20:
            break
        time.sleep(0.5)

    time.sleep(1.5)

    if bot.find_and_click("groupclaim"):
        log("Zone rewards claimed")

    time.sleep(0.3)

    # Phase 5: Assist Buildings
    log("Phase 5: Looking for buildings to assist")
    counter = 0
    offset_x = random.randint(1, 30)
    offset_y = random.randint(1, 35)
    buildings_found = True

    while not bot.find_and_click("assist", accuracy=0.92, offset_x=offset_x, offset_y=offset_y) and counter <= 10:
        if bot.find_and_click("groupzonenormal", accuracy=0.95, tap=False):
            log("Zone in normal state - no buildings need assistance")
            counter = 10
            buildings_found = False
        counter += 1
        time.sleep(0.1)
        bot.swipe(270, 490, 400, 490)

    if buildings_found and counter <= 6:
        log(f"Building found requiring assistance")
        bot.find_and_click("assist")
        time.sleep(2)
        assist(bot, use_min_fans=True)
    elif buildings_found:
        offset_x = random.randint(1, 30)
        offset_y = random.randint(1, 35)
        back_count = 0
        while bot.find_and_click("back", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            back_count += 1
            if back_count > 20:
                break
            time.sleep(1)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)
    else:
        back_count = 0
        while bot.find_and_click("back", accuracy=0.92, offset_x=offset_x, offset_y=offset_y):
            back_count += 1
            if back_count > 20:
                break
            time.sleep(1)
            offset_x = random.randint(1, 30)
            offset_y = random.randint(1, 35)

    if not buildings_found:
        # Zone is in normal state - all buildings complete, cooldown will start
        log("do_group completed - zone normal, cooldown will start")
        return None  # Cooldown starts (normal completion)
    else:
        # Building was assisted or not found - don't start cooldown
        log("do_group completed - no normal state, cooldown will NOT start")
        return False  # Cooldown does NOT start


# ============================================================================
# GAME ACTION FUNCTIONS - SIMPLE ACTIONS
# ============================================================================

def do_street(bot, device):
    """Perform street-related activities"""
    _ = device

    if not bot.find_and_click("street"):
        log("Street button not found - skipping")
        return
    time.sleep(2)

    counter = 0
    while not bot.find_and_click("streetback", tap=False) and not bot.find_and_click("offlineincomeclaim"):
        time.sleep(0.1)
        counter += 1
        if counter > 100:
            log("Street screen load timeout")
            return

    counter = 0
    while not bot.find_and_click("streetback", tap=False):
        time.sleep(0.1)
        counter += 1
        if counter > 100:
            log("Street back button not found")
            return

    bot.find_and_click("tokyo2street", accuracy=0.99)
    time.sleep(2)

    if bot.find_and_click("streetxpready", accuracy=0.99):
        loop_count = 0
        while not bot.find_and_click("streetxpreadyselected", accuracy=0.99):
            loop_count += 1
            if loop_count > 20:
                break
            time.sleep(0.1)
            bot.find_and_click("streetback", tap=False)

        time.sleep(1)
        bot.find_and_click("collectxp")
        time.sleep(2)
        bot.tap(250, 880)
        time.sleep(1)
        bot.tap(250, 880)
        time.sleep(1)
        bot.find_and_click("tokyo2street")
        time.sleep(2)

    if bot.find_and_click("demoassistant", accuracy=0.99):
        time.sleep(1)
        if bot.find_and_click("demosready", accuracy=0.99):
            time.sleep(2)
            loop_count = 0
            while bot.find_and_click("democomplete"):
                loop_count += 1
                if loop_count > 20:
                    break
                time.sleep(0.2)
                inner_loop_count = 0
                while not bot.find_and_click("tapscreentocontinue"):
                    inner_loop_count += 1
                    if inner_loop_count > 20:
                        break
                    time.sleep(0.1)
                inner_loop_count = 0
                while bot.find_and_click("tapscreentocontinue"):
                    inner_loop_count += 1
                    if inner_loop_count > 20:
                        break
                    time.sleep(0.1)
                time.sleep(0.5)

            loop_count = 0
            while bot.find_and_click("back"):
                loop_count += 1
                if loop_count > 20:
                    break
                time.sleep(0.1)

    loop_count = 0
    while bot.find_and_click("streetback"):
        loop_count += 1
        if loop_count > 20:
            break
        time.sleep(0.1)

    if hasattr(bot, 'gui') and bot.gui:
        bot.gui.function_states['doStreet'].set(False)
        bot.gui.root.after(0, bot.gui._update_full_state)


def do_help(bot, device):
    """Click help button"""
    _ = device
    try:
        if not bot.find_and_click("help", accuracy=0.99):
            bot.log("WARNING: Help button not found")
        time.sleep(0.5)
    except Exception as e:
        bot.log(f"ERROR in do_help: {e}")
        raise


def do_heal(bot, device):
    """Heal assist - find and click heal assist button"""
    _ = device
    if not bot.find_and_click("healassist", accuracy=0.91):
        bot.log("Dragging to find heal assist")
        bot.swipe(230, 830, 230, 700)
        time.sleep(3)
    time.sleep(0.5)


def do_coin(bot, device):
    """Check if coin is ready and collect it"""
    _ = device
    if bot.find_and_click("coinReady", tap=False, accuracy=0.99):
        bot.find_and_click("coin")


def do_parking(bot, device):
    """Perform parking-related activities"""
    _ = device

    log("Phase 1: Verifying screen state")
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if not (on_map or on_main):
        log("ERROR: Not on map or main screen - aborting")
        return

    if on_map:
        bot.find_and_click('screen-map')
    time.sleep(0.3)

    first_check = bot.find_all('main-parking-activespot', accuracy=0.99, search_region=(10, 570, 85, 20))
    time.sleep(0.3)
    second_check = bot.find_all('main-parking-activespot', accuracy=0.99, search_region=(10, 570, 85, 20))

    if first_check['count'] == 6 and second_check['count'] == 6:
        log("Parking - All parking spots are currently active!")
        return
    else:
        log(f'First: {first_check}')
        log(f'Second: {second_check}')
        bot.find_and_click('main-parking-button')
        time.sleep(2)
        log(bot.find_all('parking-main-claim'))

        loop_count = 0
        while bot.find_and_click('parking-main-claim'):
            loop_count += 1
            if loop_count > 20:
                break
            inner_loop_count = 0
            while not bot.find_and_click('parking-main-coin', accuracy=0.99, tap=False):
                inner_loop_count += 1
                if inner_loop_count > 20:
                    break
                time.sleep(0.1)

            inner_loop_count = 0
            while bot.find_and_click('parking-main-coin', tap=False):
                loop_count += 1
                if loop_count > 20:
                    break
                bot.tap(420, 90)
                time.sleep(1)

            time.sleep(1)
        return
        bot.swipe(270, 630, 270, -700)
        if bot.find_and_click('parking-main-gardencarpark'):
            time.sleep(2)

        for counter in range(6):
            bot.find_and_click('parking-lot-findspot')
            time.sleep(2)
        else:
            return
        log("Finished Parking!")


def do_gig(bot, device):
    """Perform gig activities"""
    _ = device

    log("Phase 1: Verifying screen state")
    on_map = bot.find_and_click("screen-map", accuracy=0.99, tap=False)
    on_main = bot.find_and_click("screen-main", accuracy=0.99, tap=False)

    if not (on_map or on_main):
        log("ERROR: Not on map or main screen - aborting")
        return

    if on_main:
        bot.find_and_click('screen-main')
        time.sleep(1)

    loop_count = 0
    while bot.find_and_click('map-agent-collections'):
        loop_count += 1
        if loop_count > 20:
            break
        time.sleep(1)

    time.sleep(1)

    loop_count = 0
    while bot.find_and_click('opportunity-agentgig-unselected'):
        loop_count += 1
        if loop_count > 20:
            break
        time.sleep(1)

    if bot.find_and_click('opportunity-close-rewards'):
        time.sleep(2)

    performed = False
    # Check if we're still on the map screen (gig menu didn't open properly)
    if bot.find_and_click('screen-map', tap=False):
        log("WARNING: Still on map screen - gig menu may not have opened")
        return  # Don't uncheck - this is a navigation issue, not "no gigs available"
    elif (bot.find_and_click('opportunity-red-target', search_region=(0, 160, 540, 510), accuracy=0.98) or
          bot.find_and_click('opportunity-yellow-target', search_region=(0, 160, 540, 510), accuracy=0.98) or
          bot.find_and_click('opportunity-purple-target', search_region=(0, 160, 540, 510), accuracy=0.98) or
          bot.find_and_click('opportunity-blue-target', search_region=(0, 160, 540, 510), accuracy=0.98)):
        performed = True
        time.sleep(1)
        if bot.find_and_click('opportunity-driving'):
            time.sleep(1)
            bot.tap(0, 160)
            time.sleep(1)
            bot.find_and_click('fixgenericback')
            time.sleep(2)
            return
        bot.find_and_click('opportunity-go')
        time.sleep(3)
        bot.find_and_click('map-agent-rob')
        bot.find_and_click('map-agent-send')
        bot.find_and_click('map-agent-perform')
        time.sleep(2)
        bot.find_and_click('driveto')
        time.sleep(2)

    if bot.find_and_click('opportunity-close-rewards'):
        time.sleep(2)
        bot.find_and_click('fixgenericback')
        time.sleep(2)

    if not performed:
        if bot.gui:
            bot.gui.function_states['doGig'].set(False)
            bot.gui.root.after(0, bot.gui._update_full_state)
