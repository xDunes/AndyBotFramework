"""
GUI Module - Generic tkinter bot interface

This module provides a config-driven GUI for game bots.
The GUI reads all configuration from master.conf and game-specific .conf files.
"""

from .bot_gui import BotGUI

__all__ = ['BotGUI']
