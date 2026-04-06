# ! usr/bin/env python3

import os
import sys
import subprocess
import tempfile
import time
from pathlib import Path

import psutil
import typer
import pytimeparse
from platformdirs import PlatformDirs
from loguru import logger

def _setup_env()->Path:

    APP_NAME = "autoclear"
    APP_AUTHOR="Al-Azeem"

    dirs = PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR)

    LOG_DIR = Path(dirs.user_log_dir)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = LOG_DIR / "controller.log"
    return log_file

def _setup_logger(log_file: Path)-> None:

    ENV = os.getenv("APP_ENV", "dev")

    logger.remove()
    if ENV == "prod":
        logger.add(
            sink= sys.stdout,
            level="INFO",
            enqueue=True
        )
        logger.add(
            sink=log_file,
            level="DEBUG",
            format= "{time:YYYY-HH-MM-DD HH:mm:ss} | {level: <8} | {message}",
            rotation="1 MB",
            retention="3 days",
            compression="gz",
            enqueue=True,
            catch=True,
            backtrace=True,

        )
    else:
        logger.add(
            sink= sys.stdout,
            level= "DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | <level>{module}.{function}:{line}</level> | <level>{message}</level>",
            enqueue=True,
            backtrace=True,
            catch=True,
        )
        logger.add(
            sink= log_file,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss}",
            rotation="1 MB",
            retention="5 days",   
            enqueue=True,
            backtrace=True,
            serialize=True,
            catch=True,
        )


def _get_pid_file_path()-> Path:

    temp_dir = Path(tempfile.gettempdir())
    return temp_dir / "autoclear.pid"

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
        cmdline = ', '.join(proc.cmdline())
        return "autoclear.py" in cmdline
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

    controller_dir = Path(__file__).parent/ "autoclear.py"
    command = [sys.executable, str(controller_dir), str(interval)]

    return subprocess.Popen(command, start_new_session=True)

def  _parse_interval(value: str)-> int:
    
    if value.isdigit():
        return int(value)
    
    seconds = pytimeparse.parse(value)
    if seconds is None:
        raise ValueError(f"Invalid time format")
    
    if seconds <= 0: 
        raise ValueError(f"value must be > 0: {value}")
    
    if seconds > 17280: # 2days
        raise ValueError(f"Interval too large. (max 2days)")
    
    return int(seconds)




def status_autoclear()-> str:

    pid_file = _get_pid_file_path()
    if not pid_file.is_file():
        return "STOPPED: Autoclear not running"
    
    pid = _read_file_path(pid_file)
    if pid is None:
        logger.warning("Stale PID file detected")
        return "STALE"
    
    running = _is_process_running(pid)
    if not running:
        return "Stale PID file"
    
    our_process = _is_our_process(pid)
    if not our_process:
        logger.warning("PID belongs to another process")
        return "STOPPED: unknown process"

    return "RUNNING"

def stop_autoclear()-> str:

    pid_file = _get_pid_file_path()
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
        return f"Failed to stop Autoclear"

def start_autoclear(interval: str)-> bool:

    interval_sec = _parse_interval(interval)

    pid_file= _get_pid_file_path()
    existing_pid = _read_file_path(pid_file)

    if existing_pid is not None:
        if _is_process_running(existing_pid) and _is_our_process(existing_pid):
            logger.warning(f"Autoclear already running")
            return False
        
        # we delete stale
        _delete_pid_file(pid_file)
        logger.info(f"Cleaned up stale PID: {existing_pid}")

    # we start autoclear
    proc = _spawn_process(interval_sec)
    _write_pid_to_file(pid_file, proc.pid)

    time.sleep(0.3)
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

app = typer.Typer()

@app.callback()
def init():
    log_file = _setup_env()
    _setup_logger(log_file)

@app.command()
def status():
    result = status_autoclear()
    typer.echo(result)

@app.command()
def stop():
    result = stop_autoclear()
    typer.echo(result)

@app.command()
def start(interval: str= typer.Option("1h", "-i", help="interval e.g 1h, 60s, 60, 2m, 3600")):
    result = start_autoclear(interval)
    if result:
        time.sleep(1)
        typer.echo("Autoclear started")

@app.command()
def restart(seconds: str= typer.Option("1h", "-i", help="interval e.g 60m, 30s, 3600")):
    result = restart_autoclear(seconds)
    time.sleep(1)
    if result:
        interval = _parse_interval(seconds)
        typer.echo(f"Restarted autoclear with: {interval}s")
    else:
        typer.BadParameter(f"Failed to restart autoclear: {result}")
        raise typer.Exit(code=1)
    
if __name__=="__main__":
    app()