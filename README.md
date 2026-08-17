
# Task Automator

A lightweight CLI tool for running automated background worker processes on a schedule.  
It handles process control (start/stop/restart), PID tracking, and logging out of the box. It includes three workers: terminal-bound AutoClear, a periodic backup worker, and a disk health monitor.

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

backup-worker /path/to/source /path/to/backups --interval 3600
health-worker --path /home --interval 60 --minimum-free-gb 1

---

## Supported Interval Formats

* `60` (no format )→ seconds
* `30s` → seconds
* `2m` → minutes
* `1h` → hours or `1h30s`→ hours/secs
* `1d` → daysMax interval: **2 days**

The backup and health workers are terminal-independent and should run under
systemd for crash recovery. Replace paths and executable locations in the
service templates under `systemd/` before installing them. AutoClear keeps its
terminal-oriented process behavior as the intentional exception.

For a foreground health check during development:

```bash
cd ~/task_automator
source .venv/bin/activate
health-worker --path /home --interval 60 --minimum-free-gb 1
```

Stop the foreground worker with `Ctrl+C`. Use the systemd template when the
worker must continue without an open terminal.

---

# Problem
If every worker is treated as terminal-bound, `systemd` becomes a fake solution instead of a real runtime option.

# Fix
The detached process backend now supports both terminal-scoped and terminal-free launches. When a terminal exists, the worker records and targets that terminal. When no terminal exists, the worker falls back to a global PID file so service-style jobs can still run and be managed.

Use `autoclear start` for a terminal-scoped session.
Use `install-service`, `start-service`, and `stop-service` for persistent background jobs, crash recovery, and terminal-free workers.
If you already installed an older service unit, reinstall it after changing the runtime instead of deleting files by hand.
