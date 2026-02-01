"""
Template Game Functions

This module contains placeholder bot functions for the template.
Copy and modify these functions to create your own bot.

Function naming convention:
- Use snake_case for function names (e.g., do_hello_world)
- Config.json uses camelCase (e.g., doHelloWorld)
- The framework converts between them automatically

Each function receives:
- bot: BOT instance with image recognition and device control
- device: Device name string for configuration lookups

Optional parameters:
- gui: BotGUI instance for logging and state access
- stop: Integer value from bot_settings (for configurable limits)
"""

import time
from core.utils import log


# ============================================================================
# FIX/RECOVER FUNCTION
# ============================================================================

def do_recover(bot, device):
    """Fix/Recover function - called automatically between bot loop iterations

    This function runs after all enabled functions complete each loop iteration.
    Use it to:
    - Navigate back to a known screen state
    - Close unexpected popups or dialogs
    - Recover from error states

    Args:
        bot: BOT instance for game interactions
        device: Device name for configuration lookups

    Example implementation:
        # Close any popups
        if bot.find_and_click('close_button'):
            time.sleep(0.5)

        # Navigate to home screen
        if not bot.find_and_click('home_icon', tap=False):
            bot.tap(270, 850)  # Tap home position
    """
    _ = device  # Unused in this template
    log("Fix/Recover: Checking game state...")

    # Example: Close any popups by looking for close button
    # if bot.find_and_click('close_popup'):
    #     time.sleep(0.5)

    # Example: Navigate to home screen
    # if not bot.find_and_click('home_screen', tap=False):
    #     bot.tap(270, 850)  # Default home position

    time.sleep(0.5)


# ============================================================================
# EXAMPLE BOT FUNCTIONS
# ============================================================================

def do_hello_world(bot, device):
    """Example function - prints Hello World to log

    This is a simple template function showing the basic structure.
    Replace with your own bot functions.

    Args:
        bot: BOT instance for game interactions
        device: Device name for configuration lookups
    """
    _ = bot, device  # Unused in this example
    log("Hello World!")
    time.sleep(1)


def do_example_task(bot, device):
    """Example task function demonstrating common bot patterns

    Shows how to use bot methods for:
    - Taking screenshots
    - Finding and clicking images
    - Tapping coordinates
    - Logging messages

    Args:
        bot: BOT instance for game interactions
        device: Device name for configuration lookups

    Returns:
        True: Task completed successfully (triggers auto-uncheck if configured)
        False: Task failed/aborted early (cooldown will NOT start)
        None: Task completed normally (cooldown will start)
    """
    _ = device  # Unused in this example

    log("Starting example task...")

    # Take a screenshot
    # screenshot = bot.screenshot()

    # Find and click an image (returns True if found and clicked)
    # if bot.find_and_click('button_image', accuracy=0.95):
    #     log("Button found and clicked")
    #     time.sleep(0.5)

    # Find image without clicking (returns match info or False)
    # if bot.find_and_click('target_image', tap=False):
    #     log("Target found on screen")

    # Example: Return False to prevent cooldown from starting
    # if not bot.find_and_click('required_screen', tap=False):
    #     log("ERROR: Not on required screen - aborting")
    #     return False  # Cooldown will NOT start

    # Tap specific coordinates
    # bot.tap(270, 480)
    # time.sleep(0.3)

    # Swipe gesture
    # bot.swipe(100, 400, 400, 400, duration=300)

    log("Example task completed")
    time.sleep(1)

    # Return True to trigger auto-uncheck (if function is in auto_uncheck list)
    return True


def do_collect_rewards(bot, device):
    """Example collection function with loop pattern

    Demonstrates how to create a function that:
    - Loops until a condition is met
    - Handles multiple possible states
    - Has a safety limit to prevent infinite loops

    Args:
        bot: BOT instance for game interactions
        device: Device name for configuration lookups
    """
    _ = device

    log("Collecting rewards...")

    loop_count = 0
    max_loops = 10

    while loop_count < max_loops:
        loop_count += 1

        # Example: Look for reward to collect
        # if bot.find_and_click('reward_icon'):
        #     log(f"Collected reward {loop_count}")
        #     time.sleep(0.5)
        # else:
        #     log("No more rewards found")
        #     break

        # Placeholder: just simulate work
        time.sleep(0.5)
        break  # Remove this when implementing real logic

    log(f"Reward collection finished after {loop_count} iterations")
