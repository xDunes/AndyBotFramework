# Changelog

All notable changes to the Andy Bot Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version Format

- **MAJOR.MINOR.BUILD** (e.g., 1.2.34)
- **MAJOR**: Breaking changes, major feature overhauls
- **MINOR**: New features, significant improvements (summarizes build changes)
- **BUILD**: Bug fixes, small improvements, refactoring (auto-incremented)

---

## [0.4.0] - 2025-12-16

### Master of Bots Web Interface Improvements

#### Fixed
- **ALL Mode Device Selection Bug** - Fixed issue where selecting a different device in ALL mode would deselect the original device
  - The `updatePreviewSelectedStates()` function now properly syncs the `selected` CSS class with the `selectedPreviews` set
  - When switching devices in ALL mode, all non-active devices now remain selected as expected
  - Users can now properly apply commands to all selected devices without losing selections

#### Changed
- **Removed config.json completely** - All tools now use `master.conf` exclusively
  - `ArrangeWindows.py` updated to read window titles from `master.conf`
  - `getScreenShot.py` updated to use `master.conf` only (removed legacy fallback)
  - Deleted `config.json` file from repository
  - Updated all documentation and docstrings to reference new config system

#### Added
- **apex_girl.example.conf** - Example game configuration file for reference

#### Documentation
- Updated README.md, NEWBOT.md, CHANGELOG.md to remove config.json references
- Updated STATE_MONITORING_README.md with correct `start_bot.py` command examples
- Updated docstrings in `gui/__init__.py`, `gui/bot_gui.py`, `games/apex_girl/__init__.py`, `start_bot.py`

#### Technical Details
- **File Changed**: `web/static/app.js` (lines 412-446)
- Added logic to update `selected` class based on `selectedPreviews` set membership
- Active device now properly has `selected` class removed
- Non-active devices have `selected` class added/removed based on set membership

---

## [0.3.0] - 2025-12-08

### Major Refactoring - Modular Architecture

Complete restructure of the codebase into a clean modular architecture for better maintainability and easier bot creation.

#### Added
- **`start_bot.py`** - Unified bot launcher for all games
  - Replaces game-specific entry points (ApexGirlBot.py, botTemplate.py)
  - Uses argparse for command-line arguments: `-g/--game`, `-d/--device`, `-a/--auto-start`
  - `--list-games` flag to show available games
  - Dynamically loads game modules from `games/` directory
  - Single entry point for all games

- **`core/` directory** - All framework modules now in core package
  - Moved `android.py`, `bot.py`, `ldplayer.py`, `log_database.py`, `state_manager.py` to `core/`
  - Updated all imports to use `core.` prefix
  - Clean `__init__.py` with all public exports

- **`games/*/commands.py`** - Separate command handler modules
  - Command handlers moved out of functions.py into dedicated commands.py
  - `build_command_map()` function for dynamic command mapping
  - `games/apex_girl/commands.py` with handle_min_fans, handle_max_fans
  - `games/template/commands.py` as template for new games

- **`games/template/` directory** - Template for creating new game bots
  - `functions.py` with placeholder examples (`do_hello_world`, `do_example_task`, `do_collect_rewards`)
  - `commands.py` with example command handler
  - `do_recover()` fix/recover function template
  - Comprehensive docstrings explaining each pattern

- **`tools/` directory** - Utility scripts organized
  - Moved `ArrangeWindows.py`, `getScreenShot.py`, `LogViewer.py`, `version.py`, `version_manager.py`
  - Updated `gui/bot_gui.py` to reference new LogViewer location

- **`docs/` directory** - Documentation organized
  - Moved `CHANGELOG.md`, `NEWBOT.md`, `STATE_MONITORING_README.md`
  - Updated all cross-references

- **ADB Command Serialization** - Thread-safe ADB access
  - Added `_adb_locks` dictionary for per-device locks
  - All ADB commands (`capture_screen`, `touch`, `send_text`, `press_enter`, `press_backspace`) now use locks
  - Prevents concurrent ADB commands from different threads (bot loop, screenshot updater, remote monitor)
  - Fixes issue where remote tap commands would queue up and execute in bursts

- **Renamed "Shortcuts" to "Commands"** - Terminology update throughout codebase
  - Config: `shortcuts` → `commands`, `assist_shortcut` → `assist_command`
  - GUI: "Shortcuts" section → "Commands" section
  - Web API: `/api/command/shortcut` → `/api/command/trigger`
  - Code: `shortcut_triggers` → `command_triggers`, `SHORTCUT_HANDLERS` → `COMMAND_HANDLERS`

