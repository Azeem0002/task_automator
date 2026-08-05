import hashlib
import os
import tempfile
import sys
import time
import psutil
import subprocess
from pathlib import Path
from loguru import logger


from ..adapters.runtime_adapter import get_platform_dirs, get_worker_module, get_worker_working_dir
from ..models.lifecycle_models import AutoclearStatus


def _can_write_pid_dir(pid_dir: Path) -> bool:
    """Return whether autoclear can create and update PID files in a directory."""
    try:
        pid_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        test_file = pid_dir / ".autoclear-write-test"
        with test_file.open("w", encoding="utf-8"):
            pass
        test_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _get_pid_storage_dir() -> Path:
    """Return the first writable directory for autoclear PID files."""
    candidate_dirs = [Path(get_platform_dirs().user_data_dir)]
    fallback_dir = Path(tempfile.gettempdir()) / "autoclear" / "state"
    if fallback_dir not in candidate_dirs:
        candidate_dirs.append(fallback_dir)

    for pid_dir in candidate_dirs:
        if _can_write_pid_dir(pid_dir):
            return pid_dir

    raise OSError("Unable to prepare any writable autoclear PID directory")


def _get_pid_file_path()-> Path:
    tty_path = _resolve_launch_terminal_path()
    return _get_pid_file_path_for_tty(tty_path)


def _get_legacy_pid_file_path() -> Path:
    data_dir = _get_pid_storage_dir()
    return data_dir / "autoclear.pid"


def _get_pid_file_path_for_tty(tty_path: str | None) -> Path:
    """Return the PID file path for one terminal scope.

    The worker backend prefers per-terminal state when a terminal exists, but it
    also supports a terminal-free global worker path for service-style launches.
    """
    data_dir = _get_pid_storage_dir()
    if tty_path is None:
        return data_dir / "autoclear-global.pid"

    tty_name = Path(tty_path).name or "tty"
    safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in tty_name)
    digest = hashlib.sha256(tty_path.encode("utf-8")).hexdigest()[:12]
    return data_dir / f"autoclear-{safe_name}-{digest}.pid"


def _get_global_pid_file_path() -> Path:
    """Return the PID file used when the worker has no terminal scope."""
    return _get_pid_file_path_for_tty(None)


def _read_pid_file_at_path(pid_file: Path, *, warn_on_invalid: bool = True) -> int | None:
    try:
        raw_pid = pid_file.read_text(encoding="utf-8").strip()
        return int(raw_pid)
    except FileNotFoundError:
        return None
    except (ValueError, PermissionError):
        if warn_on_invalid:
            logger.warning(f"Invalid content at {pid_file}")
        pid_file.unlink(missing_ok=True)
        return None

def _read_pid_file(*, tty_path: str | None = None, warn_on_invalid: bool=True)-> int | None:
    if tty_path is None:
        tty_path = _resolve_launch_terminal_path()

    pid_file = _get_pid_file_path_for_tty(tty_path)
    pid = _read_pid_file_at_path(pid_file, warn_on_invalid=warn_on_invalid)
    if pid is not None:
        return pid

    global_pid_file = _get_global_pid_file_path()
    if global_pid_file != pid_file:
        global_pid = _read_pid_file_at_path(global_pid_file, warn_on_invalid=warn_on_invalid)
        if global_pid is not None:
            return global_pid

    legacy_pid_file = _get_legacy_pid_file_path()
    if legacy_pid_file in {pid_file, global_pid_file}:
        return None

    legacy_pid = _read_pid_file_at_path(legacy_pid_file, warn_on_invalid=warn_on_invalid)
    if legacy_pid is None:
        return None

    process = _get_process(legacy_pid)
    if process is None or not _is_autoclear_process(process):
        return None

    target_tty = _read_target_tty_from_process(process)
    if tty_path is not None and target_tty is not None and target_tty != tty_path:
        return None

    _write_pid_file(legacy_pid, tty_path=tty_path)
    try:
        legacy_pid_file.unlink(missing_ok=True)
    except OSError as error:
        logger.warning(str(error))
    return legacy_pid
    
    
