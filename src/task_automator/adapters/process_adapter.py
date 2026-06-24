

import sys
import time
import psutil
import subprocess
from pathlib import Path
from loguru import logger


from ..adapters.runtime_adapter import get_platform_dirs, get_worker_script_path
from ..models.lifecycle_models import AutoclearStatus


def _get_pid_file_path()-> Path:

    data_dir = Path(get_platform_dirs().user_data_dir)
    return data_dir / "autoclear.pid"

def _read_pid_file(*, warn_on_invalid: bool=True)-> int | None:
    pid_file= _get_pid_file_path()
    try:
        raw_pid = pid_file.read_text(encoding="utf-8").strip()
    
    except FileNotFoundError:
        return None
    except (ValueError, PermissionError):
        if warn_on_invalid:
            logger.warning(f"Invalid content at {pid_file}")
        pid_file.unlink(missing_ok=True)
        return None
    return int(raw_pid)
    
def _get_process(pid: int)-> psutil.Process | None:
    try:
        process = psutil.Process(pid)
        if not process.is_running():
            return None
        if process.status() == psutil.STATUS_ZOMBIE:
            return None
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    return process

def _is_autoclear_process(process: psutil.Process)-> bool:
    try:
        cmdline = process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    script_path = get_worker_script_path()
    return any(part == script_path or part.endswith("autoclear.py") for part in cmdline)

def _write_pid_file(pid: int)-> None:

    pid_file = _get_pid_file_path()
    pid_file.mkdir(mode=0o700, parents=True, exist_ok=True)
    logger.debug(f"writing {pid} to {pid_file}")
    pid_file.write_text(str(pid), encoding="utf-8")

def _remove_pid_file()-> None:
    pid_file = _get_pid_file_path()
    pid_file.unlink(missing_ok=True)

def _get_active_process_pid_status(*, warn_on_invalid: bool=True)-> int | None:

    pid = _read_pid_file(warn_on_invalid=warn_on_invalid)
    if pid is None:
        return None
    
    process = _get_process(pid)
    if process is not None and _is_autoclear_process(process):
        return process.pid
    
    logger.warning(f"Removing stale PID file of invalid process {pid}")
    try:
        _remove_pid_file()
    except OSError as e:
        logger.warning(str(e))
    return None

def _read_interval_from_process(process: psutil.Process)->int | None:

    try:
        cmdline = process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None
    
    if cmdline and cmdline[-1].isdigit():
        return int(cmdline[-1])
    return None
    

def _build_stopped_process_status(detail: str, pid_file: Path)-> AutoclearStatus:
    
    return AutoclearStatus(
        backend= "process",
        is_running=False,
        pid=None,
        interval_secs=None,
        last_trigger=None,
        detail=detail,
        pid_file=pid_file
    )

def _build_running_process_status(pid: int, pid_file: Path)-> AutoclearStatus:
    
    process= _get_process(pid)
    interval= _read_interval_from_process(process) if process is not None else None
    return AutoclearStatus(
        backend = "process",
        is_running= True,
        pid=pid,
        interval_secs=interval,
        last_trigger= None,
        detail="Autoclear process backend running",
        pid_file=pid_file
    )

def _get_status_from_process()-> AutoclearStatus:

    pid_file = _get_pid_file_path()
    active_pid = _get_active_process_pid_status(warn_on_invalid=False)
    if active_pid is None:
        return _build_stopped_process_status("Autoclear not running", pid_file)
    return _build_running_process_status(active_pid, pid_file) 

    
def _spawn_detached_process(interval_secs: int)-> int:

    existing_pid = _get_status_from_process()
    if existing_pid is not None:
        raise RuntimeError("Autoclear is already running")
    
    script_path = get_worker_script_path()
    process = subprocess.Popen(
        [sys.executable, str(script_path), str(interval_secs)],
        stdout = subprocess.DEVNULL,
        stdin = subprocess.DEVNULL,
        stderr = subprocess.DEVNULL,
        start_new_session= True,
        close_fds= True
    )

    deadline = time.time() + 5
    while time.time() < deadline:
        active_pid = _get_active_process_pid_status(warn_on_invalid=False)
        if active_pid is not None:
            return active_pid
        

        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"autoclear failed to start with {exit_code}")

        if process.pid is not None:
            return process.pid
        
        time.sleep(0.1)
    raise RuntimeError("Detached autoclear did not create a pid file in time")


def  _stop_process(wait: bool=True)-> bool:
    active_pid = _get_active_process_pid_status()
    if active_pid is None:
        logger.info("Autoclear already stopped")
        return False
    
    try:
        process = psutil.Process(active_pid)
    except psutil.NoSuchProcess:
        return False
    
    logger.info(f"sending stop signal to autoclear process {active_pid}")

    if wait:
        try:
            process.wait(timeout=5)
            _remove_pid_file()
            return True
        except psutil.TimeoutExpired:
            logger.info("timeout expired. force kill autoclear")
            process.kill()
            process.wait(timeout=3)
            _remove_pid_file()
            return True
    return True



# public function API's

def get_pid_file_path()-> Path:
    return _get_pid_file_path()

def read_pid_file(*, warn_on_invalid)-> int | None:
    return _read_pid_file(warn_on_invalid=warn_on_invalid)

def get_process(pid: int)-> psutil.Process | None:
    return _get_process(pid)

def is_autoclear_process(process: psutil.Process)-> bool:
    return _is_autoclear_process(process)

def write_pid_file(pid: int)->None:
    return _write_pid_file(pid)

def remove_pid_file():
    return _remove_pid_file()

def get_status_from_process()-> AutoclearStatus:
    return _get_status_from_process()

def spawn_detached_process(*, interval_secs: int | None)->int:
    if interval_secs is None:
        raise RuntimeError("Interval secs is required for autoclear background process")
    return _spawn_detached_process(interval_secs)

def read_interval_from_process(process: psutil.Process)-> int | None:
    return _read_interval_from_process(process)

def stop_process(wait: bool=True)-> bool:
    return _stop_process(wait=wait)