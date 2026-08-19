
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

# Install the task-automator command globally on your system
uv tool install .
```
Once installed, you can run the commands below directly as `autoclear <command>`.

*Note: If you are developing the project and do not want to install it globally, run `uv sync` to build the local virtual environment, and prefix all commands below with `uv run ` (e.g. `uv run task-automator start`).*

### Option 2: Using `pipx`
If you prefer to install the command globally to your system path using pipx:

```bash
git clone https://github.com/Azeem0002/task_automator.git
cd task_automator
pipx install .
```
Once installed, you can run the commands below directly.

> **Note**: This project requires Python 3.13 or newer. If using `pipx`, ensure your local Python interpreter is version 3.13+ (or run `pipx install . --python python3.13`). If using `uv`, the correct Python version will be downloaded and used automatically.

## Commands

`task-automator` is the primary command because it manages multiple workers.
`autoclear` remains a compatible alias for the existing terminal-clear commands.

task-automator install-service           # Install or update the persistent native service backend
task-automator install-service --system  # Optional: manage the system-level persistent backend on Linux

task-automator start                     # Default: `1h`
task-automator start  1h 30m
task-automator start -i 1h30m
task-automator status
task-automator stop                     # Stop both the detached process and installed service backend
task-automator restart -i 120m           # Default: `1h`
task-automator start-service             # Start backend persistence and crash recovery
task-automator stop-service              # Stop the persistent native service backend
task-automator autoclear start -i 60m    # Explicit autoclear form (recommended)
task-automator autoclear status
task-automator autoclear stop
task-automator autoclear restart -i 2h
task-automator interactive               # Guided menu for all worker actions

scheduled-backup /path/to/source /path/to/backups --interval 3600
disk-health-monitor --path /home --interval 60 --minimum-free-gb 1

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
disk-health-monitor --path /home --interval 60 --minimum-free-gb 1
```

## Add Your Own Worker

Put a runnable Python module in `src/task_automator/workers/`. The controller
discovers its filename automatically; do not edit a worker registry or the CLI.
Your worker should expose its own Typer CLI (or otherwise handle command-line
arguments) and include a normal `if __name__ == "__main__": ...` entrypoint.
For the interactive list, optionally add `WORKER_DESCRIPTION` and
`WORKER_ARGUMENT_HINT` strings near the top of the module; for example,
`WORKER_ARGUMENT_HINT = "Example: --path /home --interval 60"`.

```bash
task-automator workers list
task-automator workers run                 # choose a worker and enter its arguments
task-automator workers run my_worker --interval 60
```

Worker filenames must be valid Python identifiers, such as `my_worker.py`.
`workers run` is foreground-only. Start terminal-bound autoclear with
`task-automator autoclear start -i 60m` so it detaches and your shell remains usable.
Use `-- --help` only when you need a selected worker's help; normal worker
options need one dash sequence, such as `workers run disk_health_monitor --path /home`.

`disk_health_monitor` enforces its configured disk-free-space floor and reports
disk free space, RAM usage/available RAM, and sampled CPU usage each interval.
CPU and RAM are observability signals in this MVP; only the disk floor stops
the worker because CPU/RAM thresholds and a safe recovery policy are not yet
configured.

Interactive mode can start a future worker in the background and reports its
PID plus log path. Scheduled backups write `BACKUP_PATH=/...` to that log after
each successful snapshot. It first asks foreground versus background; choosing
autoclear from Background then offers Start, Status, and Stop. At its interval
prompt enter a value such as `2h`, not `--interval 2h`.

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
