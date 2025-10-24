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

## [Unreleased]

### Build Changes
<!-- Automatically tracked changes go here. Will be summarized when MINOR version is bumped. -->

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

- **0.1.1** - Code refactoring, Shortcuts system, do_street improvements
- **0.1.0** - Initial release with core framework and ApexGirl bot

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
