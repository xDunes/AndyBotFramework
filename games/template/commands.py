"""
Template Command Handlers - Triggered by command buttons

This module contains command handlers for your game.
Commands are triggered by buttons in the GUI/web interface and execute immediately.

Command naming convention:
- Config uses snake_case IDs: "quick_collect", "boost_all"
- Python uses handle_ prefix: "handle_quick_collect", "handle_boost_all"

All command handlers take (bot, gui) as standard parameters.
"""

import time

# Import core utilities
from core.utils import log


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_example_command(bot, gui):
    """Example command handler

    Commands are triggered by buttons in the GUI, not the automatic loop.
    Use for actions that should run immediately on user request.

    Args:
        bot: BOT instance for game interactions
        gui: BotGUI instance for logging and state access
    """
    _ = gui  # Can be used for gui.log() or accessing gui state
    log("Example command triggered!")

    # Perform immediate action
    # bot.tap(270, 480)

    time.sleep(0.5)
