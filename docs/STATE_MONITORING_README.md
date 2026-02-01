# Bot State Monitoring System

## Overview

The bot framework uses **direct in-memory state management** for instant access and high performance. StateManager database is **optional** and disabled by default.

## Architecture

### Two Operating Modes

#### 1. Local Mode (start_bot.py)
- **Pure local operation** with Tkinter GUI
- **No database** - all state in memory
- **No remote monitoring** - designed for single-bot interactive use
- **Instant response** - no database overhead

```bash
python start_bot.py -g apex_girl -d Gelvil
```

#### 2. Headless Multi-Bot Mode (master_of_bots.py)
- **Integrated web interface** at http://localhost:5000
- **Direct in-memory state** - HeadlessBot objects
- **No database relay** - Flask reads directly from bot memory
- **Instant updates** - commands execute < 100ms
- **Optional StateManager** - disabled by default, can be enabled for persistence

```bash
python master_of_bots.py apex_girl
```

### Components

1. **[gui/bot_gui.py](../gui/bot_gui.py)** - Local GUI with optional StateManager
   - `enable_remote=False` (default) - Pure local mode
   - `enable_remote=True` - Enable StateManager for remote monitoring

2. **[master_of_bots.py](../master_of_bots.py)** - Headless multi-bot manager
   - `HeadlessBot` class - In-memory state with thread-safe access
   - Integrated Flask web server
   - Direct state access via `bot.get_state_dict()`
   - Optional StateManager for persistence/recovery

3. **[core/state_manager.py](../core/state_manager.py)** - Optional persistence
   - SQLite database backend
   - Thread-safe operations
   - **Not used by default** - enabled only when needed

## Direct In-Memory State (Default)

### HeadlessBot State (master_of_bots.py)

All bot state is stored in memory for instant access:

```python
class HeadlessBot:
    # Timing
    start_time: str           # ISO format timestamp
    end_time: str             # ISO format timestamp
    current_action: str       # Current bot function

    # State
    is_running: bool
    function_states: Dict     # Checkbox states
    fix_enabled: HeadlessVar
    debug: HeadlessVar
    sleep_time: HeadlessVar

    # Screenshots
    latest_screenshot: Any    # In-memory screenshot
    screenshot_timestamp: float

    # Logs
    log_buffer: List[str]     # Recent log entries
```

### Direct Access Methods

Flask endpoints use direct memory access:

```python
# Get full bot state (thread-safe)
state = bot.get_state_dict()
# Returns: {
#   'device_name': 'Gelvil',
#   'is_running': True,
#   'start_time': '2026-02-01T12:30:00',
#   'current_action': 'doStreet',
#   'uptime_seconds': 3600,
#   'doStreet': 1,
#   'doArtists': 0,
#   ...
# }

# Get screenshot data (thread-safe)
screenshot_data = bot.get_screenshot_data()
# Returns: {'screenshot': <image>, 'timestamp': 1738419000.5}
```

## Web Interface (master_of_bots only)

### Starting the Web Interface

The web interface is **integrated** into master_of_bots:

```bash
# Start with web UI (default)
python master_of_bots.py apex_girl

# Custom port
python master_of_bots.py apex_girl --port 5001

# Disable web UI (CLI only)
python master_of_bots.py apex_girl --no-web
```

Open browser to `http://localhost:5000`

### Web Interface Features

- **Real-time monitoring** - Instant state updates via direct memory access
- **Remote control** - Toggle checkboxes, adjust settings, send commands
- **Live screenshots** - WebSocket streaming with direct bot access
- **Multi-device dashboard** - Manage all bots from one interface
- **Mobile support** - Works on desktop and mobile browsers
- **Instant commands** - Direct method calls, no database relay (< 100ms)

### Performance

- **State queries**: < 1ms (direct memory access)
- **Commands**: < 100ms (direct method calls)
- **Screenshots**: Real-time streaming
- **No database lag**: Eliminated database polling

## Optional StateManager (Legacy)

StateManager can be optionally enabled for persistence/recovery, but it's **not recommended** for normal use.

### Enabling StateManager

**In start_bot.py:**
```python
# Edit start_bot.py line 296
gui = BotGUI(root, device_name, config=config, enable_remote=True)
```

**In master_of_bots.py:**
```python
# Edit HeadlessBot initialization (line ~150)
self.state_manager = StateManager(device_name)
```

### Database Schema (if enabled)

**Location:** `state/state_monitor.db`

**Table:** `bot_states`

