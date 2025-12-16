# Bot State Monitoring System

## Overview

The State Monitoring System provides real-time monitoring of multiple concurrent bot instances using SQLite. This allows remote monitoring of all running bots, their checkbox states, logs, and latest screenshots.

## Architecture

### Components

1. **[core/state_manager.py](../core/state_manager.py)** - Core state management module
   - `StateManager` class - Manages state for a single bot instance
   - SQLite database backend
   - Thread-safe operations
   - Class methods for querying all bots

2. **[Web Interface](../web/)** - Web-based monitoring application
   - Real-time view of all bot instances
   - Auto-refresh with configurable intervals
   - View device details, logs, and screenshots
   - Remote control via web browser
   - Desktop and mobile support

3. **Bot Integration** - All bots integrate with StateManager
   - Automatically tracks all state changes
   - Updates database on checkbox/setting changes
   - Sends logs and screenshots to state database
   - Heartbeat every bot loop iteration

### Database Schema

**Location:** `state/state_monitor.db`

**Table:** `bot_states`

```sql
CREATE TABLE bot_states (
    device_name TEXT PRIMARY KEY,           -- Device identifier (e.g., "Gelvil", "Gelvil1")
    is_running INTEGER NOT NULL DEFAULT 1,  -- 1=running, 0=stopped
    last_update TIMESTAMP NOT NULL,         -- Last state update
    start_time TIMESTAMP NOT NULL,          -- Bot start time
    end_time TIMESTAMP,                     -- Bot stop time (NULL if running)

    -- Checkbox states (11 function checkboxes)
    doStreet INTEGER DEFAULT 0,
    doArtists INTEGER DEFAULT 0,
    doStudio INTEGER DEFAULT 0,
    doTour INTEGER DEFAULT 0,
    doGroup INTEGER DEFAULT 0,
    doConcert INTEGER DEFAULT 0,
    doHelp INTEGER DEFAULT 0,
    doCoin INTEGER DEFAULT 0,
    doHeal INTEGER DEFAULT 0,
    doRally INTEGER DEFAULT 0,

    -- Settings
    fix_enabled INTEGER DEFAULT 1,          -- Fix/Recover enabled
    debug_enabled INTEGER DEFAULT 0,        -- Debug mode enabled
    sleep_time REAL DEFAULT 1.0,            -- Bot loop sleep time (seconds)
    studio_stop INTEGER DEFAULT 6,          -- Studio stop count
    screenshot_interval INTEGER DEFAULT 0,  -- Screenshot interval (seconds)

    -- Latest screenshot
    latest_screenshot BLOB,                 -- PNG encoded screenshot
    screenshot_timestamp TIMESTAMP,         -- Screenshot capture time

    -- Current log (last 10 entries)
    current_log TEXT DEFAULT ''             -- Newline-separated log entries
)
```

## Usage

### 1. Running Bots (Automatic)

State monitoring is **automatically enabled** when you start any bot instance. No configuration required!

```bash
# Start a bot - state monitoring starts automatically
python start_bot.py -g apex_girl -d Gelvil
```

The bot will:
- Create/update its entry in `state/state_monitor.db`
- Track all checkbox and setting changes in real-time
- Update logs and screenshots periodically
- Send heartbeat every bot loop iteration
- Mark as stopped when bot exits

### 2. Viewing Bot States

Launch the web interface to monitor all running bots:

```bash
cd web
python server.py
```

Then open your browser to `http://localhost:5000`

**Web Interface Features:**
- **Device List** - Shows all bot instances (running in green, stopped in red/orange)
- **Auto-refresh** - Configurable refresh intervals
- **Device Details** - Click a device to view:
  - Status (running/stopped, uptime, last update)
  - Settings (sleep time, debug, fix enabled, etc.)
  - Enabled/Disabled checkboxes
  - Recent log entries (last 10)
  - Latest screenshot with click/tap and swipe controls