def _get_process(pid: int)-> psutil.Process | None:
    try:
        process = psutil.Process(pid)
        if not process.is_running():
            return None
        if process.status() == psutil.STATUS_ZOMBIE:
            return None
        return process
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    

def _is_autoclear_process(process: psutil.Process)-> bool:
    try:
        cmdline = process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    worker_module = get_worker_module()
    # The process can be launched either as a module (`python -m ...`) or as a file.
    # Recognize both shapes so status does not remove a valid PID as stale.
    return any(part == worker_module or part.endswith("autoclear.py") for part in cmdline)

def _write_pid_file(pid: int, *, tty_path: str | None = None)-> None:
    pid_file = _get_pid_file_path_for_tty(tty_path)
    pid_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    logger.debug(f"writing {pid} to {pid_file}")
    pid_file.write_text(str(pid), encoding="utf-8")

def _fd_terminal_path(fd: int)-> str | None:

    try:
        if os.isatty(fd):
            return os.ttyname(fd)
    except OSError:
        pass

    if os.name == "nt":
        return None
    
    try:
        fd_target = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return None
    
    return fd_target if fd_target.startswith("/dev/") else None

def _process_terminal_path(process: psutil.Process)-> str | None:
    try:
        terminal = process.terminal()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    
    return terminal if terminal and terminal.startswith("/dev/") else None

def _resolve_launch_terminal_path()-> str | None:
    env_tty = os.getenv("AUTOCLEAR_TTY", "").strip()
    if env_tty:
        return env_tty
    
    for fd in (1, 0, 2):
        terminal = _fd_terminal_path(fd)
        if terminal:
            return terminal
    
    current = psutil.Process()
    terminal = _process_terminal_path(current)
    if terminal:
        return terminal
    
    for parent in current.parents():
        terminal = _process_terminal_path(parent)
        if terminal:
            return terminal
    
    return None

def _remove_pid_file(*, tty_path: str | None = None)-> None:
    if tty_path is None:
        tty_path = _resolve_launch_terminal_path()

    for pid_file in {
        _get_pid_file_path_for_tty(tty_path),
        _get_global_pid_file_path(),
        _get_legacy_pid_file_path(),
    }:
        pid_file.unlink(missing_ok=True)

def _get_active_process_pid_status(*, tty_path: str | None = None, warn_on_invalid: bool=True)-> int | None:

    if tty_path is None:
        tty_path = _resolve_launch_terminal_path()

    pid = _read_pid_file(tty_path=tty_path, warn_on_invalid=warn_on_invalid)
    if pid is None:
        return None
    
    process = _get_process(pid)
    if process is not None and _is_autoclear_process(process):
        return process.pid
    
    logger.warning(f"Removing stale PID file of invalid process {pid}")
    try:
        _remove_pid_file(tty_path=tty_path)
    except OSError as e:
        logger.warning(str(e))
    return None

def _spawn_detached_process(interval_secs: int)-> int:
    launch_tty = _resolve_launch_terminal_path()
    status = _get_status_from_process(tty_path=launch_tty)
    if status.is_running:
        raise RuntimeError(f"Autoclear is already running. (PID: {status.pid})")
    
    worker_module = get_worker_module()
    env = os.environ.copy()
    if os.name != "nt" and not launch_tty:
        logger.warning("No terminal detected; starting without AUTOCLEAR_TTY")

    if launch_tty:
        env["AUTOCLEAR_TTY"] = launch_tty
    
    
    process = subprocess.Popen(
        [sys.executable, "-m", worker_module, str(interval_secs)],
        stdout = subprocess.DEVNULL,
        stdin = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
        env=env,
        cwd=str(get_worker_working_dir()),
        start_new_session= True,
        close_fds= True,
    )

    deadline = time.time() + 5
    while time.time() < deadline:
        active_pid = _get_active_process_pid_status(warn_on_invalid=False)
        if active_pid is not None:
            return active_pid
        
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"autoclear failed to start with {exit_code}")

        if process.pid:
            _write_pid_file(process.pid, tty_path=launch_tty)
        
        time.sleep(0.1)

    raise RuntimeError("Detached autoclear did not create a pid file in time")