#### Changed
- **Import paths updated throughout codebase:**
  - `from android import Android` → `from core.android import Android`
  - `from bot import BOT` → `from core.bot import BOT`
  - `from state_manager import StateManager` → `from core.state_manager import StateManager`
  - `from log_database import LogDatabase` → `from core.log_database import LogDatabase`
  - `from ldplayer import LDPlayer` → `from core.ldplayer import LDPlayer`

- **Documentation updated:**
  - README.md completely rewritten with new project structure
  - NEWBOT.md updated for unified start_bot.py launcher
  - Updated all file references and paths

#### Removed
- Deleted `ApexGirlBot.py` - replaced by `start_bot.py -g apex_girl`
- Deleted `botTemplate.py` - replaced by `start_bot.py -g <game>`
- Deleted `tempScreenShot.png` (temporary file)
- Deleted `MODULARIZATION_PLAN.md` (completed)

#### Project Structure
```
Apex-Girl/
├── start_bot.py            # Unified bot launcher for all games
├── master.conf             # Global device settings
├── apex_girl.conf          # Game-specific configuration
├── core/                   # Framework modules
│   ├── android.py          # ADB device communication
│   ├── bot.py              # BOT class
│   ├── bot_loop.py         # Main execution loop
│   ├── config_loader.py    # Config utilities
│   ├── ldplayer.py         # LDPlayer control
│   ├── log_database.py     # Debug logging
│   ├── ocr.py              # OCR utilities
│   ├── state_manager.py    # Web state management
│   └── utils.py            # Shared utilities
├── games/                  # Game-specific modules
│   ├── apex_girl/          # Apex Girl functions & commands
│   └── template/           # Template for new games
├── gui/                    # GUI components
├── web/                    # Web interface
├── tools/                  # Utility scripts
└── docs/                   # Documentation
```

---

## [0.2.0] - 2025-11-16

### Added
- **Web Interface** - Flask-based remote monitoring and control system
  - Real-time bot state monitoring via web browser
  - Remote control capabilities (checkbox toggle, settings adjustment)
  - Screenshot viewing from all devices
  - Multi-device support with "Apply to All" functionality
  - Mobile-friendly responsive design
  - Auto-refresh with configurable intervals (1-60 seconds)
  - REST API for programmatic access
  - SocketIO support for real-time updates
  - Comprehensive documentation in web/README.md
  - Multiple hosting options (local, background, Task Scheduler, ngrok, port forwarding)

- **State Monitoring System** - Centralized multi-bot state tracking
  - SQLite-based shared state database (state/state_monitor.db)
  - Thread-safe operations with class-level locking
  - Real-time state synchronization across bots
  - Remote command queue system
  - Heartbeat mechanism for bot alive detection
  - Screenshot storage with JPEG compression
  - Comprehensive API in state_manager.py
  - Full documentation in STATE_MONITORING_README.md

### Improved
- **Documentation Enhancements** - Comprehensive code documentation overhaul
  - Added 26+ detailed docstrings to ApexGirlBot.py functions
  - Documented all hard-coded coordinates with inline comments
  - Added OCR preprocessing pipeline explanations
  - Enhanced function docstrings with Args, Returns, and Notes sections
  - Documented control key override behavior
  - Added coordinate comments for all tap/swipe operations
  - Improved README.md with web interface section
  - Updated feature list to include remote monitoring

- **Code Quality** - Cleanup and optimization
  - Removed unused discord.py dependency from requirements.txt
  - Verified .gitignore properly excludes config.json
  - Enhanced code comments throughout ApexGirlBot.py
  - Improved maintainability with better function documentation

### Changed
- Updated version badges and references to 0.2.0
- Enhanced README.md Table of Contents to include Web Interface section
- Updated feature descriptions to highlight remote monitoring capabilities

### Technical Details
- Web server runs on Flask with CORS support
- State database supports multiple concurrent bot instances
- Screenshot data JPEG-compressed for performance
- Remote commands processed via polling mechanism
- Full backward compatibility with existing bots

---

## [0.1.3] - 2025-11-11

### Added
- **Control key override** - Hold Ctrl key during bot loop to skip function execution
  - Shows "CTRL held - skipping {function_name}" status during override
  - Works during both function execution and sleep periods
  - Allows manual intervention without stopping the bot
  - Synced to botTemplate.py for consistency across all bots

### Changed
- **do_recover improvements** - Enhanced recovery function with additional fix cases
  - Added fixceocard detection and handling
  - Added fixgenericback for generic back button detection
  - Added fixmapassist to click away from assist popup
  - Improved navigation reliability when bot gets stuck
- **Rally improvements** - Enhanced rally detection and joining
  - Added dangerrally image detection for danger rallies
  - Improved rally join reliability with better counter logic
  - Added back button handling when rally join fails
