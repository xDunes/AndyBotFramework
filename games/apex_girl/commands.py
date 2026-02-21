"""
ApexGirl Command Handlers - Triggered by command buttons

This module contains command handlers for ApexGirl.
Commands are triggered by buttons in the GUI/web interface and execute immediately.

Command naming convention:
- Config uses snake_case IDs: "min_fans", "max_fans"
- Python uses handle_ prefix: "handle_min_fans", "handle_max_fans"

All command handlers take (bot, gui) as standard parameters.
"""

import time

# Import game functions for reuse
from . import functions as game_functions


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_min_fans(bot, _gui):
    """Handle min_fans command - run send_assist function with min fans setting

    Args:
        bot: BOT instance for game interactions
        _gui: BotGUI instance (unused, required by command handler interface)
    """
    bot.log("Min Fans command triggered")
    game_functions.send_assist(bot, use_min_fans=True)
    time.sleep(2)
    bot.find_and_click("continuemarch")


def handle_max_fans(bot, _gui):
    """Handle max_fans command - run send_assist function with max fans setting

    Args:
        bot: BOT instance for game interactions
        _gui: BotGUI instance (unused, required by command handler interface)
    """
    bot.log("Max Fans command triggered")
    game_functions.send_assist(bot, use_min_fans=False)
    time.sleep(2)
    bot.find_and_click("continuemarch")
