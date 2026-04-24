# ! usr/bin/env python3

import sys
import subprocess
import time
from pathlib import Path

import psutil
from loguru import logger
from parsers.parse import parse_interval
from env.env import get_pid_file_path


def _read_file_path(pid_file: Path)-> int | None:
    
    try:
        content = pid_file.read_text().strip()
        return int(content)
    except (FileNotFoundError, ValueError, OSError):
        return None
    
def _is_process_running(pid: int)-> bool:

    return psutil.pid_exists(pid)

def _is_our_process(pid: int)-> bool:
    """we check if the process running is for autoclear"""

    try:
        proc = psutil.Process(pid)
        cmdline = ' '.join(proc.cmdline())
        return ("autoclear-worker" in cmdline)
    except OSError:
        return False

def _terminate_pid(pid: int)-> None:

    proc = psutil.Process(pid)
    proc.terminate()

    try:
        proc.wait(timeout=3)
    except psutil.TimeoutExpired:
        proc.kill()

def _delete_pid_file(pid_file: Path)-> None:

    try:
        pid_file.unlink(missing_ok=True)
    except OSError as e:
        logger.debug(f"Failed to delete pid file: {pid_file}")
        raise PermissionError(f"Failed to delete pid file: {str(e)}") from e
    
def _write_pid_to_file(pid_file: Path, pid: int)-> None:
    """ we write pid to file """
    try:
        pid_file.write_text(str(pid))
    except PermissionError as e:
        logger.debug(f"File does ot have write permission: {e}")
        raise RuntimeError(f"Failed to write pid to file: {pid_file}")

def _spawn_process(interval: int)-> subprocess.Popen:

    # controller_dir = Path(__file__).parent.parent / "autoclear"
    command = ["autoclear-worker", str(interval)]

    return subprocess.Popen(
        command,
        stdout=None,   # ← Let output show
        stderr=None,
        start_new_session=True,)



def status_autoclear()-> str:

    pid_file = get_pid_file_path()
    if not pid_file.is_file():
        return "STOPPED: Autoclear not running"
    
    pid = _read_file_path(pid_file)
    if pid is None:
        logger.warning("Stale PID file detected")
        return "STALE: Process is stale"
    
    running = _is_process_running(pid)
    if not running:
        return "Autoclear not running"
    
    our_process = _is_our_process(pid)
    if not our_process:
        logger.warning("PID belongs to another process")
        return "STOPPED: unknown process"
    
    try:
        proc = psutil.Process(pid)
        cmdline = proc.cmdline()
        interval = cmdline[-1] if len(cmdline) >= 2 else "unknown"
        return f"Autoclear is running with {interval}(s) interval. (PID: {proc.pid})"
    except:
        return f"Running: Autoclear (PID: {pid})"
    
    
def stop_autoclear()-> str:

    pid_file = get_pid_file_path()
    pid = _read_file_path(pid_file)

    if pid is None:
        return "Already stopped"
    
    if not _is_process_running(pid):
        try:
            _delete_pid_file(pid_file)
            return f"Cleaned up stale process"
        except RuntimeError as e:
            return f"Failed to cleanup stale file: {str(e)}"
        
    if not _is_our_process(pid):

        return "Not our process, refusing to kill"
    try:
        _terminate_pid(pid)
        _delete_pid_file(pid_file)
        return f"Autoclear stopped"
    
    except RuntimeError as e:
        logger.error(f"Failed to stop {str(e)}")
        return f"Failed to stop Autoclear"

def start_autoclear(interval: str)-> bool:

    pid_file= get_pid_file_path()
    existing_pid = _read_file_path(pid_file)

    if existing_pid is not None:
        if _is_process_running(existing_pid):
            if _is_our_process(existing_pid):
                logger.warning(f"Autoclear already running")
                return False
            
        # we clean up stale
        else:
            _delete_pid_file(pid_file)
            logger.info(f"Cleaned up stale PID: {existing_pid}")

    interval_sec = parse_interval(interval)
    # we start autoclear
    proc = _spawn_process(interval_sec)
    time.sleep(0.3)

    if proc.poll() is not None:
        raise RuntimeError("Autoclear failed to start")

    _write_pid_to_file(pid_file, proc.pid) 
    logger.info(f"Autoclear is starting with interval {interval_sec}s. (PID:{proc.pid})")
    return True

def restart_autoclear(interval: str)-> bool:
    # logger.info(f"Restarting autoclear with interval: {interval}s")
   # time.sleep(1)
    try:
        stop_autoclear()
    except RuntimeError:
        pass
    return start_autoclear(interval)

