## AutoClear Task Automator

Minimal CLI tool to run a background process at a fixed interval. Handles process control (start/stop/restart), PID tracking, and logging out of the box.

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/Azeem0002/autoclear.git
cd autoclear
```

### 2. Install dependencies

```bash
pip install typer psutil pytimeparse loguru platformdirs
```

### 3. Run the CLI

```bash
python controller.py --help
```

---

## Usage

### Start AutoClear

```bash
python controller.py start -i 1h
```

**Interval formats supported:**

* `60` → seconds
* `30s` → seconds
* `2m` → minutes
* `1h` → hours

Max interval: **2 days**

---

### Check Status

```bash
python controller.py status
```

Returns:

* `RUNNING`
* `STOPPED`
* `STALE` (broken PID file)

---

### Stop AutoClear

```bash
python controller.py stop
```

Safely terminates the process and cleans PID file.

---

### Restart AutoClear

```bash
python your_cli_file.py restart -i 30m
```

Stops and starts with a new interval.

---

## How It Works

* Spawns a background process (`autoclear.py`)
* Stores PID in temp directory
* Prevents duplicate processes
* Detects stale or hijacked PID files
* Logs to system-specific log directory

---

## Logs

Stored automatically using `platformdirs`:

* **Linux:** `~/.local/state/autoclear/log/`
* **Windows:** `C:\Users\<user>\AppData\Local\autoclear\Logs\`
* **Mac:** `~/Library/Logs/autoclear/`

---

## Notes (Important)

* Refuses to kill unknown processes (basic safety)
* Validates interval input strictly
* Limits max interval to prevent abuse
* Uses subprocess isolation (`start_new_session=True`)

---

## Rule of Thumb
Run it like a daemon, not a script. Start once, let it manage itself.
