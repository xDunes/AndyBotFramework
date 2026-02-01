"""
State Manager - SQLite-backed Bot State Monitoring

Provides SQLite-backed state monitoring for multiple concurrent bot instances.
Each bot instance updates its state in a shared database, allowing remote monitoring
of all running bots, their checkbox states, logs, and latest screenshots.

Database Location: state/state_monitor.db

Usage:
    # Initialize state manager for a device
    state_mgr = StateManager(device_name="Gelvil")

    # Update checkbox states
    state_mgr.update_checkbox_state("doStreet", True)
    state_mgr.update_all_checkbox_states(gui.function_states)

    # Update settings
    state_mgr.update_settings(sleep_time=1, debug=True, fix_enabled=True)

    # Add log entry with screenshot
    state_mgr.add_log("Starting street tasks...", screenshot=screenshot_array)

    # Update screenshot only
    state_mgr.update_screenshot(screenshot_array)

    # Mark bot as stopped
    state_mgr.mark_stopped()

    # Query all running bots
    running_bots = StateManager.get_all_running_bots()

    # Get state for specific device
    device_state = StateManager.get_device_state("Gelvil")
"""

import sqlite3
import os
import json
from datetime import datetime
import cv2 as cv
import threading

# Cache for valid checkboxes loaded from config
_valid_checkboxes_cache = None


def _get_valid_checkboxes():
    """Get valid checkbox names from config function_layout

    Returns:
        list: Flattened list of checkbox names from function_layout
    """
    global _valid_checkboxes_cache
    if _valid_checkboxes_cache is None:
        try:
            from .config_loader import load_config
            config = load_config()
            # Flatten function_layout into a single list
            function_layout = config.get('function_layout', [])
            _valid_checkboxes_cache = [
                checkbox for row in function_layout for checkbox in row
            ]
        except Exception:
            # Fallback to empty list if config can't be loaded
            _valid_checkboxes_cache = []
    return _valid_checkboxes_cache


