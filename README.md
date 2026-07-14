
# Task Automator

A lightweight CLI tool for running automated background worker processes on a schedule.  
It handles process control (start/stop/restart), PID tracking, and logging out of the box, making it useful for any recurring worker task. AutoClear is included here as an example worker, but the same framework can be used for other automation jobs as well.

---

# Installation

git clone https://github.com/Azeem0002/task_automator.git
cd task_automator
pipx install .

> Note: this project requires Python 3.13 or newer.
> If you already installed it before and want to reinstall or update it, run `pipx install . --force`.

## AutoClear Commands

autoclear install-service  # Install the worker as a service (platform-aware)
autoclear install-service --system  # Optional: install as a system-level service on Linux or Windows
autoclear start  # Default: `1h`
autoclear start -i 1h30m
autoclear status
autoclear stop
autoclear restart -i 120m

---

## Supported Interval Formats

* `60` (no format )→ seconds
* `30s` → seconds
* `2m` → minutes
* `1h` → hours or `1h30s`→ hours/secs
* `1d` → daysMax interval: **2 days**

---

