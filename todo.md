# Waybar Pomodoro Timer - Implementation Plan

This document outlines the development steps for a feature-rich Pomodoro timer integrated with Waybar, featuring customizable times, pastel theming, activity statistics, and a unique screen blurring function during breaks.

**Target Environment:** Endeavour OS Arch Linux (GNOME Wayland)
**Primary Language:** Python 3
**Database:** SQLite3
**Inter-Process Communication (IPC):** FIFO Pipes
**Notifications:** `notify-send`
**Screen Blurring (Wayland):** Integration with a GNOME Shell Extension, potentially using `dbus` for triggers.

---

## Phase 1: Core Pomodoro Logic & Data Persistence (`pomodoro_backend.py`)

This phase focuses on building the "brain" of the Pomodoro timer, handling timekeeping, state transitions, and session logging.

- [ ] **1.1. Project Setup:**
    - [ ] Create the main project directory: `waybar-pomodoro/`.
    - [ ] Create configuration directory: `waybar-pomodoro/config/waybar-pomodoro/`.
    - [ ] Create data directory: `waybar-pomodoro/share/waybar-pomodoro/`.
    - [ ] Create a placeholder for sounds (optional): `waybar-pomodoro/share/waybar-pomodoro/sounds/`.
    - [ ] Create a placeholder for systemd service (optional): `waybar-pomodoro/systemd/`.
- [ ] **1.2. Configuration Management:**
    - [ ] Create `config.json` inside `waybar-pomodoro/config/waybar-pomodoro/`.
    - [ ] Define default settings in `config.json`:
        - `work_duration_minutes` (default: 25)
        - `short_break_duration_minutes` (default: 5)
        - `long_break_duration_minutes` (default: 15)
        - `pomodoros_before_long_break` (default: 4)
        - `notification_sound_work_end` (path, optional)
        - `notification_sound_break_end` (path, optional)
        - `db_path` (e.g., `~/.local/share/waybar-pomodoro/stats.db`)
        - `fifo_path_status` (e.g., `/tmp/waybar-pomodoro-status`)
        - `fifo_path_commands` (e.g., `/tmp/waybar-pomodoro-commands`)
    - [ ] Implement loading logic in `pomodoro_backend.py`: Read settings from `config.json` on startup. If the file doesn't exist, create it with defaults.
- [ ] **1.3. SQLite Database Setup:**
    - [ ] Ensure `db_path` from `config.json` is used for the SQLite database file.
    - [ ] Design the `sessions` table schema:
        - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
        - `start_time` (DATETIME, UNIX timestamp)
        - `end_time` (DATETIME, UNIX timestamp)
        - `type` (TEXT: 'work', 'short_break', 'long_break')
        - `completed` (BOOLEAN: TRUE if finished, FALSE if interrupted)
        - `duration_actual_seconds` (INTEGER: actual time spent in this phase)
        - `pomodoro_count_at_completion` (INTEGER: num pomodoros completed *before* this session, for work phases)
    - [ ] Implement database initialization: On `pomodoro_backend.py` startup, check if the DB and `sessions` table exist. If not, create them.
- [ ] **1.4. Pomodoro State Machine Logic:**
    - [ ] Define internal states: `IDLE`, `WORK`, `SHORT_BREAK`, `LONG_BREAK`, `PAUSED`.
    - [ ] Manage state variables: `current_state`, `time_remaining_seconds`, `pomodoros_completed_in_cycle`, `session_start_timestamp`.
    - [ ] Implement the main loop, running every second.
    - [ ] Handle `time_remaining_seconds` decrement.
    - [ ] Implement state transition logic (e.g., `WORK` to `SHORT_BREAK`, `SHORT_BREAK` to `WORK`, etc.).
    - [ ] Ensure `pomodoros_completed_in_cycle` is correctly incremented and reset.
    - [ ] Implement session logging: When a phase ends (naturally, skipped, or paused), record the completed portion in the `sessions` table with `start_time`, `end_time`, `type`, `completed`, and `duration_actual_seconds`.
- [ ] **1.5. FIFO Pipe Communication (for Waybar module):**
    - [ ] Create `fifo_path_status` (write-only for backend): The backend will write its current status (JSON string: `state`, `time_remaining`, `pomodoros_completed`, `total_pomodoros_for_long_break`, `message`) to this pipe regularly.
    - [ ] Create `fifo_path_commands` (read-only for backend): The backend will continuously listen for commands from this pipe.
    - [ ] Define commands: `start`, `pause`, `resume`, `skip`, `reset`, `restart_cycle`, `get_status`.
    - [ ] Implement command processing and error handling for malformed commands.
- [ ] **1.6. Desktop Notifications (`notify-send`):**
    - [ ] Send notifications via `subprocess.run(["notify-send", ...])` when phases end.
    - [ ] Customize notification content for work/break transitions.
- [ ] **1.7. Sound Notifications (Optional):**
    - [ ] If sound paths are configured, play audio files using `subprocess.run(["aplay", ...])` on phase transitions.
- [ ] **1.8. System Integration (Optional, but recommended):**
    - [ ] Create a `systemd` user service file (`waybar-pomodoro.service`) to start `pomodoro_backend.py` on user login and ensure it runs reliably in the background.

---

## Phase 2: Waybar Module & Screen Blurring Integration

This phase builds the user-facing Waybar component and integrates the screen blurring functionality.

