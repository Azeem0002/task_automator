#! usr/bin/env python3

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Callable

from platformdirs import PlatformDirs
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from src.config.settings import AutoclearConfig

def _setup_env()-> Path:

    APP_NAME = "autoclear"
    APP_AUTHOR = "Al-Azeem"

    dirs = PlatformDirs(appname=APP_NAME, appauthor=APP_AUTHOR)

    LOG_DIR = Path(dirs.user_log_dir)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.debug(f" Failed to create directory")
        raise PermissionError(f"Failed to create directory") from e

    file_log = LOG_DIR / "autoclear.log"
    return file_log

def _setup_logger(file_log: Path)-> None:

    logger.remove()
    ENV = os.getenv("APP_NAME", "dev")
    
    if ENV == "prod":

        logger.add(
            sink= sys.stdout,
            level= "INFO",
            enqueue=True,
        )
    else:
        logger.add(
            sink= sys.stdout,
            level="DEBUG",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | {level: <8} | {module}.{function}:{line} | <level>{message}</level>",
            enqueue= True,
            backtrace= True,
        )

        logger.add(
        sink = file_log,
        rotation= "1 MB",
        retention= "2 days",
        enqueue= True,
        backtrace=True
    )

# @dataclass
# class AutoclearConfig:
#     interval: int = 3600
#     max_retries: int= 3
#     retry_delay: float= 1.0

def _get_clear_command()-> list[str]:

    command = ["cmd", "/c", "cls"] if os.name == "nt" else ["clear"]
    return command

def _execute_command(command: list[str])-> None:
    command = _get_clear_command()
    try:
        subprocess.run(command, timeout=5, check=True)
    
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Clear failed: {command}") from e
    
def _sleep(seconds: int)-> None:
    time.sleep(seconds)


def log_before(retry_state)-> None:
    attempt = retry_state
    logger.info(f"Attempt {attempt} / {retry_state}")

def log_after(retry_state)-> None:

    if retry_state.outcome.failed:
        logger.warning(f"Attempt Failed: {retry_state}")
    else:
        logger.info(f"Attempt Succeeded")


def with_retry(max_attempt: int, delay: float)-> Callable:

    def decorator(func: Callable)-> Callable:
        @retry(
            stop= stop_after_attempt(max_attempt),
            wait= wait_fixed(delay),
            before= log_before,
            after= log_after,
            reraise=True,
        )
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped
    return decorator



def clear_terminal(config: AutoclearConfig):

    command = _get_clear_command()
    operation = with_retry(config.max_retries, config.retry_delay)(_execute_command)

    if not operation:
        logger.warning(f"Too many commands")
    
    operation(command)

def run_autoclear(config: AutoclearConfig)-> None:

    while True:
        try:
            clear_terminal(config)
            logger.success(f"Terminal cleared")
        
        except RuntimeError:
            time.sleep(1)
        _sleep(config.interval)
    

def init():
    file_log = _setup_env()
    _setup_logger(file_log)

def main():
    log_file = _setup_env()
    _setup_logger(log_file)
    try:

        interval = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
        config = AutoclearConfig(interval)
        run_autoclear(config)
    except ValueError:
        logger.info("Invalid time interval")
        sys.exit(1)

if __name__=="__main__":
    main()