class StateManager:
    """SQLite-backed state manager for multi-instance bot monitoring"""

    # Class-level lock for thread-safe database access
    _db_lock = threading.Lock()

    # Shared database path
    _db_path = None

    # Thread-local storage for connection pooling (one connection per thread)
    _thread_local = threading.local()

    @classmethod
    def _get_db_path(cls):
        """Get the shared database path (lazy initialization)"""
        if cls._db_path is None:
            # State directory is at project root, not inside core/
            project_root = os.path.dirname(os.path.dirname(__file__))
            state_dir = os.path.join(project_root, 'state')
            os.makedirs(state_dir, exist_ok=True)
            cls._db_path = os.path.join(state_dir, 'state_monitor.db')
        return cls._db_path

    def __init__(self, device_name):
        """Initialize state manager for a device

        Args:
            device_name: Device/user name (e.g., "Gelvil", "Gelvil1")

        Note:
            All instances share the same database file.
            Each device has its own row in the bot_states table.
        """
        self.device_name = device_name
        self.db_path = self._get_db_path()
        self.current_action = ""  # Track current action/function for display

        # Initialize database schema (thread-safe)
        self._init_schema()

        # Create or update bot state entry
        self._init_bot_state()

    def _get_connection(self):
        """Get a database connection using thread-local pooling

        Each thread reuses its own connection instead of creating new ones.
        This significantly reduces connection overhead.

        Returns:
            sqlite3.Connection: Database connection for current thread
        """
        # Check if this thread already has a connection
        if not hasattr(self._thread_local, 'connection') or self._thread_local.connection is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent performance
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            self._thread_local.connection = conn
        return self._thread_local.connection

    def _close_connection(self):
        """Close the thread-local connection if it exists"""
        if hasattr(self._thread_local, 'connection') and self._thread_local.connection is not None:
            try:
                self._thread_local.connection.close()
            except Exception:
                pass
            self._thread_local.connection = None

    def _init_schema(self):
        """Initialize database schema if not exists (thread-safe)"""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Bot states table - one row per device
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_states (
                    device_name TEXT PRIMARY KEY,
                    is_running INTEGER NOT NULL DEFAULT 1,
                    last_update TIMESTAMP NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,

                    -- Checkbox states (function checkboxes)
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
                    doParking INTEGER DEFAULT 0,
                    doGig INTEGER DEFAULT 0,

                    -- Settings
                    fix_enabled INTEGER DEFAULT 1,
                    debug_enabled INTEGER DEFAULT 0,
                    sleep_time REAL DEFAULT 1.0,
                    studio_stop INTEGER DEFAULT 6,
                    screenshot_interval INTEGER DEFAULT 0,
                    ld_running INTEGER DEFAULT 1,

                    -- Latest screenshot
                    latest_screenshot BLOB,
                    screenshot_timestamp TIMESTAMP,

                    -- Current log (last 10 entries)
                    current_log TEXT DEFAULT '',

                    -- Current action/function
                    current_action TEXT DEFAULT '',

                    -- Command queue data (JSON)
                    command_queue TEXT DEFAULT '{}'
                )
            ''')

            # Remote commands table - for sending commands from web interface to bots
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS remote_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_name TEXT NOT NULL,
                    command_type TEXT NOT NULL,
                    command_data TEXT,
                    created_at TIMESTAMP NOT NULL,
                    processed INTEGER DEFAULT 0,
                    processed_at TIMESTAMP
                )
            ''')

            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_is_running
                ON bot_states(is_running)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_update
                ON bot_states(last_update)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_device_processed
                ON remote_commands(device_name, processed)
            ''')

            # Migration: Add columns if they don't exist (for existing databases)
            cursor.execute("PRAGMA table_info(bot_states)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'ld_running' not in columns:
                cursor.execute('ALTER TABLE bot_states ADD COLUMN ld_running INTEGER DEFAULT 1')
            if 'doParking' not in columns:
                cursor.execute('ALTER TABLE bot_states ADD COLUMN doParking INTEGER DEFAULT 0')
            if 'doGig' not in columns:
                cursor.execute('ALTER TABLE bot_states ADD COLUMN doGig INTEGER DEFAULT 0')
            if 'current_action' not in columns:
                cursor.execute('ALTER TABLE bot_states ADD COLUMN current_action TEXT DEFAULT \'\'')
            if 'command_queue' not in columns:
                cursor.execute('ALTER TABLE bot_states ADD COLUMN command_queue TEXT DEFAULT \'{}\'')

            conn.commit()
            # Don't close - connection is reused via thread-local pooling

    def _init_bot_state(self):
        """Create or reset bot state entry for this device

        Note:
            Does NOT set is_running=1 automatically. The bot should call
            mark_running() only after successfully connecting to a device.
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.now()

            # Check if entry exists
            cursor.execute('''
                SELECT device_name FROM bot_states WHERE device_name = ?
            ''', (self.device_name,))

            exists = cursor.fetchone() is not None

            if exists:
                # Update existing entry - reset timestamp but keep is_running as 0
                # Bot will call mark_running() after successful device connection
                cursor.execute('''
                    UPDATE bot_states
                    SET is_running = 0,
                        ld_running = 0,
                        last_update = ?,
                        end_time = NULL,
                        current_log = ''
                    WHERE device_name = ?
                ''', (now, self.device_name))
            else:
                # Create new entry with is_running = 0 (not connected yet)
                cursor.execute('''
                    INSERT INTO bot_states (
                        device_name, is_running, ld_running, start_time, last_update
                    ) VALUES (?, 0, 0, ?, ?)
                ''', (self.device_name, now, now))

            conn.commit()

    def update_checkbox_state(self, checkbox_name, enabled):
        """Update a single checkbox state

        Args:
            checkbox_name: Name of checkbox (e.g., "doStreet", "doGroup")
            enabled: Boolean state of checkbox
        """
        # Validate checkbox name against config
        if checkbox_name not in _get_valid_checkboxes():
            return  # Silently ignore invalid checkbox names

        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Dynamic SQL to update specific checkbox column
            value = 1 if enabled else 0
            cursor.execute(f'''
                UPDATE bot_states
                SET {checkbox_name} = ?,
                    last_update = ?
                WHERE device_name = ?
            ''', (value, datetime.now(), self.device_name))

            conn.commit()

    def update_all_checkbox_states(self, function_states):
        """Update all checkbox states at once

        Args:
            function_states: Dictionary of {checkbox_name: BooleanVar} from GUI
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build SET clause dynamically
            updates = []
            values = []

            for checkbox_name in _get_valid_checkboxes():
                if checkbox_name in function_states:
                    value = 1 if function_states[checkbox_name].get() else 0
                    updates.append(f'{checkbox_name} = ?')
                    values.append(value)

            if updates:
                updates.append('last_update = ?')
                values.append(datetime.now())
                values.append(self.device_name)

                sql = f'''
                    UPDATE bot_states
                    SET {', '.join(updates)}
                    WHERE device_name = ?
                '''

                cursor.execute(sql, values)
                conn.commit()

    def update_state(self, state_dict):
        """Update bot state from a dictionary

        This is a flexible method that can update any known columns in bot_states.
        Used by botTemplate.py to update multiple state values at once.

        Args:
            state_dict: Dictionary with state values to update. Supported keys:
                - is_running: Boolean
                - debug_enabled: Boolean
                - sleep_time: Float
                - screenshot_interval: Float/Int
                - Any valid checkbox name (doStreet, doStudio, etc.)
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            updates = []
            values = []

            # Map of allowed fields and their conversion functions
            field_map = {
                'is_running': lambda x: 1 if x else 0,
                'debug_enabled': lambda x: 1 if x else 0,
                'fix_enabled': lambda x: 1 if x else 0,
                'sleep_time': float,
                'screenshot_interval': int,
                'studio_stop': int,
            }

            # Valid checkbox names from config
            valid_checkboxes = _get_valid_checkboxes()

            for key, value in state_dict.items():
                if key in field_map:
                    updates.append(f'{key} = ?')
                    values.append(field_map[key](value))
                elif key in valid_checkboxes:
                    updates.append(f'{key} = ?')
                    values.append(1 if value else 0)

            if updates:
                updates.append('last_update = ?')
                values.append(datetime.now())
                values.append(self.device_name)

                sql = f'''
                    UPDATE bot_states
                    SET {', '.join(updates)}
                    WHERE device_name = ?
                '''

                cursor.execute(sql, values)
                conn.commit()

    def update_settings(self, fix_enabled=None, debug_enabled=None,
                       sleep_time=None, studio_stop=None, screenshot_interval=None):
        """Update bot settings

        Args:
            fix_enabled: Boolean - Fix/Recover function enabled
            debug_enabled: Boolean - Debug mode enabled
            sleep_time: Float - Sleep time between bot loops (seconds)
            studio_stop: Int - Studio stop count
            screenshot_interval: Int - Screenshot capture interval (seconds)
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            updates = []
            values = []

            if fix_enabled is not None:
                updates.append('fix_enabled = ?')
                values.append(1 if fix_enabled else 0)

            if debug_enabled is not None:
                updates.append('debug_enabled = ?')
                values.append(1 if debug_enabled else 0)

            if sleep_time is not None:
                updates.append('sleep_time = ?')
                values.append(float(sleep_time))

            if studio_stop is not None:
                updates.append('studio_stop = ?')
                values.append(int(studio_stop))

            if screenshot_interval is not None:
                updates.append('screenshot_interval = ?')
                values.append(int(screenshot_interval))

            if updates:
                updates.append('last_update = ?')
                values.append(datetime.now())
                values.append(self.device_name)

                sql = f'''
                    UPDATE bot_states
                    SET {', '.join(updates)}
                    WHERE device_name = ?
                '''

                cursor.execute(sql, values)
                conn.commit()

    def add_log(self, message, screenshot=None):
        """Add a log entry and optionally update screenshot

        Args:
            message: Log message text
            screenshot: Optional numpy array (BGR/BGRA format)

        Note:
            - Maintains last 10 log entries in current_log field
            - Updates latest_screenshot if provided
            - Adds timestamp to each log entry
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.now()
            timestamp = now.strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}"

            # Get current log
            cursor.execute('''
                SELECT current_log FROM bot_states WHERE device_name = ?
            ''', (self.device_name,))

            row = cursor.fetchone()
            if row:
                current_log = row['current_log']
                log_lines = current_log.split('\n') if current_log else []

                # Add new entry and keep last 50 for better visibility
                log_lines.append(log_entry)
                log_lines = log_lines[-50:]

                new_log = '\n'.join(log_lines)
            else:
                new_log = log_entry

            # Update log and screenshot
            screenshot_blob = None
            if screenshot is not None:
                # Use JPEG encoding for faster performance
                encode_params = [cv.IMWRITE_JPEG_QUALITY, 85]
                success, encoded = cv.imencode('.jpg', screenshot, encode_params)
                if success:
                    screenshot_blob = encoded.tobytes()

            if screenshot_blob:
                cursor.execute('''
                    UPDATE bot_states
                    SET current_log = ?,
                        latest_screenshot = ?,
                        screenshot_timestamp = ?,
                        last_update = ?
                    WHERE device_name = ?
                ''', (new_log, screenshot_blob, now, now, self.device_name))
            else:
                cursor.execute('''
                    UPDATE bot_states
                    SET current_log = ?,
                        last_update = ?
                    WHERE device_name = ?
                ''', (new_log, now, self.device_name))

            conn.commit()

    def update_screenshot(self, screenshot, quality=85):
        """Update only the latest screenshot (optimized with JPEG encoding)

        Args:
            screenshot: Numpy array (BGR/BGRA format)
            quality: JPEG quality (1-100, default 85) - lower = smaller/faster
        """
        if screenshot is None:
            return

        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Encode screenshot to JPEG (much faster than PNG, smaller file size)
            # JPEG encoding is 5-10x faster than PNG and produces 60-80% smaller files
            encode_params = [cv.IMWRITE_JPEG_QUALITY, quality]
            success, encoded = cv.imencode('.jpg', screenshot, encode_params)
            if success:
                screenshot_blob = encoded.tobytes()
                now = datetime.now()

                cursor.execute('''
                    UPDATE bot_states
                    SET latest_screenshot = ?,
                        screenshot_timestamp = ?,
                        last_update = ?
                    WHERE device_name = ?
                ''', (screenshot_blob, now, now, self.device_name))

                conn.commit()

    def mark_stopped(self):
        """Mark this bot instance as stopped"""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.now()
            cursor.execute('''
                UPDATE bot_states
                SET is_running = 0,
                    end_time = ?,
                    last_update = ?
                WHERE device_name = ?
            ''', (now, now, self.device_name))

            conn.commit()

    def mark_running(self):
        """Mark this bot instance as running (for restart after stop)"""
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.now()
            cursor.execute('''
                UPDATE bot_states
                SET is_running = 1,
                    start_time = ?,
                    end_time = NULL,
                    last_update = ?
                WHERE device_name = ?
            ''', (now, now, self.device_name))

            conn.commit()

    def update_ld_running(self, is_running):
        """Update LDPlayer running state in database

        Args:
            is_running: Boolean - True if LDPlayer instance is running
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE bot_states
                SET ld_running = ?,
                    last_update = ?
                WHERE device_name = ?
            ''', (1 if is_running else 0, datetime.now(), self.device_name))

            conn.commit()

    def heartbeat(self):
        """Update last_update timestamp to show bot is alive

        Call this periodically (e.g., every bot loop iteration) to indicate
        the bot is still running. Useful for detecting stuck/crashed bots.
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE bot_states
                SET last_update = ?
                WHERE device_name = ?
            ''', (datetime.now(), self.device_name))

            conn.commit()

    def update_current_action(self, action):
        """Update current action/function being executed

        Args:
            action: String describing current action (e.g., "Recovery", "Group", "User input")
        """
        self.current_action = action
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE bot_states
                SET current_action = ?,
                    last_update = ?
                WHERE device_name = ?
            ''', (action, datetime.now(), self.device_name))

            conn.commit()

    def update_command_queue(self, queue_info):
        """Update command queue information in database

        Args:
            queue_info: Dict with queue information from bot.get_command_queue_info()
                       {'queue_size': int, 'commands': [...]}
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE bot_states
                SET command_queue = ?,
                    last_update = ?
                WHERE device_name = ?
            ''', (json.dumps(queue_info), datetime.now(), self.device_name))

            conn.commit()

    # ============================================================================
    # CLASS METHODS - QUERY ALL BOTS
    # ============================================================================

    @classmethod
    def get_all_running_bots(cls):
        """Get all currently running bot instances

        Returns:
            list: List of device state dictionaries for running bots
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM bot_states
                WHERE is_running = 1
                ORDER BY start_time DESC
            ''')

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results

    @classmethod
    def get_all_bots(cls):
        """Get all bot instances (running and stopped)

        Returns:
            list: List of all device state dictionaries
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM bot_states
                ORDER BY last_update DESC
            ''')

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results

    @classmethod
    def get_device_state(cls, device_name):
        """Get state for a specific device

        Args:
            device_name: Device name to query

        Returns:
            dict or None: Device state dictionary or None if not found
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM bot_states WHERE device_name = ?
            ''', (device_name,))

            row = cursor.fetchone()
            conn.close()

            return dict(row) if row else None

    @classmethod
    def get_device_screenshot(cls, device_name):
        """Get latest screenshot for a device

        Args:
            device_name: Device name to query

        Returns:
            numpy.ndarray or None: Screenshot image or None if not found
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT latest_screenshot FROM bot_states WHERE device_name = ?
            ''', (device_name,))

            row = cursor.fetchone()
            conn.close()

            if row and row['latest_screenshot']:
                import numpy as np
                nparr = np.frombuffer(row['latest_screenshot'], np.uint8)
                img = cv.imdecode(nparr, cv.IMREAD_UNCHANGED)
                return img

            return None

    @classmethod
    def get_device_screenshot_with_timestamp(cls, device_name):
        """Get latest screenshot and its timestamp for a device

        Args:
            device_name: Device name to query

        Returns:
            tuple: (numpy.ndarray or None, timestamp or None)
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT latest_screenshot, screenshot_timestamp FROM bot_states WHERE device_name = ?
            ''', (device_name,))

            row = cursor.fetchone()
            conn.close()

            if row and row['latest_screenshot']:
                import numpy as np
                nparr = np.frombuffer(row['latest_screenshot'], np.uint8)
                img = cv.imdecode(nparr, cv.IMREAD_UNCHANGED)
                return img, row['screenshot_timestamp']

            return None, None

    @classmethod
    def clear_device_state(cls, device_name):
        """Remove a device from the state database

        Args:
            device_name: Device name to remove
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM bot_states WHERE device_name = ?
            ''', (device_name,))

            conn.commit()
            conn.close()

    @classmethod
    def clear_all_states(cls):
        """Clear all device states from database

        Use with caution - removes all monitoring data!
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM bot_states')

            conn.commit()
            conn.close()

    @classmethod
    def get_database_stats(cls):
        """Get statistics about the state database

        Returns:
            dict: Statistics including counts and database size
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get counts
            cursor.execute('SELECT COUNT(*) as total_bots FROM bot_states')
            total_bots = cursor.fetchone()['total_bots']

            cursor.execute('SELECT COUNT(*) as running_bots FROM bot_states WHERE is_running = 1')
            running_bots = cursor.fetchone()['running_bots']

            cursor.execute('SELECT COUNT(*) as with_screenshots FROM bot_states WHERE latest_screenshot IS NOT NULL')
            with_screenshots = cursor.fetchone()['with_screenshots']

            conn.close()

            # Get database file size
            db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            db_size_mb = db_size_bytes / (1024 * 1024)

            return {
                'total_bots': total_bots,
                'running_bots': running_bots,
                'stopped_bots': total_bots - running_bots,
                'with_screenshots': with_screenshots,
                'db_size_mb': round(db_size_mb, 2),
                'db_path': db_path
            }

    # ============================================================================
    # REMOTE COMMAND METHODS
    # ============================================================================

    @classmethod
    def send_command(cls, device_name, command_type, command_data=None):
        """Send a remote command to a bot instance

        Args:
            device_name: Target device name
            command_type: Type of command (e.g., "checkbox", "setting", "stop")
            command_data: Optional JSON-serializable command data

        Returns:
            int: Command ID
        """
        import json

        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = conn.cursor()

            data_json = json.dumps(command_data) if command_data else None

            cursor.execute('''
                INSERT INTO remote_commands (device_name, command_type, command_data, created_at)
                VALUES (?, ?, ?, ?)
            ''', (device_name, command_type, data_json, datetime.now()))

            command_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return command_id

    def get_pending_commands(self):
        """Get all pending commands for this device

        Returns:
            list: List of command dictionaries
        """
        import json

        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM remote_commands
                WHERE device_name = ? AND processed = 0
                ORDER BY created_at ASC
            ''', (self.device_name,))

            commands = []
            for row in cursor.fetchall():
                cmd = dict(row)
                if cmd['command_data']:
                    cmd['command_data'] = json.loads(cmd['command_data'])
                commands.append(cmd)

            return commands

    def mark_command_processed(self, command_id):
        """Mark a command as processed

        Args:
            command_id: ID of the command to mark as processed
        """
        with self._db_lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE remote_commands
                SET processed = 1, processed_at = ?
                WHERE id = ?
            ''', (datetime.now(), command_id))

            conn.commit()

    @classmethod
    def clear_old_commands(cls, days=7):
        """Clear processed commands older than specified days

        Args:
            days: Number of days to keep processed commands
        """
        with cls._db_lock:
            db_path = cls._get_db_path()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = conn.cursor()

            cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)

            cursor.execute('''
                DELETE FROM remote_commands
                WHERE processed = 1 AND processed_at < datetime(?, 'unixepoch')
            ''', (cutoff,))

            conn.commit()
            conn.close()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_running_bots_summary():
    """Get a formatted summary of all running bots

    Returns:
        str: Formatted text summary of running bots
    """
    running_bots = StateManager.get_all_running_bots()

    if not running_bots:
        return "No bots currently running"

    lines = [f"Currently running bots: {len(running_bots)}\n"]

    for bot in running_bots:
        device = bot['device_name']
        start_time = bot['start_time']
        last_update = bot['last_update']

        # Count enabled checkboxes
        checkboxes = ['doStreet', 'doArtists', 'doStudio', 'doTour', 'doGroup',
                     'doConcert', 'doHelp', 'doCoin', 'doHeal', 'doRally']
        enabled = [cb for cb in checkboxes if bot[cb] == 1]

        lines.append(f"\n{device}:")
        lines.append(f"  Started: {start_time}")
        lines.append(f"  Last Update: {last_update}")
        lines.append(f"  Enabled: {', '.join(enabled) if enabled else 'None'}")
        lines.append(f"  Settings: sleep={bot['sleep_time']}s, debug={bool(bot['debug_enabled'])}, fix={bool(bot['fix_enabled'])}")

        if bot['current_log']:
            lines.append(f"  Recent Log:")
            for log_line in bot['current_log'].split('\n')[-3:]:
                lines.append(f"    {log_line}")

    return '\n'.join(lines)


if __name__ == '__main__':
    # Demo usage
    print("StateManager Demo\n" + "="*50)

    # Create state manager for a test device
    state = StateManager("TestDevice")

    # Update some checkboxes
    state.update_checkbox_state("doStreet", True)
    state.update_checkbox_state("doGroup", True)

    # Update settings
    state.update_settings(sleep_time=2.5, debug_enabled=True)

    # Add some logs
    state.add_log("Bot started successfully")
    state.add_log("Running street tasks...")
    state.add_log("Collecting coins...")

    # Get all running bots
    print("\n" + get_running_bots_summary())

    # Get database stats
    stats = StateManager.get_database_stats()
    print(f"\nDatabase Stats:")
    print(f"  Total Bots: {stats['total_bots']}")
    print(f"  Running: {stats['running_bots']}")
    print(f"  Stopped: {stats['stopped_bots']}")
    print(f"  Database Size: {stats['db_size_mb']} MB")
    print(f"  Path: {stats['db_path']}")

    # Mark as stopped
    state.mark_stopped()
    print("\nBot marked as stopped")

    # Clean up
    StateManager.clear_device_state("TestDevice")
    print("Test device state cleared")