```sql
CREATE TABLE bot_states (
    device_name TEXT PRIMARY KEY,
    is_running INTEGER NOT NULL DEFAULT 1,
    last_update TIMESTAMP NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,

    -- Checkbox states
    doStreet INTEGER DEFAULT 0,
    doArtists INTEGER DEFAULT 0,
    -- ... other checkboxes

    -- Settings
    fix_enabled INTEGER DEFAULT 1,
    debug_enabled INTEGER DEFAULT 0,
    sleep_time REAL DEFAULT 1.0,

    -- Screenshots (optional)
    latest_screenshot BLOB,
    screenshot_timestamp TIMESTAMP,

    -- Logs
    current_log TEXT DEFAULT ''
)
```

### Programmatic Access (if StateManager enabled)

```python
from core.state_manager import StateManager

# Get all running bots
running_bots = StateManager.get_all_running_bots()

# Get specific device state
state = StateManager.get_device_state("Gelvil")

# Get database stats
stats = StateManager.get_database_stats()
```

## Migration from Database Mode

If you were using the old standalone web server:

### Before (Old Architecture)
```bash
# Terminal 1: Start bot
python start_bot.py -g apex_girl -d Gelvil

# Terminal 2: Start web server
python web/server.py

# Bot → StateManager DB → Web Server
```

### After (New Architecture)
```bash
# Option 1: Local GUI only (no remote)
python start_bot.py -g apex_girl -d Gelvil

# Option 2: Headless with integrated web UI
python master_of_bots.py apex_girl

# master_of_bots: Bot → Direct Memory → Flask (instant)
```

## Benefits of Direct In-Memory State

### Performance
- **10-50x faster** state queries (< 1ms vs 10-50ms)
- **Instant commands** - no database write/read cycle
- **Real-time screenshots** - no encoding/decoding to database
- **Zero lag** - no polling delays

### Simplicity
- **No database files** to manage (in local mode)
- **No database locks** or contention
- **No database growth** concerns
- **Fewer moving parts**

### Reliability
- **No database corruption** risk
- **No stale data** - always current
- **No sync issues** - single source of truth
- **Thread-safe** - RLock protection

## Troubleshooting

### start_bot.py Issues

**Problem:** Bot creates state_monitor.db when I don't want it
- **Solution:** Verify start_bot.py line 296 has `enable_remote=False`

**Problem:** Can't access bot remotely
- **Solution:** Use master_of_bots.py for remote access, not start_bot.py

### master_of_bots.py Issues

**Problem:** Web interface not loading
- **Solution:** Check port 5000 not in use, verify Flask installed
- **Command:** `pip install flask flask-cors flask-socketio`

**Problem:** Commands slow or not working
- **Solution:** Check browser console for errors, verify bot is running

**Problem:** Screenshots not updating
- **Solution:** Verify bot has andy connection, check screenshot capture thread

### Performance Issues

**Problem:** High memory usage
- **Solution:** Normal - screenshots stored in memory. Reduce screenshot capture rate if needed.

**Problem:** Commands taking > 100ms
- **Solution:** Check network latency (for remote access), verify no blocking operations

## API Reference

### HeadlessBot Methods

```python
# Get full state dictionary (thread-safe)
bot.get_state_dict() -> dict

# Get screenshot data (thread-safe)
bot.get_screenshot_data() -> dict

# Mark bot as running (updates start_time)
bot.mark_running()

# Mark bot as stopped (updates end_time)
bot.mark_stopped()

# Update current action
bot.update_action(action: str)

# Set checkbox
bot.set_checkbox(func_name: str, enabled: bool)

# Get checkbox
bot.get_checkbox(func_name: str) -> bool
```

### Flask API Endpoints (master_of_bots)

```
GET  /api/bots                        # List all bots
GET  /api/bots/<device>               # Get bot state
GET  /api/bots/<device>/screenshot    # Get screenshot
GET  /api/bots/<device>/details       # Get detailed info

POST /api/command/checkbox            # Toggle checkbox
POST /api/command/setting             # Change setting
POST /api/command/tap                 # Send tap command
POST /api/command/swipe               # Send swipe command
POST /api/command/bot                 # Start/stop bot
POST /api/command/ldplayer            # LDPlayer control
```

## Best Practices

1. **Use start_bot.py for single-bot interactive use**
   - Simple, local-only operation
   - Full GUI with all features
   - No network overhead

2. **Use master_of_bots.py for multi-bot management**
   - Headless operation
   - Web-based monitoring
   - Manage multiple devices

3. **Don't enable StateManager unless needed**
   - Default direct memory mode is faster
   - Only enable for legacy compatibility or persistence needs

4. **For remote access, use master_of_bots, not start_bot**
   - Designed for remote monitoring
   - Better performance
   - Simpler architecture

## License

Same as AndyBotFramework project.
