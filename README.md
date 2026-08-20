
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
Autoclear is an explicit command group under `task-automator`, not a second
top-level command.

task-automator autoclear start -i 60m    # Explicit autoclear form (recommended)
task-automator autoclear status
task-automator autoclear stop
task-automator autoclear restart -i 2h
task-automator interactive               # Guided menu for all worker actions

task-automator workers run scheduled_backup /path/to/source --interval 1h
disk-health-monitor --path /home --interval 60 --minimum-free-gb 1

---

## Supported Interval Formats

* `60` (no format )→ seconds
* `30s` → seconds
* `2m` → minutes
* `1h` → hours or `1h30s`→ hours/secs
* `1d` → daysMax interval: **2 days**

## Configuration, State, and Source Layout

`src/task_automator/` contains only importable application code. Do not place
machine-specific configuration, PID files, logs, or backups under `src/`.
`platformdirs` selects the correct per-user directories on Linux, Windows, and
macOS: configuration for user-editable settings, state for PID/checkpoint
metadata, data for backups, and logs for diagnostics. The former `build/`
directory was generated packaging output, not source configuration, and is not
part of the application layout.

The backup and health workers are terminal-independent and can use the native
service supervisor for their OS when crash recovery is required: systemd on
Linux or Task Scheduler on Windows. Start with
[services/README.md](services/README.md); Linux unit templates live in
`services/linux/` and Windows setup instructions live in `services/windows/`.
Autoclear is never a system service: it is bound to the live terminal session
that started it.

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
`WORKER_ARGUMENT_HINT = "Example: --path /home --interval 60s"`.
To allow detached execution through `workers start`, explicitly add
`WORKER_BACKGROUND_SAFE = True`. New workers are foreground-only by default;
this prevents accidentally detaching a TTY-dependent or one-shot script.
If a worker needs a terminal, GUI session, clipboard, or interactive prompt,
also set `WORKER_TERMINAL_BOUND = True`. The catalog hides it from generic
background execution and rejects `workers start` and service use. It remains
safe to run in the foreground with `workers run`; autoclear has its own
explicit session command because it must detach and clear the launching TTY.

```bash
task-automator workers list
task-automator workers run                 # choose a worker and enter its arguments
task-automator workers run my_worker --interval 60s
task-automator workers run scheduled_backup /path/to/source --interval 1h
task-automator workers run scheduled_backup /path/to/source --destination /external/backups --interval 1h
task-automator workers start disk_health_monitor --path /home --interval 5m
task-automator workers status disk_health_monitor
task-automator workers logs disk_health_monitor
task-automator workers stop disk_health_monitor
```

Worker filenames must be valid Python identifiers, such as `my_worker.py`.
`workers run` is foreground-only. Start terminal-bound autoclear with
`task-automator autoclear start -i 60m` so it detaches and your shell remains usable.
Use `-- --help` only when you need a selected worker's help; normal worker
options need one dash sequence, such as `workers run disk_health_monitor --path /home --interval 60s`.
The built-in periodic workers accept `60s`, `5m`, `2h`, or plain seconds such
as `3600` through the shared duration parser.

`disk_health_monitor` enforces its configured disk-free-space floor and reports
disk free space, RAM usage/available RAM, and sampled CPU usage each interval.
CPU and RAM are observability signals in this MVP; only the disk floor stops
the worker because CPU/RAM thresholds and a safe recovery policy are not yet
configured.

`workers start` creates one controller-managed background process per worker
name. Its PID is persisted in the app state directory, so `workers status`,
`workers logs`, and `workers stop` work from a later shell. Scheduled backups
write `BACKUP_PATH=/...` to that log after each successful snapshot.

Stop the foreground worker with `Ctrl+C`. Use the systemd template only when a
worker must continue without an open terminal.

---

## Worker Capability Rule

Terminal-bound workers are a separate category, not merely foreground workers:
they need a live user session and cannot be supervised safely after reboot.
Set `WORKER_TERMINAL_BOUND = True` and expose an explicit session command.
Terminal-independent workers may additionally opt into detached operation with
`WORKER_BACKGROUND_SAFE = True`, then use a systemd template when boot-time
startup or crash recovery is genuinely required.