- **botTemplate.py updates** - Synced Control key override feature from ApexGirlBot

### Technical Details
- **Control Key Implementation**
  - Uses `keyboard.is_pressed('ctrl')` to detect Ctrl key state
  - Checks before each function and during sleep
  - Displays override status in GUI
  - Breaks out of function loop when Ctrl is held
- **Rally Counter Logic**
  - Maximum 20 attempts to find rally join button
  - Maximum 30 attempts to find drive button after joining
  - Auto-backs out if counters exceeded
- **Recovery Function Enhancements**
  - Maximum 20 recovery attempts to prevent infinite loops
  - Handles maintenance mode with 5-minute wait
  - Comprehensive popup and dialog closing

---

## [0.1.2] - 2025-01-27

### Added
- **LogViewer.py** - Standalone debug log viewer with three-column browser interface
  - Device list navigation (left column)
  - Session list with timestamps (middle column)
  - Log content viewer with inline screenshot display (right column)
  - Lazy image loading for performance optimization
  - Scrollable interface with auto-load on viewport visibility
- **log_database.py** - SQLite-based persistent logging system
  - Per-device database organization in logs/ directory
  - Session tracking with start/end timestamps
  - Screenshot storage as PNG-encoded BLOBs
  - Database statistics and management utilities
  - Memory-efficient lazy loading for large log files
- **Debug Mode** - Enhanced debugging capabilities in ApexGirlBot
  - Optional database-backed logging with screenshots
  - Screenshot annotations (red rectangles and crosshairs on found elements)
  - Detailed action logging with visual confirmation
  - Full log viewer button to launch LogViewer.py

### Changed
- **do_group improvements** - Enhanced group activity automation
  - Better gift collection and claiming logic
  - Improved investment selection
  - More reliable zone participation
  - Enhanced building assistance with character filtering
  - Added far group building support logic
- **Rally join enhancements** - More reliable auto-join for rallies
  - Improved detection of rally availability
  - Better car availability checking
  - Enhanced error recovery
- **Auto-connect on launch** - ApexGirlBot now automatically starts bot loop on launch
  - Eliminates need to manually press Start button
  - Faster workflow for multi-device management
- **Git ignore updates** - Added logs/ directory and config.json to .gitignore

### Fixed
- **do_group bug fixes** - Multiple stability improvements
  - Fixed crashes in group assistance workflow
  - Improved error handling for edge cases
  - Better state management during complex operations

