#!/usr/bin/env python3
"""
Tomatobar Module
This script reads the Tomatobar timer status from a FIFO pipe and formats it for Waybar.
It also provides command-line functionality to send commands to the backend.
"""

import argparse
import json
import os
import sys
import time


def get_config_path():
    """Get the config file path, either from user's config dir or the project dir."""
    user_config_path = os.path.expanduser("~/.config/tomatobar/config.json")
    if os.path.exists(user_config_path):
        return user_config_path
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_config_path = os.path.join(script_dir, "config", "tomatobar", "config.json")
    if os.path.exists(project_config_path):
        return project_config_path
    
    return None


def load_config():
    """Load configuration from the config file."""
    config_path = get_config_path()
    if not config_path:
        print(json.dumps({
            "text": "⚠️ No config",
            "alt": "Error",
            "class": "error"
        }), flush=True)
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(json.dumps({
            "text": f"⚠️ Config error",
            "alt": f"Error: {e}",
            "class": "error"
        }), flush=True)
        sys.exit(1)


def format_status_for_waybar(status):
    """Format the status JSON for Waybar."""
    state = status["state"]
    pomodoros_completed = status["pomodoros_completed"]
    total_pomodoros = status["total_pomodoros_for_long_break"]
    message = status["message"]
    
    # Emoji for each state
    emoji_map = {
        "idle": "🍅",
        "work": "🍅",
        "short_break": "☕",
        "long_break": "🌴",
        "paused": "⏸️"
    }
    
    emoji = emoji_map.get(state, "🍅")
    
    # Text to display
    text = f"{emoji} {message} [{pomodoros_completed}/{total_pomodoros}]"
    
    # Shorter text for when space is limited
    alt = f"{emoji} {state.capitalize()}"
    
    return {
        "text": text,
        "alt": alt,
        "class": state
    }


def read_status(config):
    """Read the current status from the status file."""
    status_file_path = config.get("status_file_path") # Use .get for safety
    
    if not status_file_path:
        return {
            "text": "⚠️ No status_file_path in config",
            "alt": "Error",
            "class": "error"
        }

    if not os.path.exists(status_file_path):
        # If the status file doesn't exist, assume idle or backend not started
        return {
            "text": "🍅 Ready",
            "alt": "Idle",
            "class": "idle"
        }
    
    try:
        with open(status_file_path, 'r') as f:
            data = f.read().strip()
        
        if not data:
            # If the file is empty, also assume idle
            return {
                "text": "🍅 Ready",
                "alt": "Idle",
                "class": "idle"
            }
        
        status = json.loads(data)
        return format_status_for_waybar(status)
    except json.JSONDecodeError:
        return {
            "text": "⚠️ Invalid JSON in status file",
            "alt": "Error",
            "class": "error"
        }
    except Exception as e:
        return {
            "text": f"⚠️ {type(e).__name__}",
            "alt": f"Error: {e}",
            "class": "error"
        }


def send_command(config, command):
    """Send a command to the backend through the command FIFO pipe."""
    fifo_path = config["fifo_path_commands"]
    
    if not os.path.exists(fifo_path):
        print(f"Error: Command FIFO not found at {fifo_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(fifo_path, 'w') as f:
            f.write(f"{command}\n")
            f.flush()
    except Exception as e:
        print(f"Error sending command: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for the Waybar module script."""
    parser = argparse.ArgumentParser(description='Tomatobar Module')
    parser.add_argument('--action', choices=['start', 'pause', 'resume', 'skip', 'reset', 'restart_cycle'],
                      help='Action to perform')
    
    args = parser.parse_args()
    config = load_config()
    
    # If an action was specified, send the command and exit
    if args.action:
        send_command(config, args.action)
        sys.exit(0)
    
    # Otherwise, read and display the status
    status = read_status(config)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    main()
