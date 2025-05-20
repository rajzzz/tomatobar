# Tomatobar Timer

A feature-rich Pomodoro timer integrated with Waybar, featuring customizable durations, pastel theming, activity statistics, and optional screen blurring during breaks. This project is now named Tomatobar.

![alt text](image.png)

## Features

- 🍅 **Core Pomodoro Functionality**: Work sessions, short breaks, and long breaks with configurable durations
- 📊 **Statistics Tracking**: Log completed pomodoros and break sessions to a SQLite database
- 🎨 **Pastel Theming**: Visually distinguish different states with pleasant pastel colors
- 📱 **Waybar Integration**: Seamless integration with Waybar status bar
- 🔄 **Interactive Controls**: Start, pause, resume, skip, and reset via mouse clicks
- 🔔 **Notifications**: Desktop notifications when sessions end
- 🎵 **Sound Alerts**: Optional sound notifications (configurable)
- 🌐 **Persistent Settings**: User-configurable settings stored in JSON
- 🚀 **Systemd Integration**: Optional systemd user service for reliable background operation

## Requirements

- Python 3.6+
- Waybar
- SQLite3
- notify-send (for notifications)
- aplay (for sound alerts, optional)
- Arch Linux with GNOME Wayland (for screen blurring, optional)

## Installation

1. Clone this repository or download the files:

```bash
git clone https://github.com/rajzzz/tomatobar.git
cd tomatobar
```

2. Make the scripts executable:

```bash
chmod +x tomatobar_backend.py tomatobar_module.py start.sh
```

3. Install the files:

```bash
# Create necessary directories
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/tomatobar
mkdir -p ~/.config/tomatobar
mkdir -p ~/.config/systemd/user

# Copy the main scripts
cp tomatobar_backend.py tomatobar_module.py start.sh ~/.local/bin/

# Copy the config and share directories
cp -r config/tomatobar/* ~/.config/tomatobar/
cp -r share/tomatobar/* ~/.local/share/tomatobar/

# Copy the systemd service (optional)
cp systemd/tomatobar.service ~/.config/systemd/user/
```

4. Start the backend service:

```bash
# Option 1: Start manually
~/.local/bin/start.sh

# Option 2: Enable and start with systemd (recommended)
systemctl --user enable tomatobar.service
systemctl --user start tomatobar.service
```

## Waybar Configuration

Add the Tomatobar module to your Waybar configuration (`~/.config/waybar/config` or `~/.config/waybar/config.jsonc`):

```json
"custom/tomatobar": {
    "format": "{}",
    "return-type": "json",
    "exec": "python3 ~/.local/bin/tomatobar_module.py",
    "interval": 1,
    "on-click": "python3 ~/.local/bin/tomatobar_module.py --action start",
    "on-click-right": "python3 ~/.local/bin/tomatobar_module.py --action pause",
    "on-click-middle": "python3 ~/.local/bin/tomatobar_module.py --action skip",
    "on-scroll-up": "python3 ~/.local/bin/tomatobar_module.py --action reset",
    "on-scroll-down": "python3 ~/.local/bin/tomatobar_module.py --action restart_cycle",
    "tooltip": true
},
```

Add the following styles to your Waybar CSS (`~/.config/waybar/style.css`):

```css
/* Base styles for the Tomatobar module */
#custom-tomatobar {
    font-family: "Ubuntu Nerd Font", sans-serif;
    font-size: 14px;
    padding: 0 10px;
    margin: 0 5px;
    border-radius: 6px;
    transition: all 0.3s ease;
}

/* Work session - soft red pastel */
#custom-tomatobar.work {
    background-color: #ffb3b3;
    color: #802020;
}

/* Short break - soft blue pastel */
#custom-tomatobar.short_break {
    background-color: #b3d9ff;
    color: #204080;
}

/* Long break - soft green pastel */
#custom-tomatobar.long_break {
    background-color: #b3ffb3;
    color: #206020;
}

/* Paused state - soft yellow pastel */
#custom-tomatobar.paused {
    background-color: #ffffb3;
    color: #806020;
    animation: blink 1.5s infinite;
}

/* Idle state - light gray pastel */
#custom-tomatobar.idle {
    background-color: #e0e0e0;
    color: #505050;
}
```

See the `examples` directory for complete configuration samples.

## Configuration

Edit `~/.config/tomatobar/config.json` to customize the timer:

```json
{
    "work_duration_minutes": 25,
    "short_break_duration_minutes": 5,
    "long_break_duration_minutes": 15,
    "pomodoros_before_long_break": 4,
    "notification_sound_work_end": "",
    "notification_sound_break_end": "",
    "db_path": "~/.local/share/tomatobar/stats.db",
    "fifo_path_status": "/tmp/tomatobar-status",
    "fifo_path_commands": "/tmp/tomatobar-commands"
}
```

## Usage

The Tomatobar module in Waybar supports these interactions:

- Left Click: Start timer / Resume if paused
- Right Click: Pause timer
- Middle Click: Skip current phase
- Scroll Up: Reset timer
- Scroll Down: Restart Pomodoro cycle

## Statistics

A simple statistics tool is included to view your Pomodoro history:

```bash
# Coming in Phase 3
python3 ~/.local/bin/tomatobar_stats.py --day   # Stats for current day
python3 ~/.local/bin/tomatobar_stats.py --week  # Stats for current week
python3 ~/.local/bin/tomatobar_stats.py --month # Stats for current month
python3 ~/.local/bin/tomatobar_stats.py --all   # All recorded sessions
```

## Screen Blurring (GNOME Wayland)

Screen blurring functionality will be implemented in Phase 2.

## Troubleshooting

- **Module not showing up**:
  - Verify the `custom/tomatobar` module is added to `modules-left`, `modules-center`, or `modules-right` in your Waybar config (`~/.config/waybar/config` or `~/.config/waybar/config.jsonc`).
  - Check that the FIFO pipes (e.g., `/tmp/tomatobar-status`, `/tmp/tomatobar-commands`) exist.
  - Ensure the backend service is running: `systemctl --user status tomatobar.service`.
- **Backend crashes**: Check the logs with `journalctl --user -u tomatobar.service`
- **Styling issues**: Make sure the CSS classes match the state names in the module

## License

MIT License

## Credits

Created for productivity enhancement on Endeavour OS Arch Linux with GNOME Wayland.
