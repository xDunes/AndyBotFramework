# Changelog

All notable changes to the Apex-Girl Bot Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version Format

- **MAJOR.MINOR.BUILD** (e.g., 1.2.34)
- **MAJOR**: Breaking changes, major feature overhauls
- **MINOR**: New features, significant improvements (summarizes build changes)
- **BUILD**: Bug fixes, small improvements, refactoring (auto-incremented)

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
- **Activity logging**:
  - Connection status and device detection
  - Click/touch coordinates with target names
  - OCR results and recognition accuracy
  - Error handling and reconnection attempts

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

#### Safety & User Experience
- **Keyboard shortcuts disabled in GUI mode** - Prevents accidental exits
- **Error recovery** - Automatic reconnection on connection loss
- **Graceful shutdown** - Stop button properly terminates bot loop
- **No malicious code** - Defensive security focus only

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

## [0.1.3] - 2025-11-11

### Added
- **Control key override** - Hold Ctrl key during bot loop to skip function execution
  - Shows "CTRL held - skipping {function_name}" status during override
  - Works during both function execution and sleep periods
  - Allows manual intervention without stopping the bot
  - Synced to botTemplate.py for consistency across all bots

### Changed
- **do_recover improvements** - Enhanced recovery function with additional fix cases
  - Added fixceocard detection and handling ([ApexGirlBot.py:920-922](ApexGirlBot.py:920-922))
  - Added fixgenericback for generic back button detection ([ApexGirlBot.py:923-924](ApexGirlBot.py:923-924))
  - Added fixmapassist to click away from assist popup ([ApexGirlBot.py:895-897](ApexGirlBot.py:895-897))
  - Improved navigation reliability when bot gets stuck
- **Rally improvements** - Enhanced rally detection and joining
  - Added dangerrally image detection for danger rallies ([ApexGirlBot.py:485](ApexGirlBot.py:485))
  - Improved rally join reliability with better counter logic ([ApexGirlBot.py:501-520](ApexGirlBot.py:501-520))
  - Added back button handling when rally join fails
- **botTemplate.py updates** - Synced Control key override feature from ApexGirlBot
  - Added keyboard library import ([botTemplate.py:718-719](botTemplate.py:718-719))
  - Added Ctrl key detection before function execution ([botTemplate.py:731-736](botTemplate.py:731-736))
  - Added Ctrl key override status during sleep ([botTemplate.py:781-786](botTemplate.py:781-786))

### Technical Details
- **Control Key Implementation** ([ApexGirlBot.py:2015-2090](ApexGirlBot.py:2015-2090))
  - Uses `keyboard.is_pressed('ctrl')` to detect Ctrl key state
  - Checks before each function and during sleep
  - Displays override status in GUI
  - Breaks out of function loop when Ctrl is held
- **Rally Counter Logic** ([ApexGirlBot.py:501-520](ApexGirlBot.py:501-520))
  - Maximum 20 attempts to find rally join button
  - Maximum 30 attempts to find drive button after joining
  - Auto-backs out if counters exceeded
- **Recovery Function Enhancements** ([ApexGirlBot.py:868-943](ApexGirlBot.py:868-943))
  - Maximum 20 recovery attempts to prevent infinite loops
  - Handles maintenance mode with 5-minute wait
  - Comprehensive popup and dialog closing

---

## [Unreleased]

### Build Changes
<!-- Automatically tracked changes go here. Will be summarized when MINOR version is bumped. -->

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
  - Prevents accidental commit of sensitive configuration
  - Keeps log databases local to each installation

### Fixed
- **do_group bug fixes** - Multiple stability improvements
  - Fixed crashes in group assistance workflow
  - Improved error handling for edge cases
  - Better state management during complex operations

### Technical Details
- **LogViewer Architecture** (LogViewer.py:1-450+):
  - Three-panel Tkinter interface with synchronized scrolling
  - SQLite database reading from logs/*.db files
  - PIL-based image rendering from BLOB data
  - Lazy loading prevents memory overflow on large sessions
- **log_database Module** (log_database.py:1-200+):
  - Two-table schema: sessions and log_entries
  - Millisecond timestamp precision (HH:MM:SS.sss format)
  - PNG compression for screenshot storage
  - Database size tracking and statistics
- **Debug Integration** (ApexGirlBot.py):
  - Debug mode checkbox in GUI
  - Conditional screenshot capture on each action
  - Database logger instantiation per session
  - "Show Full Log" button launches LogViewer with current device
- **botTemplate.py Updates**:
  - Added LogDatabase import and initialization
  - Debug mode checkbox in GUI Settings
  - `log()` function now accepts optional screenshot parameter
  - "Show Full Log" button launches LogViewer.py
  - `_on_debug_toggle()` callback for database initialization
  - `_get_timestamp()` with millisecond support
  - `detailed_log_buffer` for storing entries with screenshots

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
- **Shortcuts section in GUI** - New section between Functions and Log for quick action buttons
- **"1 fan" shortcut button** - Immediately triggers assist_one_fan function on next bot loop cycle
- **Shortcut trigger system** - Infrastructure for immediate execution of shortcut actions with highest priority

### Changed
- **Code refactoring** - Extracted assist_one_fan function from do_group (lines 726-760)
- **GUI layout optimization** - Shortcuts section positioned under Functions, left of Settings/buttons
- **do_street improvements**:
  - Added comprehensive documentation with full docstring
  - Added timeout protection to prevent infinite loops (10-second timeouts)
  - Added logging for early returns and error conditions
  - Marked unused parameters for clarity
  - Auto-unchecks Street function in GUI when complete

### Fixed
- **GUI spacing** - Functions area made more compact to accommodate Shortcuts without changing window size
- **Log area preserved** - Maintained original log area size by taking space from Functions section

### Technical Details
- **assist_one_fan function** (ApexGirlBot.py:627-677) - Handles selecting and driving a character to assist one group building
- **Shortcut execution** (ApexGirlBot.py:1402-1414) - Runs at start of bot loop with highest priority
- **do_street documentation** (ApexGirlBot.py:807-823) - Full docstring with workflow explanation

---

## Version History

- **0.1.3** - 2025-11-11 - Control key override, do_recover improvements, rally enhancements, botTemplate sync
- **0.1.2** - 2025-01-27 - Debug logging system with LogViewer, do_group improvements, auto-connect on launch
- **0.1.1** - 2025-01-24 - Code refactoring, Shortcuts system, do_street improvements
- **0.1.0** - 2025-01-20 - Initial release with core framework and ApexGirl bot

---

## How to Update Versions

### Auto-increment Build Version
```bash
python version_manager.py build
```

### Manually Set Minor Version (summarizes build changes)
```bash
python version_manager.py minor
```

### Manually Set Major Version
```bash
python version_manager.py major
```

### Add Change Entry
```bash
python version_manager.py add "Your change description"
```

---

## Notes

- Build versions auto-increment with each change
- Minor version bump summarizes all build changes
- Major version bump lists minor versions without summarizing
- Keep changelog updated with meaningful descriptions
- Breaking changes should always trigger major version bump