def _read_interval_from_process(process: psutil.Process)->int | None:

    try:
        cmdline = process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    
    if cmdline and cmdline[-1].isdigit():
        return int(cmdline[-1])
    return None

def _read_target_tty_from_process(process: psutil.Process)-> str | None:
    try:
        return process.environ().get("AUTOCLEAR_TTY")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def _build_stopped_process_status(detail: str, pid_file: Path)-> AutoclearStatus:
    
    return AutoclearStatus(
        backend= "process",
        is_running=False,
        pid=None,
        interval_secs=None,
        last_trigger=None,
        detail=detail,
        pid_file=pid_file,
        target_tty=None
    )

def _build_running_process_status(pid: int, pid_file: Path)-> AutoclearStatus:
    
    process= _get_process(pid)
    interval= _read_interval_from_process(process) if process is not None else None
    target_tty = _read_target_tty_from_process(process) if process is not None else None
    return AutoclearStatus(
        backend = "process",
        is_running= True,
        pid=pid,
        interval_secs=interval,
        last_trigger= None,
        detail="Autoclear process backend running",
        pid_file=pid_file,
        target_tty=target_tty
    )

def _get_status_from_process(*, tty_path: str | None = None)-> AutoclearStatus:

    if tty_path is None:
        tty_path = _resolve_launch_terminal_path()

    pid_file = _get_pid_file_path_for_tty(tty_path)
    active_pid = _get_active_process_pid_status(tty_path=tty_path, warn_on_invalid=False)
    if active_pid is None:
        return _build_stopped_process_status("Autoclear not running", pid_file)
    return _build_running_process_status(active_pid, pid_file) 
    

def  _stop_process(wait:bool= True)-> bool:
    active_pid = _get_active_process_pid_status()
    if active_pid is None:
        logger.info("Autoclear is not running")
        return False
    
    try:
        process = psutil.Process(active_pid)
        process.terminate()
    except psutil.NoSuchProcess:
        logger.info("Autoclear is not running")
        return False
    
    logger.info(f"sent stop signal to autoclear process {active_pid}")

    if wait:
        try:
            process.wait(timeout=5)
            _remove_pid_file()
            return True
        except psutil.TimeoutExpired:
            logger.info(f"{active_pid} timeout expired. force kill autoclear")
            process.kill()
            process.wait(timeout=5)
            _remove_pid_file()
            return True
    return True



# public function API's

def get_pid_file_path()-> Path:
    return _get_pid_file_path()

def read_pid_file(*, tty_path: str | None = None, warn_on_invalid:bool= True)-> int | None:
    return _read_pid_file(tty_path=tty_path, warn_on_invalid=warn_on_invalid)

def get_process(pid: int)-> psutil.Process | None:
    return _get_process(pid)

def is_autoclear_process(process: psutil.Process)-> bool:
    return _is_autoclear_process(process)

def write_pid_file(pid: int, *, tty_path: str | None = None)-> None:
    return _write_pid_file(pid, tty_path=tty_path)

def remove_pid_file(*, tty_path: str | None = None)-> None:
    return _remove_pid_file(tty_path=tty_path)

def get_active_process_pid_status(*, tty_path: str | None = None, warn_on_invalid:bool= True)-> int | None:
    return _get_active_process_pid_status(tty_path=tty_path, warn_on_invalid=warn_on_invalid)

def spawn_detached_process(*, interval_secs: int | None)->int:
    if interval_secs is None:
        raise RuntimeError("Interval secs is required for autoclear background process")
    return _spawn_detached_process(interval_secs)

def stop_process(wait: bool=True)-> bool:
    return _stop_process(wait=wait)

def get_status_from_process(*, tty_path: str | None = None)-> AutoclearStatus:
    return _get_status_from_process(tty_path=tty_path)

def read_interval_seconds_from_process(process: psutil.Process)-> int | None:
    return _read_interval_from_process(process)
