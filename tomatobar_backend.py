#!/usr/bin/env python3
"""
Tomatobar Timer Backend
This script implements the core Pomodoro timer logic, state transitions,
and data persistence for the Tomatobar Timer.
"""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
import threading
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='tomatobar.log'
)
logger = logging.getLogger('tomatobar_backend')

class PomodoroState(Enum):
    """Enum representing the different states of the Pomodoro timer."""
    IDLE = auto()
    WORK = auto()
    SHORT_BREAK = auto()
    LONG_BREAK = auto()
    PAUSED = auto()

class PomodoroTimer:
    """Main Pomodoro Timer class handling timer logic and state transitions."""
    
    def __init__(self):
        """Initialize the Pomodoro Timer with default settings."""
        self.config = self._load_config()
        self.db_conn = self._setup_database()
        
        # State variables
        self.current_state = PomodoroState.IDLE
        self.time_remaining_seconds = 0
        self.pomodoros_completed_in_cycle = 0
        self.session_start_timestamp = None
        self.paused_time_remaining = 0
        self.running = True
        
        # Create and setup FIFOs
        self._setup_fifos()
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)
        
        logger.info("Tomatobar Timer initialized")

    def _load_config(self):
        """
        Load configuration from the config file.
        If the config file doesn't exist, create it with default values.
        """
        config_dir = os.path.expanduser("~/.config/tomatobar")
        config_path = os.path.join(config_dir, "config.json")
        
        # If the config directory doesn't exist in the user's home, check the project directory
        if not os.path.exists(config_dir):
            project_config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "config", 
                "tomatobar",
                "config.json"
            )
            if os.path.exists(project_config_path):
                with open(project_config_path, 'r') as f:
                    return json.load(f)
        
        # If we got here, try the user's config or create it with defaults
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                # Default configuration
                default_config = {
                    "work_duration_minutes": 25,
                    "short_break_duration_minutes": 5,
                    "long_break_duration_minutes": 15,
                    "pomodoros_before_long_break": 4,
                    "notification_sound_work_end": "",
                    "notification_sound_break_end": "",
                    "db_path": "~/.local/share/tomatobar/stats.db",
                    "status_file_path": "/tmp/tomatobar-status.json",
                    "fifo_path_commands": "/tmp/tomatobar-commands"
                }
                
                # Create the config directory if it doesn't exist
                os.makedirs(config_dir, exist_ok=True)
                
                # Write the default config
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
                
                return default_config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)

    def _setup_database(self):
        """
        Set up the SQLite database for storing Pomodoro sessions.
        Creates the database file and sessions table if they don't exist.
        """
        db_path = os.path.expanduser(self.config["db_path"])
        db_dir = os.path.dirname(db_path)
        
        # Create the database directory if it doesn't exist
        os.makedirs(db_dir, exist_ok=True)
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create the sessions table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time INTEGER,
                end_time INTEGER,
                type TEXT,
                completed BOOLEAN,
                duration_actual_seconds INTEGER,
                pomodoro_count_at_completion INTEGER
            )
            ''')
            
            conn.commit()
            logger.info(f"Database setup complete: {db_path}")
            return conn
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            sys.exit(1)

    def _setup_fifos(self):
        """
        Set up the FIFO pipes for communication with the Waybar module.
        Creates the FIFOs if they don't exist.
        """
        self.status_file_path = self.config["status_file_path"]
        self.fifo_path_commands = self.config["fifo_path_commands"]
        
        # Ensure the command FIFO exist
        try:
            if not os.path.exists(self.fifo_path_commands):
                os.mkfifo(self.fifo_path_commands, 0o600)
            
            logger.info("Command FIFO and status file path setup complete")
        except Exception as e:
            logger.error(f"Error setting up command FIFO: {e}")
            sys.exit(1)
        
        # Start the command listener thread
        threading.Thread(target=self._command_listener, daemon=True).start()

    def _command_listener(self):
        """
        Listen for commands from the command FIFO pipe.
        This runs in a separate thread to avoid blocking the main loop.
        """
        logger.info("Command listener started")
        while self.running:
            try:
                # Open the FIFO in read mode (blocking)
                with open(self.fifo_path_commands, 'r') as fifo:
                    while self.running:
                        raw_command = fifo.readline()
                        if not raw_command and not self.running: # EOF and shutting down
                            break
                        logger.debug(f"Raw command read from FIFO: '{raw_command.encode('utf-8').hex()}' (len: {len(raw_command)})")
                        command = raw_command.strip()
                        if command:
                            logger.info(f"Received command: {command}")
                            self._process_command(command)
                        elif raw_command: # Non-empty but stripped to empty (e.g. just newline)
                            logger.debug(f"Command stripped to empty, was: '{raw_command.encode('utf-8').hex()}'")
            except Exception as e:
                logger.error(f"Error in command listener: {e}")
                time.sleep(1)  # Wait a bit before trying again

    def _process_command(self, command):
        """Process a command received from the command FIFO pipe."""
        if command == "start":
            # Start a new work session if we're idle
            if self.current_state == PomodoroState.IDLE:
                self._start_work_session()
            # Resume if paused
            elif self.current_state == PomodoroState.PAUSED:
                self._resume()
        elif command == "pause":
            if self.current_state in [PomodoroState.WORK, PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK]:
                self._pause()
        elif command == "resume":
            if self.current_state == PomodoroState.PAUSED:
                self._resume()
        elif command == "skip":
            if self.current_state in [PomodoroState.WORK, PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK]:
                self._skip_current_phase()
        elif command == "reset":
            self._reset()
        elif command == "restart_cycle":
            self._restart_cycle()
        elif command == "get_status":
            self._write_status()
        else:
            logger.warning(f"Unknown command: {command}")

    def _write_status(self):
        """Write the current status to the status file."""
        try:
            state_map = {
                PomodoroState.IDLE: "idle",
                PomodoroState.WORK: "work",
                PomodoroState.SHORT_BREAK: "short_break",
                PomodoroState.LONG_BREAK: "long_break",
                PomodoroState.PAUSED: "paused"
            }
            
            minutes, seconds = divmod(self.time_remaining_seconds, 60)
            time_string = f"{minutes:02d}:{seconds:02d}"
            
            message = ""
            if self.current_state == PomodoroState.WORK:
                message = f"Work: {time_string}"
            elif self.current_state == PomodoroState.SHORT_BREAK:
                message = f"Break: {time_string}"
            elif self.current_state == PomodoroState.LONG_BREAK:
                message = f"Long Break: {time_string}"
            elif self.current_state == PomodoroState.PAUSED:
                if self.paused_state == PomodoroState.WORK:
                    message = f"Paused Work: {time_string}"
                elif self.paused_state == PomodoroState.SHORT_BREAK:
                    message = f"Paused Break: {time_string}"
                elif self.paused_state == PomodoroState.LONG_BREAK:
                    message = f"Paused Long Break: {time_string}"
            else:  # IDLE
                message = "Ready"
            
            status = {
                "state": state_map[self.current_state],
                "time_remaining": self.time_remaining_seconds,
                "pomodoros_completed": self.pomodoros_completed_in_cycle,
                "total_pomodoros_for_long_break": self.config["pomodoros_before_long_break"],
                "message": message
            }
            
            # Prepare the full JSON string
            status_json_string = json.dumps(status)
            with open(self.status_file_path, 'w') as f:
                f.write(status_json_string)
            # logger.debug(f"Status written to {self.status_file_path}: {status_json_string}")
        except Exception as e:
            # Unexpected errors during status write
            logger.error(f"Unexpected error writing status to {self.status_file_path}: {e}")

    def _start_work_session(self):
        """Start a new work session."""
        self.current_state = PomodoroState.WORK
        self.time_remaining_seconds = self.config["work_duration_minutes"] * 60
        self.session_start_timestamp = int(time.time())
        self._write_status()
        logger.info("Started work session")
        
    def _start_break(self, is_long_break=False):
        """Start a break session."""
        if is_long_break:
            self.current_state = PomodoroState.LONG_BREAK
            self.time_remaining_seconds = self.config["long_break_duration_minutes"] * 60
            logger.info("Started long break")
        else:
            self.current_state = PomodoroState.SHORT_BREAK
            self.time_remaining_seconds = self.config["short_break_duration_minutes"] * 60
            logger.info("Started short break")
        
        self.session_start_timestamp = int(time.time())
        self._write_status()
        
    def _pause(self):
        """Pause the current session."""
        if self.current_state != PomodoroState.PAUSED:
            self.paused_state = self.current_state
            self.paused_time_remaining = self.time_remaining_seconds
            self.current_state = PomodoroState.PAUSED
            
            # Log the session up to this point
            self._log_session(completed=False)
            
            self._write_status()
            logger.info("Paused session")
            
    def _resume(self):
        """Resume a paused session."""
        if self.current_state == PomodoroState.PAUSED:
            self.current_state = self.paused_state
            self.time_remaining_seconds = self.paused_time_remaining
            self.session_start_timestamp = int(time.time())
            self._write_status()
            logger.info("Resumed session")
            
    def _skip_current_phase(self):
        """Skip the current phase."""
        # Log the current session as incomplete
        self._log_session(completed=False)
        
        # Move to the next phase
        if self.current_state == PomodoroState.WORK:
            self._complete_work_session(was_skipped=True)
        else:  # It was a break
            self._start_work_session()
            
        logger.info("Skipped current phase")
            
    def _reset(self):
        """Reset the timer to idle state."""
        # If we're not already idle, log the current session as incomplete
        if self.current_state != PomodoroState.IDLE:
            self._log_session(completed=False)
            
        self.current_state = PomodoroState.IDLE
        self.time_remaining_seconds = 0
        self.session_start_timestamp = None
        self._write_status()
        logger.info("Reset timer")
            
    def _restart_cycle(self):
        """Restart the Pomodoro cycle."""
        # Log the current session as incomplete if not idle
        if self.current_state != PomodoroState.IDLE:
            self._log_session(completed=False)
            
        self.pomodoros_completed_in_cycle = 0
        self._start_work_session()
        logger.info("Restarted Pomodoro cycle")
            
    def _log_session(self, completed=True):
        """Log the current session to the database."""
        if self.session_start_timestamp is None:
            return
        
        end_time = int(time.time())
        duration = end_time - self.session_start_timestamp
        
        # Map state to type
        type_map = {
            PomodoroState.WORK: "work",
            PomodoroState.SHORT_BREAK: "short_break",
            PomodoroState.LONG_BREAK: "long_break",
        }
        
        # Get the correct state (if paused, use the paused_state)
        state = self.paused_state if self.current_state == PomodoroState.PAUSED else self.current_state
        
        if state in type_map:
            session_type = type_map[state]
            
            db_path = os.path.expanduser(self.config["db_path"])
            conn = None
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO sessions 
                (start_time, end_time, type, completed, duration_actual_seconds, pomodoro_count_at_completion)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    self.session_start_timestamp,
                    end_time,
                    session_type,
                    completed,
                    duration,
                    self.pomodoros_completed_in_cycle
                ))
                conn.commit()
                logger.info(f"Logged {session_type} session: {duration} seconds, completed: {completed}")
            except Exception as e:
                logger.error(f"Error logging session: {e}")
            finally:
                if conn:
                    conn.close()

    def _complete_work_session(self, was_skipped=False):
        """Handle completion of a work session."""
        self._log_session(completed=not was_skipped)
        
        # Increment pomodoro count
        self.pomodoros_completed_in_cycle += 1
        
        # Send notification
        self._send_notification("Pomodoro completed!", "Time for a break!")
        
        # Play sound if configured
        if self.config["notification_sound_work_end"]:
            self._play_sound(self.config["notification_sound_work_end"])
        
        # Determine which break to take
        if self.pomodoros_completed_in_cycle % self.config["pomodoros_before_long_break"] == 0:
            self._start_break(is_long_break=True)
        else:
            self._start_break(is_long_break=False)
            
    def _complete_break_session(self, was_skipped=False):
        """Handle completion of a break session."""
        self._log_session(completed=not was_skipped)
        
        # Send notification
        self._send_notification("Break completed!", "Time to focus!")
        
        # Play sound if configured
        if self.config["notification_sound_break_end"]:
            self._play_sound(self.config["notification_sound_break_end"])
        
        # Start a new work session
        self._start_work_session()
            
    def _send_notification(self, title, body):
        """Send a desktop notification."""
        try:
            subprocess.run(["notify-send", title, body])
            logger.info(f"Notification sent: {title}")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            
    def _play_sound(self, sound_path):
        """Play a notification sound."""
        try:
            sound_path = os.path.expanduser(sound_path)
            if os.path.exists(sound_path):
                subprocess.run(["aplay", sound_path])
                logger.info(f"Played sound: {sound_path}")
        except Exception as e:
            logger.error(f"Error playing sound: {e}")
            
    def _handle_exit(self, signum, frame):
        """Handle exit signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        
        # If we're in the middle of a session, log it as incomplete
        if self.current_state not in [PomodoroState.IDLE, PomodoroState.PAUSED]:
            self._log_session(completed=False)
            
        self.running = False
        self.db_conn.close()
        sys.exit(0)
            
    def run(self):
        """Run the main timer loop."""
        logger.info("Starting main timer loop")
        
        while self.running:
            try:
                # Don't do anything if idle or paused
                if self.current_state not in [PomodoroState.IDLE, PomodoroState.PAUSED]:
                    # Decrement the time remaining
                    if self.time_remaining_seconds > 0:
                        self.time_remaining_seconds -= 1
                        
                        # Write status every 5 seconds
                        if self.time_remaining_seconds % 5 == 0:
                            self._write_status()
                    else:
                        # Time's up! Handle the transition
                        if self.current_state == PomodoroState.WORK:
                            self._complete_work_session()
                        elif self.current_state in [PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK]:
                            self._complete_break_session()
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(1)  # Wait a bit before continuing


def main():
    """Main entry point for the Pomodoro backend."""
    try:
        timer = PomodoroTimer()
        timer.run()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
