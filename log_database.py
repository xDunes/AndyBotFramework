"""
Database-backed logging system for ApexGirl Bot

Uses SQLite to store log entries and screenshots efficiently.
No additional installation required - SQLite comes with Python.
"""

import sqlite3
import os
from datetime import datetime
import cv2 as cv


class LogDatabase:
    """SQLite database for storing bot logs and screenshots"""

    def __init__(self, device_name, read_only=False):
        """Initialize database connection for a device

        Args:
            device_name: Device/user name for log organization
            read_only: If True, don't create a new session (for viewing only)

        Note:
            Creates database at logs/device_name/logs.db
            One database per device for organization
            Use read_only=True for LogViewer to prevent empty sessions
        """
        self.device_name = device_name
        self.read_only = read_only

        # Create logs directory structure
        self.logs_dir = os.path.join(os.path.dirname(__file__), 'logs', device_name)
        os.makedirs(self.logs_dir, exist_ok=True)

        # Database file path
        self.db_path = os.path.join(self.logs_dir, 'logs.db')

        # Connect to database
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Initialize schema
        self._init_schema()

        # Current session ID (only create if not read-only)
        if read_only:
            self.session_id = None
        else:
            self.session_id = self._create_session()

    def _init_schema(self):
        """Initialize database schema if not exists"""
        cursor = self.conn.cursor()

        # Sessions table - tracks each bot run
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP
            )
        ''')

        # Log entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                timestamp_ms TEXT NOT NULL,
                message TEXT NOT NULL,
                screenshot BLOB,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        ''')

        # Create indices for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session_id
            ON log_entries(session_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON log_entries(timestamp)
        ''')

        self.conn.commit()

    def _create_session(self):
        """Create a new session for this bot run

        Returns:
            int: New session ID
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (device_name, start_time)
            VALUES (?, ?)
        ''', (self.device_name, datetime.now()))

        self.conn.commit()
        return cursor.lastrowid

    def add_log_entry(self, message, screenshot=None):
        """Add a log entry to the database

        Args:
            message: Log message text
            screenshot: Optional screenshot numpy array (BGR/BGRA format)

        Returns:
            int: Entry ID of inserted log
        """
        cursor = self.conn.cursor()

        now = datetime.now()
        timestamp = now
        timestamp_ms = now.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.sss

        # Convert screenshot to PNG bytes if provided
        screenshot_blob = None
        if screenshot is not None:
            # Encode screenshot as PNG
            success, encoded = cv.imencode('.png', screenshot)
            if success:
                screenshot_blob = encoded.tobytes()

        cursor.execute('''
            INSERT INTO log_entries (session_id, timestamp, timestamp_ms, message, screenshot)
            VALUES (?, ?, ?, ?, ?)
        ''', (self.session_id, timestamp, timestamp_ms, message, screenshot_blob))

        self.conn.commit()
        return cursor.lastrowid

    def get_sessions(self):
        """Get all sessions for this device

        Returns:
            list: List of session dictionaries with session info
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT session_id, start_time, end_time,
                   (SELECT COUNT(*) FROM log_entries WHERE session_id = sessions.session_id) as entry_count
            FROM sessions
            WHERE device_name = ?
            ORDER BY start_time DESC
        ''', (self.device_name,))

        return [dict(row) for row in cursor.fetchall()]

    def get_log_entries(self, session_id, include_screenshots=True):
        """Get all log entries for a session

        Args:
            session_id: Session ID to retrieve logs for
            include_screenshots: If False, excludes screenshot BLOBs for faster loading

        Returns:
            list: List of log entry dictionaries
        """
        cursor = self.conn.cursor()

        if include_screenshots:
            cursor.execute('''
                SELECT entry_id, timestamp, timestamp_ms, message, screenshot
                FROM log_entries
                WHERE session_id = ?
                ORDER BY timestamp ASC
            ''', (session_id,))
        else:
            cursor.execute('''
                SELECT entry_id, timestamp, timestamp_ms, message,
                       CASE WHEN screenshot IS NOT NULL THEN 1 ELSE 0 END as has_screenshot
                FROM log_entries
                WHERE session_id = ?
                ORDER BY timestamp ASC
            ''', (session_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_screenshot(self, entry_id):
        """Get screenshot for a specific log entry

        Args:
            entry_id: Entry ID to get screenshot for

        Returns:
            numpy.ndarray or None: Screenshot image or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT screenshot FROM log_entries WHERE entry_id = ?', (entry_id,))

        row = cursor.fetchone()
        if row and row['screenshot']:
            # Decode PNG bytes back to numpy array
            import numpy as np
            nparr = np.frombuffer(row['screenshot'], np.uint8)
            img = cv.imdecode(nparr, cv.IMREAD_UNCHANGED)
            return img

        return None

    def close_session(self):
        """Mark current session as ended"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE sessions
            SET end_time = ?
            WHERE session_id = ?
        ''', (datetime.now(), self.session_id))
        self.conn.commit()

    def clear_current_session(self):
        """Delete all log entries for the current session

        This clears the current session's logs from the database.
        Use this to clear visible logs in the current bot run.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM log_entries
            WHERE session_id = ?
        ''', (self.session_id,))
        self.conn.commit()

    def clear_session(self, session_id):
        """Delete all log entries for a specific session

        Args:
            session_id: Session ID to clear

        This removes all log entries for the specified session
        and deletes the session record itself.
        """
        cursor = self.conn.cursor()

        # Delete all log entries for this session
        cursor.execute('''
            DELETE FROM log_entries
            WHERE session_id = ?
        ''', (session_id,))

        # Delete the session record
        cursor.execute('''
            DELETE FROM sessions
            WHERE session_id = ?
        ''', (session_id,))

        self.conn.commit()

    def clear_device(self, device_name):
        """Delete all log entries and sessions for a specific device

        Args:
            device_name: Device name to clear

        This removes all logs and sessions associated with the specified device.
        """
        cursor = self.conn.cursor()

        # Delete all log entries for this device
        cursor.execute('''
            DELETE FROM log_entries
            WHERE session_id IN (
                SELECT session_id FROM sessions WHERE device_name = ?
            )
        ''', (device_name,))

        # Delete all sessions for this device
        cursor.execute('''
            DELETE FROM sessions
            WHERE device_name = ?
        ''', (device_name,))

        self.conn.commit()

    def clear_all_logs(self):
        """Delete all log entries for this device from all sessions

        This removes all logs associated with this device,
        including all sessions and their log entries.
        Use with caution - this cannot be undone!
        """
        cursor = self.conn.cursor()

        # Delete all log entries for this device
        cursor.execute('''
            DELETE FROM log_entries
            WHERE session_id IN (
                SELECT session_id FROM sessions WHERE device_name = ?
            )
        ''', (self.device_name,))

        # Delete all sessions for this device
        cursor.execute('''
            DELETE FROM sessions
            WHERE device_name = ?
        ''', (self.device_name,))

        self.conn.commit()

        # Recreate the current session after clearing
        self.session_id = self._create_session()

    def close(self):
        """Close database connection"""
        self.close_session()
        self.conn.close()

    def get_database_stats(self):
        """Get statistics about the database

        Returns:
            dict: Statistics including size, entry count, etc.
        """
        cursor = self.conn.cursor()

        # Get counts
        cursor.execute('SELECT COUNT(*) as session_count FROM sessions WHERE device_name = ?',
                      (self.device_name,))
        session_count = cursor.fetchone()['session_count']

        cursor.execute('SELECT COUNT(*) as entry_count FROM log_entries')
        entry_count = cursor.fetchone()['entry_count']

        cursor.execute('''
            SELECT COUNT(*) as screenshot_count
            FROM log_entries
            WHERE screenshot IS NOT NULL
        ''')
        screenshot_count = cursor.fetchone()['screenshot_count']

        # Get database file size
        db_size_bytes = os.path.getsize(self.db_path)
        db_size_mb = db_size_bytes / (1024 * 1024)

        return {
            'session_count': session_count,
            'entry_count': entry_count,
            'screenshot_count': screenshot_count,
            'db_size_mb': round(db_size_mb, 2),
            'db_path': self.db_path
        }


def get_available_devices():
    """Get list of devices with log databases

    Returns:
        list: List of device names that have log databases
    """
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(logs_dir):
        return []

    devices = []
    for device_name in os.listdir(logs_dir):
        device_path = os.path.join(logs_dir, device_name)
        if os.path.isdir(device_path):
            db_path = os.path.join(device_path, 'logs.db')
            if os.path.exists(db_path):
                devices.append(device_name)

    return devices


def clear_all_devices_logs():
    """Clear all logs from all devices

    This is a standalone function that clears all logs from all devices.
    Opens each device's database, clears all data, and closes it.
    Use with extreme caution - this deletes ALL logs from ALL devices!

    Returns:
        int: Number of devices cleared
    """
    devices = get_available_devices()
    cleared_count = 0

    for device_name in devices:
        try:
            # Open database for this device in read-only mode (we'll delete everything anyway)
            db = LogDatabase(device_name, read_only=True)

            # Clear all logs for this device
            cursor = db.conn.cursor()

            # Delete all log entries
            cursor.execute('DELETE FROM log_entries')

            # Delete all sessions
            cursor.execute('DELETE FROM sessions')

            db.conn.commit()

            # Close database (no need to recreate session since we're just clearing)
            db.close()

            cleared_count += 1

        except Exception as e:
            print(f"Error clearing logs for device {device_name}: {e}")
            continue

    return cleared_count