- [ ] **2.1. Waybar Module Script (`waybar_pomodoro_module.py`):**
    - [ ] Implement reading from `fifo_path_status`: Continuously read and parse JSON status updates from the backend.
    - [ ] Format output for Waybar: Create a JSON string with `text`, `alt`, and `class` attributes (e.g., `{"text": "🍅 Work: 24:59", "alt": "Focus", "class": "work"}`).
    - [ ] Print formatted JSON to `stdout` for Waybar to display.
    - [ ] Implement command-line argument parsing for click actions (e.g., `python waybar_pomodoro_module.py --action start`).
    - [ ] Write received commands to `fifo_path_commands` based on arguments.
- [ ] **2.2. Waybar Configuration (`~/.config/waybar/config`):**
    - [ ] Add a `custom/pomodoro` module entry.
    - [ ] Set `format` to `{}` and `return-type` to `json`.
    - [ ] Set `exec` to `python /path/to/waybar_pomodoro_module.py`.
    - [ ] Configure `on-click`, `on-right-click`, and `on-middle-click` to call `waybar_pomodoro_module.py` with appropriate actions (e.g., `on-click": "python /path/to/waybar_pomodoro_module.py --action start"`).
- [ ] **2.3. Waybar Styling (`~/.config/waybar/style.css`):**
    - [ ] Define CSS rules for `.custom-pomodoro` to achieve a pastel aesthetic (e.g., `background-color`, `color`, `padding`, `border-radius`).
    - [ ] Define specific styles for different states using the `class` attribute (e.g., `.custom-pomodoro.work`, `.custom-pomodoro.break`, `.custom-pomodoro.paused`) with distinct pastel colors.
- [ ] **2.4. Screen Blurring Integration (GNOME Wayland Specific):**
    - [ ] **Research/Identify GNOME Shell Extension:** Find or identify a suitable GNOME Shell extension that can dynamically blur the screen and potentially be triggered externally or respond to idle state. (This might be the most challenging part).
    - [ ] **`gnome_blur_interactor.py` (or integrated into backend):**
        - [ ] This script/component will listen for specific signals from `pomodoro_backend.py` (e.g., a dedicated FIFO or `dbus` message) indicating a break has started or ended.
        - [ ] Implement `dbus` communication (if necessary) to interact with the chosen GNOME Shell Extension.
        - [ ] When a break starts, send a trigger to the extension to activate screen blur.
        - [ ] When the break ends, send a trigger to the extension to deactivate screen blur.
    - [ ] **GNOME Shell Extension Logic (Conceptual):** The chosen/modified extension will handle the actual blurring, detecting mouse movement to temporarily unblur, and re-blurring after a period of inactivity.

---

## Phase 3: Statistics CLI Tool (`pomodoro_stats.py`)

This phase creates a command-line interface for reviewing Pomodoro session statistics.

- [ ] **3.1. Command Line Argument Parsing:**
    - [ ] Implement argument parsing for:
        - `--day`: Stats for the current day.
        - `--week`: Stats for the current week.
        - `--month`: Stats for the current month.
        - `--all`: All recorded sessions.
        - `--start YYYY-MM-DD --end YYYY-MM-DD`: Custom date range.
        - `--csv`: Output in CSV format (optional).
- [ ] **3.2. Database Connection:**
    - [ ] Connect to the SQLite database specified in `config.json`.
- [ ] **3.3. Query Logic:**
    - [ ] Write SQL queries to retrieve data based on parsed arguments.
    - [ ] Calculate: total completed work sessions, total focus time, number of interrupted sessions, average work session duration.
    - [ ] Implement grouping logic for daily, weekly, and monthly summaries.
- [ ] **3.4. Output Formatting:**
    - [ ] Present stats in a clear, readable ASCII format in the terminal.
    - [ ] Format time durations into human-readable strings (e.g., "1h 15m 30s").
    - [ ] Implement CSV output if the `--csv` argument is provided.

---

## Phase 4: Project Setup & Refinements

This phase focuses on making the project user-friendly and robust.

- [ ] **4.1. FIFO Pipe Creation Script (`start.sh`):**
    - [ ] Create a simple shell script to ensure FIFO pipes are created before launching `pomodoro_backend.py`.
    - [ ] Add `mkfifo -m 600` commands for both `fifo_path_status` and `fifo_path_commands`.
    - [ ] Launch `pomodoro_backend.py` in the background (e.g., `python pomodoro_backend.py & disown`).
- [ ] **4.2. Permissions:**
    - [ ] Ensure correct file permissions for FIFO pipes and the SQLite database file.
- [ ] **4.3. Error Handling & Logging:**
    - [ ] Implement comprehensive `try-except` blocks for file I/O, database operations, and FIFO interactions in all Python scripts.
    - [ ] Use Python's `logging` module to log events and errors to a file for debugging purposes.
- [ ] **4.4. User Documentation:**
    - [ ] Create a `README.md` file with instructions on how to install, configure, and use the Pomodoro timer.
    - [ ] Include details on Waybar configuration and styling.
    - [ ] Explain how to use the `pomodoro_stats.py` CLI tool.
    - [ ] Document the requirements for the GNOME Shell Extension for blurring.
- [ ] **4.5. Testing:**
    - [ ] Thoroughly test each component independently.
    - [ ] Test the full integration: Waybar display, click actions, backend logic, notifications, and blur activation/deactivation.
    - [ ] Test different scenarios: skipping sessions, pausing, resetting, and long breaks.

---