- **Remote Control** - Send commands, change settings, control bots remotely
- **Mobile Support** - Works on desktop and mobile browsers
- **Database Stats** - Total bots, running, stopped, database size

### 3. Programmatic Access

You can query bot states programmatically:

```python
from core.state_manager import StateManager

# Get all running bots
running_bots = StateManager.get_all_running_bots()
for bot in running_bots:
    print(f"{bot['device_name']}: {bot['last_update']}")

# Get specific device state
state = StateManager.get_device_state("Gelvil")
if state:
    print(f"Status: {'Running' if state['is_running'] else 'Stopped'}")
    print(f"Enabled: {[k for k in state if state[k] == 1 and k.startswith('do')]}")

# Get device screenshot
screenshot = StateManager.get_device_screenshot("Gelvil")
if screenshot is not None:
    cv2.imshow("Screenshot", screenshot)

# Get database stats
stats = StateManager.get_database_stats()
print(f"Total bots: {stats['total_bots']}")
print(f"Running: {stats['running_bots']}")
print(f"Database size: {stats['db_size_mb']} MB")

# Get formatted summary
from core.state_manager import get_running_bots_summary
print(get_running_bots_summary())
```

### 4. Manual State Management (Advanced)

If you need to manually manage state for custom scripts:

```python
from core.state_manager import StateManager

# Initialize state manager
state_mgr = StateManager("MyCustomBot")

# Update checkbox states
state_mgr.update_checkbox_state("doStreet", True)
state_mgr.update_checkbox_state("doGroup", True)

# Update all checkboxes at once
checkboxes = {
    'doStreet': True,
    'doGroup': True,
    'doStudio': False,
    # ... etc
}
state_mgr.update_all_checkbox_states(checkboxes)

# Update settings
state_mgr.update_settings(
    fix_enabled=True,
    debug_enabled=False,
    sleep_time=2.5,
    studio_stop=6,
    screenshot_interval=0
)

# Add log entry (with optional screenshot)
state_mgr.add_log("Bot started successfully")
state_mgr.add_log("Found enemy", screenshot=screenshot_array)

# Update only screenshot
state_mgr.update_screenshot(screenshot_array)

# Send heartbeat (call periodically to show bot is alive)
state_mgr.heartbeat()

# Mark as stopped when done
state_mgr.mark_stopped()
```

## Integration Details

### Bot Integration

All bots automatically integrate with StateManager through the GUI:

1. **Initialization** (gui/bot_gui.py)
   ```python
   self.state_manager = StateManager(self.username)
   ```

2. **Checkbox Changes**
   - Trace callbacks on all checkbox variables
   - Automatic database update on change

3. **Settings Changes**
   - Trace callbacks on all settings
   - Automatic database update on change

4. **Log Updates**
   - Every log entry updates state database
   - Throttled to every 5th log entry (or if screenshot present)
   - Maintains last 10 log entries in database

5. **Heartbeat** (core/bot_loop.py)
   - Called every bot loop iteration
   - Updates `last_update` timestamp
   - Allows detection of stuck/crashed bots

6. **Stop Detection**
   - Automatically marks bot as stopped when Stop button clicked
   - Updates `end_time` and sets `is_running = 0`

## Performance Considerations

### Database Optimization

- **Thread-safe**: All database operations use class-level lock
- **Connection pooling**: Each operation gets new connection (SQLite limitation)
- **Indices**: Fast lookups on `is_running` and `last_update`
- **Throttling**: Log updates throttled to every 5th entry

### Screenshot Storage

- **Format**: PNG encoded (compressed)
- **Storage**: Stored as BLOB in database
- **Size**: ~50-200KB per screenshot (depending on content)
- **Updates**: Only when screenshot provided to `add_log()` or `update_screenshot()`

### Update Frequency

- **Checkbox/Settings**: Immediate (on change)
- **Logs**: Every 5th log entry (or with screenshot)
- **Screenshots**: On demand (when captured)
- **Heartbeat**: Every bot loop iteration (~1-5 seconds)

