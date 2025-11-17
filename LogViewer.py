"""
LogViewer - Standalone debug log viewer for ApexGirl Bot

Three-column browser-style layout:
- Left: Device list
- Middle: Session list
- Right: Log content with auto-loading images
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2 as cv
import numpy as np
from log_database import LogDatabase, get_available_devices, clear_all_devices_logs
from datetime import datetime
from tkinter import messagebox


class LogViewer:
    """Standalone log viewer with browser-style 3-column layout"""

    def __init__(self, root, initial_device=None, initial_session=None):
        """Initialize LogViewer

        Args:
            root: tkinter.Tk root window
            initial_device: Optional device name to select on startup
            initial_session: Optional session ID to select on startup
        """
        self.root = root
        self.root.title("ApexGirl Bot - Log Viewer")

        # Maximize window
        self.root.state('zoomed')  # Windows
        try:
            self.root.attributes('-zoomed', True)  # Linux
        except:
            pass

        # Current selections
        self.selected_device = None
        self.selected_session = None
        self.current_db = None

        # Initial selections from command line
        self.initial_device = initial_device
        self.initial_session = initial_session

        # Virtual scrolling - keep all entries in memory but only render visible ones
        self.all_entries = []  # All log entries from database
        self.rendered_entries = {}  # {index: widget} - Currently rendered entry widgets
        self.entry_widgets = {}  # {index: frame} - Track all entry frames for lazy rendering

        # Image cache for better performance
        self.image_cache = {}  # {entry_id: PIL.ImageTk.PhotoImage}

        # Entry counter for display
        self.entry_counter = 0

        # Virtual scrolling parameters
        self.viewport_buffer = 5  # Number of entries to render before/after visible area

        # Create UI
        self.create_widgets()

        # Load available devices
        self.load_devices()

    def create_widgets(self):
        """Create three-column layout"""
        # Main container with 3 columns
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill="both", expand=True)

        # Left column - Devices (auto-sized to content)
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=0)  # weight=0 means don't expand

        ttk.Label(left_frame, text="Devices", font=("Arial", 11, "bold")).pack(fill="x", padx=10, pady=5)

        # Device listbox
        device_frame = ttk.Frame(left_frame)
        device_frame.pack(fill="both", expand=True, padx=5, pady=5)

        device_scrollbar = ttk.Scrollbar(device_frame)
        device_scrollbar.pack(side="right", fill="y")

        self.device_listbox = tk.Listbox(device_frame, yscrollcommand=device_scrollbar.set,
                                        font=("Arial", 10), activestyle='none', width=15)  # 15 chars wide
        self.device_listbox.pack(side="left", fill="both", expand=True)
        device_scrollbar.config(command=self.device_listbox.yview)

        self.device_listbox.bind('<<ListboxSelect>>', self.on_device_selected)

        # Middle column - Sessions (auto-sized to content)
        middle_frame = ttk.Frame(main_container)
        main_container.add(middle_frame, weight=0)  # weight=0 means don't expand

        ttk.Label(middle_frame, text="Sessions", font=("Arial", 11, "bold")).pack(fill="x", padx=10, pady=5)

        # Session listbox
        session_frame = ttk.Frame(middle_frame)
        session_frame.pack(fill="both", expand=True, padx=5, pady=5)

        session_scrollbar = ttk.Scrollbar(session_frame)
        session_scrollbar.pack(side="right", fill="y")

        self.session_listbox = tk.Listbox(session_frame, yscrollcommand=session_scrollbar.set,
                                         font=("Arial", 9), activestyle='none', width=28)  # 28 chars for "YYYY-MM-DD HH:MM:SS (999)"
        self.session_listbox.pack(side="left", fill="both", expand=True)
        session_scrollbar.config(command=self.session_listbox.yview)

        self.session_listbox.bind('<<ListboxSelect>>', self.on_session_selected)

        # Right column - Log content (takes remaining space)
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=1)  # Gets all remaining space

        # Header with stats and clear buttons
        header_frame = ttk.Frame(right_frame)
        header_frame.pack(fill="x", padx=10, pady=5)

        self.session_info_label = ttk.Label(header_frame, text="Select a session to view logs",
                                           font=("Arial", 10))
        self.session_info_label.pack(side="left")

        # Navigation and clear buttons (right side before stats)
        # Clear All Devices button
        clear_all_button = ttk.Button(header_frame, text="Clear All Logs (All Devices)",
                                      command=self.clear_all_devices_logs)
        clear_all_button.pack(side="right", padx=(5, 0))

        # Clear Current Device button
        self.clear_device_button = ttk.Button(header_frame, text="Clear Current Device",
                                              command=self.clear_current_device,
                                              state='disabled')
        self.clear_device_button.pack(side="right", padx=(5, 0))

        # Clear Current Session button
        self.clear_session_button = ttk.Button(header_frame, text="Clear Current Session",
                                               command=self.clear_current_session,
                                               state='disabled')
        self.clear_session_button.pack(side="right", padx=(5, 0))

        # Go to Bottom button
        self.goto_bottom_button = ttk.Button(header_frame, text="↓ Go to Bottom",
                                            command=self.scroll_to_bottom,
                                            state='disabled')
        self.goto_bottom_button.pack(side="right", padx=(5, 0))

        self.stats_label = ttk.Label(header_frame, text="", font=("Arial", 9), foreground="gray")
        self.stats_label.pack(side="right", padx=(10, 0))

        # Separator
        ttk.Separator(right_frame, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # Scrollable content area - use Text widget to avoid canvas 32K coordinate limit
        content_frame = ttk.Frame(right_frame)
        content_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Text widget can handle unlimited content without coordinate limits
        self.text_widget = tk.Text(content_frame, bg="white", wrap="none",
                                   borderwidth=0, highlightthickness=0,
                                   cursor="arrow")
        content_scrollbar = ttk.Scrollbar(content_frame, orient="vertical",
                                         command=self.text_widget.yview)
        self.text_widget.config(yscrollcommand=content_scrollbar.set)

        # Make text widget read-only by binding events instead of state="disabled"
        self.text_widget.bind("<Key>", lambda e: "break")
        self.text_widget.bind("<Button-1>", lambda e: self.text_widget.focus_set())

        content_scrollbar.pack(side="right", fill="y")
        self.text_widget.pack(side="left", fill="both", expand=True)

        # No container needed - we embed widgets directly in Text widget

        # Configure tags for styling
        self.text_widget.tag_config("header", font=("Courier", 9, "bold"), foreground="blue")
        self.text_widget.tag_config("message", font=("Courier", 8))
        self.text_widget.tag_config("error", font=("Courier", 7), foreground="red")

        # Bind mouse wheel scrolling with smoother multi-line scrolling
        def _on_mousewheel(event):
            # Scroll 3 lines at a time for smoother experience
            scroll_amount = 3
            if event.num == 5 or event.delta < 0:
                self.text_widget.yview_scroll(scroll_amount, "units")
            elif event.num == 4 or event.delta > 0:
                self.text_widget.yview_scroll(-scroll_amount, "units")

        self.text_widget.bind_all("<MouseWheel>", _on_mousewheel)
        self.text_widget.bind_all("<Button-4>", _on_mousewheel)
        self.text_widget.bind_all("<Button-5>", _on_mousewheel)

        # Status bar
        self.status_var = tk.StringVar(value="Ready. Select a device to begin.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom", padx=5, pady=2)

    def load_devices(self):
        """Load available devices into left column"""
        devices = get_available_devices()

        self.device_listbox.delete(0, tk.END)

        if devices:
            for device in devices:
                self.device_listbox.insert(tk.END, device)
            self.status_var.set(f"Found {len(devices)} device(s). Select a device to view sessions.")

            # Auto-select initial device if specified
            if self.initial_device and self.initial_device in devices:
                idx = devices.index(self.initial_device)
                self.device_listbox.selection_set(idx)
                self.device_listbox.see(idx)
                # Trigger selection event after a short delay to ensure UI is ready
                self.root.after(100, lambda: self.on_device_selected(None))
        else:
            self.status_var.set("No device logs found. Run the bot with Debug mode to generate logs.")

    def on_device_selected(self, _):
        """Handle device selection from left column"""
        selection = self.device_listbox.curselection()
        if not selection:
            return

        self.selected_device = self.device_listbox.get(selection[0])

        # Close previous database if open
        if self.current_db:
            self.current_db.close()

        # Open database for selected device in read-only mode (prevents creating empty sessions)
        self.current_db = LogDatabase(self.selected_device, read_only=True)

        # Load sessions for this device
        self.load_sessions()

        # Clear content area
        self.clear_content()
        self.session_info_label.config(text="Select a session to view logs")
        self.stats_label.config(text="")

        # Enable Clear Current Device button, disable Clear Current Session
        self.clear_device_button.config(state='normal')
        self.clear_session_button.config(state='disabled')

    def load_sessions(self):
        """Load sessions into middle column"""
        if not self.current_db:
            return

        self.session_listbox.delete(0, tk.END)

        sessions = self.current_db.get_sessions()

        if sessions:
            self.sessions_data = sessions

            for session in sessions:
                start = datetime.fromisoformat(session['start_time'])
                date_str = start.strftime("%Y-%m-%d")
                time_str = start.strftime("%H:%M:%S")
                entry_count = session['entry_count']

                # Format: "Date Time (count entries)"
                display = f"{date_str} {time_str} ({entry_count})"
                self.session_listbox.insert(tk.END, display)

            self.status_var.set(f"{self.selected_device}: {len(sessions)} session(s) available")

            # Auto-select initial session if specified
            if self.initial_session:
                # Find session by ID
                session_ids = [s['session_id'] for s in sessions]
                if self.initial_session in session_ids:
                    idx = session_ids.index(self.initial_session)
                    self.session_listbox.selection_set(idx)
                    self.session_listbox.see(idx)
                    # Trigger selection event after a short delay
                    self.root.after(100, lambda: self.on_session_selected(None))
                else:
                    # Session not found, select the most recent (last in list)
                    idx = len(sessions) - 1
                    self.session_listbox.selection_set(idx)
                    self.session_listbox.see(idx)
                    self.root.after(100, lambda: self.on_session_selected(None))
                # Clear initial_session so it doesn't get reapplied
                self.initial_session = None
        else:
            self.status_var.set(f"No sessions found for {self.selected_device}")

    def on_session_selected(self, _):
        """Handle session selection from middle column - auto-load content"""
        selection = self.session_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        self.selected_session = self.sessions_data[idx]['session_id']

        # Enable Clear Current Session button
        self.clear_session_button.config(state='normal')

        # Auto-load the session
        self.load_session()

    def load_session(self):
        """Load and display the selected session in right column"""
        if not self.selected_session or not self.current_db:
            return

        # Clear existing content
        self.clear_content()

        try:
            # Get session info
            session_info = next((s for s in self.sessions_data if s['session_id'] == self.selected_session), None)

            if session_info:
                start = datetime.fromisoformat(session_info['start_time']).strftime("%Y-%m-%d %H:%M:%S")
                self.session_info_label.config(text=f"Session {self.selected_session} - {start}")

                # Get database stats
                stats = self.current_db.get_database_stats()
                self.stats_label.config(text=f"DB: {stats['db_size_mb']} MB")

            # Get log entries WITH screenshots (eager loading for better performance)
            entries = self.current_db.get_log_entries(self.selected_session, include_screenshots=True)

            self.status_var.set(f"Loading {len(entries)} entries...")
            self.root.update()

            # Load all entries in batches for better perceived performance
            self._load_entries_batched(entries)

            # Enable Go to Bottom button
            self.goto_bottom_button.config(state='normal')

            self.status_var.set(f"Loaded session {self.selected_session}: {len(entries)} entries")

        except Exception as e:
            self.status_var.set(f"Error loading session: {e}")

    def _load_entries_batched(self, entries, batch_size=30):
        """Load entries in batches to keep UI responsive

        Args:
            entries: List of log entries to display
            batch_size: Number of entries to load per batch (default: 30)
        """
        total = len(entries)
        batches = [entries[i:i + batch_size] for i in range(0, total, batch_size)]

        # Reset entry counter
        self.entry_counter = 0

        def load_batch(batch_index):
            try:
                if batch_index >= len(batches):
                    # All batches loaded - ensure final scroll region update
                    print(f"All batches loaded! Total entries: {total}")
                    self._finalize_loading(total)
                    return

                # Load this batch
                batch = batches[batch_index]
                print(f"Loading batch {batch_index + 1}/{len(batches)} ({len(batch)} entries)")

                for entry in batch:
                    self.entry_counter += 1
                    self.add_log_entry_optimized(entry, self.entry_counter)

                # Update progress
                loaded = min((batch_index + 1) * batch_size, total)
                self.status_var.set(f"Loading entries: {loaded}/{total}")

                # Force text widget to update
                self.text_widget.update_idletasks()
                self.root.update()

                # Schedule next batch with minimal delay (10ms for stability)
                self.root.after(10, load_batch, batch_index + 1)

            except Exception as e:
                print(f"FATAL ERROR in load_batch at batch {batch_index}: {e}")
                import traceback
                traceback.print_exc()
                self.status_var.set(f"ERROR at batch {batch_index}: {e}")

        # Start loading batches
        load_batch(0)

    def _finalize_loading(self, total):
        """Finalize loading

        Args:
            total: Total number of entries loaded
        """
        print(f"FINAL: Loaded all {total} entries successfully")
        self.status_var.set(f"Loaded session {self.selected_session}: {total} entries")

    def clear_content(self):
        """Clear the content area"""
        # Delete all content
        self.text_widget.delete("1.0", "end")

        self.image_cache.clear()  # Clear image cache
        self.all_entries.clear()

        # Disable Go to Bottom button when content is cleared
        self.goto_bottom_button.config(state='disabled')

    def add_log_entry_optimized(self, entry, entry_number=None):
        """Add a log entry to the Text widget with embedded windows

        Args:
            entry: Dictionary with entry data from database (includes screenshot blob)
            entry_number: Sequential entry number for display
        """
        try:
            # Add entry counter and timestamp
            timestamp = entry['timestamp_ms']
            if entry_number:
                header_text = f"[#{entry_number}] [{timestamp}]\n"
            else:
                header_text = f"[{timestamp}]\n"

            self.text_widget.insert("end", header_text, "header")

            # Add message text
            message = entry['message']
            self.text_widget.insert("end", f"{message}\n", "message")

            # Check if has screenshot blob
            screenshot_blob = entry.get('screenshot')
            if screenshot_blob:
                entry_id = entry['entry_id']

                # Decode and display image immediately
                try:
                    # Decode PNG bytes back to numpy array
                    nparr = np.frombuffer(screenshot_blob, np.uint8)
                    img = cv.imdecode(nparr, cv.IMREAD_UNCHANGED)

                    if img is not None:
                        # Convert and create PhotoImage
                        photo = self._create_photoimage(img, entry_id)

                        if photo:
                            # Create label with image
                            img_label = tk.Label(self.text_widget, image=photo, bg="white")

                            # Embed the label in the text widget
                            self.text_widget.window_create("end", window=img_label)
                            self.text_widget.insert("end", "\n")
                        else:
                            print(f"WARNING: Failed to create PhotoImage for entry #{entry_number}")
                            self.text_widget.insert("end", f"[Image error for entry #{entry_number}]\n", "error")
                    else:
                        # Image decode failed
                        print(f"ERROR: cv.imdecode returned None for entry #{entry_number}")
                        self.text_widget.insert("end", f"[Entry #{entry_number}: Image decode failed]\n", "error")

                except Exception as e:
                    # Show error if image fails to load
                    print(f"ERROR loading image for entry #{entry_number}: {e}")
                    self.text_widget.insert("end", f"[Entry #{entry_number}: Image error: {e}]\n", "error")

            # Add separator
            self.text_widget.insert("end", "-" * 80 + "\n")

        except Exception as e:
            # Catch-all for any errors
            print(f"ERROR creating entry #{entry_number}: {e}")
            import traceback
            traceback.print_exc()

            try:
                self.text_widget.insert("end", f"[FATAL ERROR Entry #{entry_number}: {e}]\n", "error")
            except:
                pass

    def _create_photoimage(self, screenshot, entry_id):
        """Convert numpy array screenshot to PhotoImage

        Args:
            screenshot: Numpy array (BGR/BGRA format)
            entry_id: Entry ID for caching

        Returns:
            PIL.ImageTk.PhotoImage or None on error
        """
        try:
            # Convert BGR/BGRA to RGB for PIL
            if screenshot.shape[2] == 4:  # BGRA
                img_rgb = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGB)
            else:  # BGR
                img_rgb = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

            # Convert to PIL Image
            img = Image.fromarray(img_rgb)

            # Resize to reasonable size (400px for better visibility)
            max_display_width = 400
            aspect_ratio = img.height / img.width

            if img.width > max_display_width:
                new_width = max_display_width
                new_height = int(new_width * aspect_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)

            # Convert to PhotoImage and cache it
            photo = ImageTk.PhotoImage(img)
            self.image_cache[entry_id] = photo

            return photo

        except Exception as e:
            print(f"ERROR creating PhotoImage for entry {entry_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def add_inline_image_optimized(self, parent_frame, screenshot, entry_id):
        """Add an image inline with caching for better performance

        Args:
            parent_frame: Parent frame to add image to
            screenshot: Numpy array (BGR/BGRA format)
            entry_id: Entry ID for caching

        Returns:
            tk.Label: The image label widget (or None on error)
        """
        try:
            # Convert BGR/BGRA to RGB for PIL
            if screenshot.shape[2] == 4:  # BGRA
                img_rgb = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGB)
            else:  # BGR
                img_rgb = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

            # Convert to PIL Image
            img = Image.fromarray(img_rgb)

            # Resize to micro thumbnail (max 60px wide to stay under 32K canvas limit)
            # Need to keep total canvas height under 32,767 pixels (Tkinter limit)
            # Target: ~125 pixels per entry max, 254 entries = ~31K pixels total
            max_display_width = 60
            aspect_ratio = img.height / img.width

            if img.width > max_display_width:
                new_width = max_display_width
                new_height = int(new_width * aspect_ratio)
                # Use BILINEAR for faster/smaller images
                img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)

            # Convert to PhotoImage and cache it
            photo = ImageTk.PhotoImage(img)
            self.image_cache[entry_id] = photo

            # Create label with the image
            label = ttk.Label(parent_frame, image=photo)
            label.pack()

            return label

        except Exception as e:
            # Show detailed error with traceback
            print(f"ERROR creating PhotoImage for entry {entry_id}: {e}")
            import traceback
            traceback.print_exc()

            error_label = ttk.Label(parent_frame, text=f"[Image error entry {entry_id}: {e}]",
                                   font=("Courier", 8), foreground="red")
            error_label.pack()
            return None

    def scroll_to_bottom(self):
        """Scroll to the bottom of the log content"""
        # For Text widget, just scroll to end
        self.text_widget.see("end")

    def clear_current_session(self):
        """Clear the currently selected session"""
        if not self.selected_session or not self.current_db:
            messagebox.showwarning("Clear Session", "No session selected.")
            return

        # Get session info for display
        session_info = next((s for s in self.sessions_data if s['session_id'] == self.selected_session), None)
        if not session_info:
            return

        start = datetime.fromisoformat(session_info['start_time']).strftime("%Y-%m-%d %H:%M:%S")
        entry_count = session_info['entry_count']

        # Confirmation dialog
        result = messagebox.askyesno(
            "Clear Current Session",
            f"This will permanently delete session:\n\n"
            f"Session ID: {self.selected_session}\n"
            f"Started: {start}\n"
            f"Entries: {entry_count}\n\n"
            f"This includes all log entries and screenshots for this session.\n\n"
            f"This cannot be undone. Continue?",
            icon='warning'
        )

        if not result:
            return

        try:
            self.status_var.set(f"Clearing session {self.selected_session}...")
            self.root.update()

            # Clear from database
            self.current_db.clear_session(self.selected_session)

            # Clear UI
            self.clear_content()

            # Reload sessions list
            self.load_sessions()

            # Reset selection
            self.selected_session = None
            self.session_info_label.config(text="Session cleared. Select another session.")
            self.stats_label.config(text="")

            # Disable Clear Current Session button
            self.clear_session_button.config(state='disabled')

            messagebox.showinfo("Clear Session", f"Session {self.selected_session} has been cleared.")
            self.status_var.set(f"Cleared session {self.selected_session}")

        except Exception as e:
            messagebox.showerror("Error", f"Error clearing session: {e}")
            self.status_var.set(f"Error clearing session: {e}")

    def clear_current_device(self):
        """Clear all logs for the currently selected device"""
        if not self.selected_device or not self.current_db:
            messagebox.showwarning("Clear Device", "No device selected.")
            return

        # Get device stats
        sessions = self.current_db.get_sessions()
        session_count = len(sessions)
        total_entries = sum(s['entry_count'] for s in sessions)

        # Confirmation dialog
        result = messagebox.askyesno(
            "Clear Current Device",
            f"This will permanently delete ALL logs for device:\n\n"
            f"Device: {self.selected_device}\n"
            f"Sessions: {session_count}\n"
            f"Total entries: {total_entries}\n\n"
            f"This includes:\n"
            f"• All sessions for this device\n"
            f"• All log entries\n"
            f"• All screenshots\n\n"
            f"This cannot be undone. Continue?",
            icon='warning'
        )

        if not result:
            return

        try:
            self.status_var.set(f"Clearing device {self.selected_device}...")
            self.root.update()

            # Clear from database
            self.current_db.clear_device(self.selected_device)

            # Close database
            self.current_db.close()
            self.current_db = None

            # Clear UI
            self.clear_content()
            self.session_listbox.delete(0, tk.END)

            # Reset selections
            self.selected_session = None
            self.session_info_label.config(text="Device cleared. Select another device.")
            self.stats_label.config(text="")

            # Disable buttons
            self.clear_device_button.config(state='disabled')
            self.clear_session_button.config(state='disabled')

            # Reload device list
            self.load_devices()

            messagebox.showinfo("Clear Device", f"All logs for device '{self.selected_device}' have been cleared.")
            self.status_var.set(f"Cleared device {self.selected_device}")

            # Reset device selection
            self.selected_device = None

        except Exception as e:
            messagebox.showerror("Error", f"Error clearing device: {e}")
            self.status_var.set(f"Error clearing device: {e}")

    def clear_all_devices_logs(self):
        """Clear all logs from all devices with confirmation dialog"""
        # Get list of devices
        devices = get_available_devices()

        if not devices:
            messagebox.showinfo("Clear All Logs", "No device logs found to clear.")
            return

        # Show strong warning with device list
        device_list = "\n".join([f"  • {device}" for device in devices])

        result = messagebox.askyesno(
            "Clear All Logs - ALL DEVICES",
            f"WARNING: This will permanently delete ALL logs from ALL {len(devices)} device(s):\n\n"
            f"{device_list}\n\n"
            f"This includes:\n"
            f"• All sessions for all devices\n"
            f"• All log entries\n"
            f"• All screenshots\n\n"
            f"THIS CANNOT BE UNDONE!\n\n"
            f"Are you absolutely sure you want to delete everything?",
            icon='warning'
        )

        if not result:
            return

        # Perform the clear operation
        try:
            self.status_var.set("Clearing all logs from all devices...")
            self.root.update()

            cleared_count = clear_all_devices_logs()

            # Close current database connection if open
            if self.current_db:
                self.current_db.close()
                self.current_db = None

            # Clear UI
            self.clear_content()
            self.session_listbox.delete(0, tk.END)
            self.device_listbox.delete(0, tk.END)

            # Reload devices (should be empty or have new sessions)
            self.load_devices()

            # Update UI
            self.session_info_label.config(text="All logs cleared")
            self.stats_label.config(text="")
            self.selected_device = None
            self.selected_session = None

            messagebox.showinfo(
                "Clear All Logs Complete",
                f"Successfully cleared logs from {cleared_count} device(s).\n\n"
                f"All sessions, log entries, and screenshots have been permanently deleted."
            )

            self.status_var.set(f"Cleared all logs from {cleared_count} device(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Error clearing logs: {e}")
            self.status_var.set(f"Error clearing logs: {e}")

    def add_inline_image(self, parent_frame, screenshot):
        """Add an image inline from numpy array

        Args:
            parent_frame: Parent frame to add image to
            screenshot: Numpy array (BGR/BGRA format)

        Returns:
            tk.Label: The image label widget (or None on error)
        """
        try:
            # Convert BGR/BGRA to RGB for PIL
            if screenshot.shape[2] == 4:  # BGRA
                img_rgb = cv.cvtColor(screenshot, cv.COLOR_BGRA2RGB)
            else:  # BGR
                img_rgb = cv.cvtColor(screenshot, cv.COLOR_BGR2RGB)

            # Convert to PIL Image
            img = Image.fromarray(img_rgb)

            # Resize to fit (max 900px wide for right column)
            max_display_width = 900
            aspect_ratio = img.height / img.width

            if img.width > max_display_width:
                display_width = max_display_width
                display_height = int(display_width * aspect_ratio)
            else:
                display_width = img.width
                display_height = img.height

            # Limit height
            max_height = 600
            if display_height > max_height:
                display_height = max_height
                display_width = int(display_height / aspect_ratio)

            img_resized = img.resize((display_width, display_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img_resized)

            # Add image label
            img_label = tk.Label(parent_frame, image=photo, bg="black")
            img_label.image = photo  # Keep reference
            img_label.pack()

            return img_label

        except Exception as e:
            error_label = ttk.Label(parent_frame, text=f"[Image load error: {e}]",
                                   font=("Courier", 7), foreground="red")
            error_label.pack(anchor="w")
            return None


def main():
    """Main entry point"""
    import sys

    # Parse command line arguments
    initial_device = None
    initial_session = None

    if len(sys.argv) >= 2:
        initial_device = sys.argv[1]

    if len(sys.argv) >= 3:
        try:
            initial_session = int(sys.argv[2])
        except ValueError:
            print(f"Warning: Invalid session ID '{sys.argv[2]}', ignoring")

    root = tk.Tk()
    app = LogViewer(root, initial_device=initial_device, initial_session=initial_session)
    root.mainloop()


if __name__ == "__main__":
    main()
