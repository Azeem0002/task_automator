
# Task Automator

A lightweight CLI tool for running automated background worker processes on a schedule.  
It handles process control (start/stop/restart), PID tracking, and logging out of the box, making it useful for any recurring worker task. AutoClear is included here as an example worker, but the same framework can be used for other automation jobs as well.

---

# Installation

You can install and run this project using **uv** (recommended for automatic Python version management and speed) or **pipx** (for global system command installation).

### Option 1: Using `uv` (Recommended)
Make sure you have [uv](https://docs.astral.sh/uv/) installed, then run:

```bash
# Clone the repository
git clone https://github.com/Azeem0002/task_automator.git
cd task_automator

# Install the autoclear command globally on your system
uv tool install .
```
Once installed, you can run the commands below directly as `autoclear <command>`.

*Note: If you are developing the project and do not want to install it globally, run `uv sync` to build the local virtual environment, and prefix all commands below with `uv run ` (e.g. `uv run autoclear start`).*

### Option 2: Using `pipx`
If you prefer to install the command globally to your system path using pipx:

```bash
git clone https://github.com/Azeem0002/task_automator.git
cd task_automator
pipx install .
```
Once installed, you can run the commands below directly.

> **Note**: This project requires Python 3.13 or newer. If using `pipx`, ensure your local Python interpreter is version 3.13+ (or run `pipx install . --python python3.13`). If using `uv`, the correct Python version will be downloaded and used automatically.

## AutoClear Commands

autoclear install-service           # Install or update the persistent native service backend
autoclear install-service --system  # Optional: manage the system-level persistent backend on Linux

autoclear start                     # Default: `1h`
autoclear start  1h 30m
autoclear start -i 1h30m
autoclear status
autoclear stop                     # Stop both the detached process and installed service backend
autoclear restart -i 120m           # Default: `1h`
autoclear start-service             # Start backend persistence and crash recovery
autoclear stop-service              # Stop the persistent native service backend

---

## Supported Interval Formats

* `60` (no format )→ seconds
* `30s` → seconds
* `2m` → minutes
* `1h` → hours or `1h30s`→ hours/secs
* `1d` → daysMax interval: **2 days**

---

# Problem
The `autoclear` worker may not clear the correct terminal due to TTY detection issues, and can leave stale service configurations on both Linux (systemd) and Windows (Task Scheduler).

# Fix
To resolve TTY detection, first remove any stale systemd timers. Relevant adapters (`process_adapter.py`, `autoclear.py`, `controller.py`, `runtime_adapter.py`) have been updated for reliable TTY identification.

Process backend state is now scoped per terminal, so separate shells can run
their own autoclear sessions without fighting over one global PID file.
Run `autoclear start` from the shell you want cleared. If you launch it from a
wrapper script, export `AUTOCLEAR_TTY=$(tty)` first.
`autoclear start` is the terminal-bound clearing path.
Use `install-service`, `start-service`, and `stop-service` for backend
persistence and crash recovery only. They do not recover an interactive shell
session after reboot.
If you want automatic relaunch after login, add a separate wrapper or login
hook that starts the terminal-bound command in that session.

**Linux (systemd):**
```bash
rm ~/.config/systemd/user/autoclear.timer
rm ~/.config/systemd/user/autoclear.service
systemctl --user daemon-reload
```
**Windows (Task Scheduler):**
```powershell
schtasks /delete /tn "Autoclear" /f
```
