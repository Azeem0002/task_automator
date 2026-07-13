
import os
import sys
from loguru import logger
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from platformdirs import PlatformDirs
from datetime import datetime
from pathlib import Path



APP_NAME = "autoclear"
APP_AUTHOR = "Al-Azeem"

def _get_platform_dirs()-> PlatformDirs:
    return PlatformDirs(APP_NAME, APP_AUTHOR)

def _get_local_timezone():

    tz_name = os.getenv("APP_LOCAL_TZ") or os.getenv("TZ")
    if tz_name:
        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning(f"Unknown timezone: {tz_name}")

    detected = datetime.now().astimezone().tzinfo
    if detected is not None:
        return detected
    
    return ZoneInfo("UTC")

def _get_worker_module() -> str:
    """Return the importable module path for `python -m ...` worker launches."""
    # Package layout uses workers/ with an s:
    # task_automator/workers/autoclear.py -> task_automator.workers.autoclear
    return "task_automator.workers.autoclear"


def _get_worker_working_dir() -> Path:
    """Return the directory where Python can import the task_automator package."""
    # runtime_adapter.py lives in task_automator/adapters/.
    # parents[1] is task_automator/, parents[2] is src/.
    # `python -m task_automator.workers.autoclear` must run from src/
    # unless the package is installed into the environment.
    return Path(__file__).resolve().parents[2]


def _setup_env()-> Path:
    dirs = _get_platform_dirs()
    log_dir = Path(dirs.user_log_dir)
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return log_dir/ "autoclear.log"

def _is_dev_env()-> bool:
    return os.getenv("APP_ENV", "dev").strip().lower() != "prod"

def _setup_logger(log_file):

    logger.remove()
    if not _is_dev_env():
        logger.add(
            sink= sys.stdout,
            level="INFO",
            enqueue=True
        )
    
    else:
        logger.add(
            sink= sys.stdout,
            level="DEBUG",
            format= "<green>{time:YYYY:DD:MM HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}.{function}:{line}</cyan> | <level>{message}</level>",
            colorize=True,
            enqueue=True,
            backtrace=True
        )
    
    logger.add(

        sink=log_file,
        level= "DEBUG",
        rotation= "1 MB",
        retention= "3 days",
        compression="zip",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

# Public adapter API

def get_platform_dirs()-> PlatformDirs:
    return _get_platform_dirs()

def get_local_time_zone():
    return _get_local_timezone()

def get_worker_module()-> str:
    return _get_worker_module()

def get_worker_working_dir()-> Path:
    return _get_worker_working_dir()

def setup_env()-> Path:
    return _setup_env()

def is_dev_env()-> bool:
    return _is_dev_env()

def setup_logger(log_file: Path):
    return _setup_logger(log_file)