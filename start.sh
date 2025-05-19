#!/bin/bash
# Start script for tomatobar
# Creates named pipes and launches the backend

# Get the config file path
CONFIG_PATH="$HOME/.config/tomatobar/config.json"
PROJECT_CONFIG_PATH="$(dirname "$(realpath "$0")")/config/tomatobar/config.json"

# Determine which config file to use
if [ -f "$CONFIG_PATH" ]; then
    echo "Using config from $CONFIG_PATH"
    CONFIG_TO_USE="$CONFIG_PATH"
else
    echo "Using config from $PROJECT_CONFIG_PATH"
    CONFIG_TO_USE="$PROJECT_CONFIG_PATH"
fi

# Extract the command FIFO path from the config
FIFO_COMMANDS=$(grep -o '"fifo_path_commands": *"[^"]*"' "$CONFIG_TO_USE" | cut -d'"' -f4)

echo "Ensuring command FIFO exists: $FIFO_COMMANDS"

# Create the command FIFO with proper permissions if it doesn't exist
[ -p "$FIFO_COMMANDS" ] || mkfifo -m 600 "$FIFO_COMMANDS"

# Get the directory of this script
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
BACKEND_SCRIPT="$SCRIPT_DIR/tomatobar_backend.py"

# Make the backend script executable
chmod +x "$BACKEND_SCRIPT"

# Launch the backend
echo "Starting Tomatobar backend..."
# Run the backend in the foreground so systemd can track it
python3 "$BACKEND_SCRIPT"

# The script will now only print this if the backend exits, which is fine for logging.
echo "Tomatobar backend exited."
