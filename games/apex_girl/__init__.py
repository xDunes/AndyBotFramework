"""
ApexGirl Game Module

This package contains all game-specific functions for ApexGirl.
Functions are loaded dynamically based on apex_girl.conf function_layout.

Function naming convention:
- Config uses camelCase: "doConcert", "doRally"
- Python uses snake_case: "do_concert", "do_rally"

The entry point converts between these automatically.
"""

from . import functions
