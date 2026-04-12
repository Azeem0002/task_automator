
# AutoClear Task Automator

Minimal CLI tool to run a background process at a fixed interval.  
Handles process control (start/stop/restart), PID tracking, and logging out of the box.

---

# Installation

git clone https://github.com/Azeem0002/task_automator.git
cd task_automator
pipx install .


## AutoClear Commands

autoclear start  # Default: `1h`
autoclear start -i 1h
autoclear status
autoclear stop
autoclear restart -i 30m

---

## Supported Interval Formats

* `60` (no format )→ seconds
* `30s` → seconds
* `2m` → minutes
* `1h` → hours or `1h 30s`→ hours/secs
* `1d` → daysMax interval: **2 days**

---

# Logs location

* **Linux:** `~/.local/state/autoclear/log/`
* **Windows:** `C:\Users\<user>\AppData\Local\autoclear\Logs\`
* **Mac:** `~/Library/Logs/autoclear/`

---