### Technical Details
- **LogViewer Architecture**:
  - Three-panel Tkinter interface with synchronized scrolling
  - SQLite database reading from logs/*.db files
  - PIL-based image rendering from BLOB data
  - Lazy loading prevents memory overflow on large sessions
- **log_database Module**:
  - Two-table schema: sessions and log_entries
  - Millisecond timestamp precision (HH:MM:SS.sss format)
  - PNG compression for screenshot storage
  - Database size tracking and statistics
- **Debug Integration**:
  - Debug mode checkbox in GUI
  - Conditional screenshot capture on each action
  - Database logger instantiation per session
  - "Show Full Log" button launches LogViewer with current device
- **botTemplate.py Updates**:
  - Added LogDatabase import and initialization
  - Debug mode checkbox in GUI Settings
  - `log()` function now accepts optional screenshot parameter
  - "Show Full Log" button launches LogViewer.py

### Documentation
- **NEWBOT.md** - Added comprehensive "Debug Logging with Database" section
  - Enabling Debug mode instructions
  - Using debug mode in bot functions
  - Viewing logs with LogViewer
  - Best practices and examples
  - Managing log database files

---

## [0.1.1] - 2025-01-24

### Added
- **Commands section in GUI** - New section between Functions and Log for quick action buttons
- **"1 fan" command button** - Immediately triggers assist_one_fan function on next bot loop cycle
- **Command trigger system** - Infrastructure for immediate execution of command actions with highest priority

### Changed
- **Code refactoring** - Extracted assist_one_fan function from do_group
- **GUI layout optimization** - Commands section positioned under Functions, left of Settings/buttons
- **do_street improvements**:
  - Added comprehensive documentation with full docstring
  - Added timeout protection to prevent infinite loops (10-second timeouts)
  - Added logging for early returns and error conditions
  - Marked unused parameters for clarity
  - Auto-unchecks Street function in GUI when complete

### Fixed
- **GUI spacing** - Functions area made more compact to accommodate Commands without changing window size
- **Log area preserved** - Maintained original log area size by taking space from Functions section

### Technical Details
- **assist_one_fan function** - Handles selecting and driving a character to assist one group building
- **Command execution** - Runs at start of bot loop with highest priority
- **do_street documentation** - Full docstring with workflow explanation

---

## [0.1.0] - 2025-01-20

### Initial Release

#### Core Features
- **Multi-device Android automation framework** with GUI interface
- **Template-based bot creation** system for easy game automation
- **ApexGirlBot.py** - Full-featured bot for Apex Girl game
- **botTemplate.py** - Barebones template for creating new game bots

#### GUI Features
- **Tkinter-based interface** with real-time logging
- **Multi-window support** for managing multiple devices simultaneously
- **Function toggles** - Enable/disable individual bot actions
- **Single toggle button** - Combined Start/Stop button based on state
- **Auto-unchecking** - Studio task unchecks when target threshold reached
- **Settings panel**:
  - Sleep time configuration
  - Screenshot interval settings
  - "Show NO CLICK" toggle for debug logging
- **Status indicators** - Live status and current action display
- **300-line log buffer** with auto-scroll and manual scroll detection

#### Android Integration
- **ADB connectivity** via ppadb library
- **Screenshot capture** with automatic reconnection on failure
- **Touch/Swipe gestures** with coordinate logging
- **Text input** and keyboard event support (Enter, Backspace)
- **Device serial detection** and multi-device management

#### Image Recognition & OCR
- **OpenCV template matching** for game element detection
- **Tesseract OCR integration** for reading in-game text
- **Configurable accuracy thresholds** for image matching
- **Image needle system** for storing game element templates
- **Combined click logging** - Single line with coordinates and accuracy

#### Logging System
- **Unified logging** - GUI or console output based on availability
- **Consistent formatting** across all modules (android.py, bot.py, ApexGirlBot.py)
- **Timestamp support** on all log entries
- **Suppressible NO CLICK logs** - Cleaner output with optional debug mode

#### Utility Scripts
- **ArrangeWindows.py** - Automatically arrange LDPlayer windows side-by-side
- **getScreenShot.py** - Screenshot capture with MS Paint integration
  - CLI options for output path, format, region capture
  - Verbose/quiet modes
  - Direct serial or user-based device lookup
  - MS Paint auto-open for needle creation

#### Game-Specific Functions (ApexGirlBot)
- **Concert automation** - Send cars to concerts with retry logic
- **Rally participation** - Auto-join rallies when cars available
- **Studio recording** - Record albums until target threshold
- **Group activities** - Gifts, investments, zone assistance
- **Artist management** - Template for artist-related actions
- **Resource collection** - Coin collection, healing, HQ spam

#### Configuration
- **JSON-based config** (config.json)
- **Device management** with user-friendly names
- **Per-device settings** (serial, concert target, stadium target)
- **ADB connection settings** (host, port)
- **Screenshot defaults** (format, output path)

#### Documentation
- **Comprehensive README.md**:
  - Installation instructions (Python, Tesseract, LDPlayer)
  - LDPlayer configuration (540x960 resolution, ADB debugging)
  - Device serial discovery methods
  - config.json setup guide
  - Creating custom bots tutorial
  - Image needle creation workflow
  - MS Paint coordinate finding
  - Troubleshooting guide
- **Code documentation** - Docstrings and inline comments

#### Developer Features
- **Modular architecture** - Separate Android, BOT, and GUI classes
- **Extensible design** - Easy to add new game functions
- **Template system** - botTemplate.py for rapid development
- **Consistent API** - set_gui() and log() pattern across modules

---

## Version History

- **0.4.0** - 2025-12-16 - Fixed ALL mode device selection bug, removed config.json dependency, added apex_girl.example.conf
- **0.3.0** - 2025-12-08 - Major refactoring: unified start_bot.py, commands.py modules, "Shortcuts"→"Commands" rename
- **0.2.0** - 2025-11-16 - Web interface, state monitoring system, comprehensive documentation improvements
- **0.1.3** - 2025-11-11 - Control key override, do_recover improvements, rally enhancements, botTemplate sync
- **0.1.2** - 2025-01-27 - Debug logging system with LogViewer, do_group improvements, auto-connect on launch
- **0.1.1** - 2025-01-24 - Code refactoring, Commands system, do_street improvements
- **0.1.0** - 2025-01-20 - Initial release with core framework and ApexGirl bot

---

## How to Update Versions

### Auto-increment Build Version
```bash
python tools/version_manager.py build
```

### Manually Set Minor Version (summarizes build changes)
```bash
python tools/version_manager.py minor
```

### Manually Set Major Version
```bash
python tools/version_manager.py major
```

### Add Change Entry
```bash
python tools/version_manager.py add "Your change description"
```

---

## Notes

- Build versions auto-increment with each change
- Minor version bump summarizes all build changes
- Major version bump lists minor versions without summarizing
- Keep changelog updated with meaningful descriptions
- Breaking changes should always trigger major version bump