## Monitoring Stale Bots

The StateViewer GUI shows bots as **orange** if `last_update` is more than 30 seconds old. This indicates:
- Bot may be stuck
- Bot may have crashed
- Long-running operation in progress

Check the log entries to determine the bot's state.

## Database Maintenance

### Clear Specific Device

```python
StateManager.clear_device_state("Gelvil")
```

### Clear All Devices

```python
StateManager.clear_all_states()
```

### Manual Database Access

The database is located at `state/state_monitor.db` and can be accessed with any SQLite client:

```bash
sqlite3 state/state_monitor.db

# Query running bots
SELECT device_name, last_update FROM bot_states WHERE is_running = 1;

# Check database size
SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb FROM pragma_page_count(), pragma_page_size();
```

## Troubleshooting

### State not updating

1. Check bot is running: `is_running = 1` in database
2. Check `last_update` timestamp - should be recent
3. Verify state_manager imported in bot script
4. Check console for errors like "Error updating state manager"

### Screenshots not appearing

1. Verify Debug mode is enabled (screenshots captured more frequently)
2. Check `screenshot_timestamp` in database
3. Verify `capture_screen()` function working correctly
4. Check database size - may be getting large

### Web interface not refreshing

1. Check auto-refresh is enabled in the web interface
2. Verify `state/state_monitor.db` file exists
3. Check browser console and server console for errors
4. Try manual refresh in the browser

### Database getting large

Screenshots can consume significant space. To reduce:

1. Clear old device states periodically
2. Disable Debug mode when not needed
3. Consider periodic database vacuum:
   ```python
   import sqlite3
   conn = sqlite3.connect('state/state_monitor.db')
   conn.execute('VACUUM')
   conn.close()
   ```

## Multi-Instance Support

The system is designed for multiple concurrent bot instances:

- **Shared database**: All bots write to `state/state_monitor.db`
- **Primary key**: `device_name` ensures one row per device
- **Thread-safe**: Lock prevents race conditions
- **Independent**: Each bot manages its own state

Example with 6 concurrent bots:

```bash
# Terminal 1
python start_bot.py -g apex_girl -d Gelvil

# Terminal 2
python start_bot.py -g apex_girl -d Gelvil1

# Terminal 3
python start_bot.py -g apex_girl -d Gelvil2

# ... etc

# Start web interface to monitor all
python web/server.py
```

All 6 bots will appear in the web interface, each with their own independent state.

## Future Enhancements

Potential improvements:

1. **Remote Database** - MySQL/PostgreSQL for network access
2. **Alerts** - Notifications when bots crash or stuck
3. **Historical Data** - Track state changes over time
4. **Performance Metrics** - Track loops/second, function execution times
5. **Screenshot History** - Store multiple screenshots per bot
6. **Export/Import** - Backup and restore bot configurations

## API Reference

See docstrings in [core/state_manager.py](../core/state_manager.py) for complete API documentation.

### Main Classes

- `StateManager(device_name)` - State manager for a single bot

### Key Methods

- `update_checkbox_state(name, enabled)` - Update single checkbox
- `update_all_checkbox_states(states)` - Update all checkboxes
- `update_settings(**kwargs)` - Update bot settings
- `add_log(message, screenshot)` - Add log with optional screenshot
- `update_screenshot(screenshot)` - Update screenshot only
- `heartbeat()` - Update timestamp
- `mark_stopped()` - Mark bot as stopped

### Class Methods (Query)

- `get_all_running_bots()` - Get all running bots
- `get_all_bots()` - Get all bots (running and stopped)
- `get_device_state(device_name)` - Get state for specific device
- `get_device_screenshot(device_name)` - Get latest screenshot
- `clear_device_state(device_name)` - Remove device state
- `clear_all_states()` - Clear all states
- `get_database_stats()` - Get database statistics

## License

Same as ApexGirl Bot project.
