
from ..models.lifecycle_models import AutoclearStatus
from ..adapters.platform_adapter import detect_platform
from ..adapters.tskscheduler_adapter import install_task_scheduler_service
from ..adapters.systemd_adapter import (
    get_status_from_systemd,
    install_systemd_service,
    is_systemd_service_installed,
    start_systemd_service,
    stop_systemd_service,
)
from ..adapters.tskscheduler_adapter import(
    get_status_from_task_scheduler,
    is_task_scheduler_service_installed,
    install_task_scheduler_service,
    start_task_scheduler_service,
    stop_task_scheduler_service,
)

def _is_service_installed(*, system:bool = False)-> bool:

    platform = detect_platform()
    if platform == "linux":
        return is_systemd_service_installed(system=system)
    
    if platform == "windows":
        return is_task_scheduler_service_installed()
    
    if platform == "mac":
        return False
    
    return False


def _install_service(*, interval_secs: int | None = None, system:bool =  False)-> tuple[str, list[str]]:

    if interval_secs is None:
        raise ValueError("Interval_secs is required ")

    platform = detect_platform()

    if platform == "linux":
        return install_systemd_service(interval_secs=interval_secs, system=system)
    
    if platform == "windows":
        return install_task_scheduler_service(interval_secs=interval_secs)
    
    if platform == "mac":
        return (
            "macOS not yet supported",
            ["launch manually or run `autoclear start`"]
        )
    raise RuntimeError(f"Unsupported platform: {platform}")


def _start_service(*, system:bool=False)-> str:

    platform = detect_platform()
    if platform == "linux":
        if not _is_service_installed(system=system):
            raise RuntimeError("Autoclear service backend is not installed. Run `autoclear install-service` first.")
        return start_systemd_service(system=system)
    
    if platform == "windows":
        if not _is_service_installed(system=system):
            raise RuntimeError("Autoclear service backend is not installed. Run `autoclear install-service` first.")
        return start_task_scheduler_service()
    
    if platform == "mac":
        return "macOS not supported yet. \nlaunch manually or run autoclear start"
    
    raise RuntimeError(f"Unsupported platform: {platform}")

def _stop_service(*, system:bool= False)-> str:

    platform = detect_platform()
    if platform == "linux":
        return stop_systemd_service(system=system)
    
    if platform == "windows":
        return stop_task_scheduler_service()
    
    if platform == "mac":
        return "macOS not supported yet. \nlaunch manually or run autoclear start"
    
    raise RuntimeError(f"Unsupported platform: {platform}")

def _get_service_status(*, system:bool = False)-> AutoclearStatus:

    platform = detect_platform()
    
    if platform == "linux":
        return get_status_from_systemd(system=system)
    if platform == "windows":
        return get_status_from_task_scheduler()
    
    raise RuntimeError(f"Unsupported platform: {platform}")
     


# Public API adapter

def install_service(*, interval_secs: int | None, system:bool= False)-> tuple[str, list[str]]:
    return _install_service(interval_secs=interval_secs, system=system)

def is_service_installed(system:bool= False):
    return _is_service_installed(system=system)

def start_service(*, system:bool=False)-> str:
    return _start_service(system=system)

def stop_service(*, system:bool= False)-> str:
    return _stop_service(system=system)

def get_service_status(*, system:bool= False)-> AutoclearStatus:
    return _get_service_status(system=system)