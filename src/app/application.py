import pytimeparse

from pathlib import Path

from ..models.lifecycle_models import AutoclearStatus
from ..adapters.platform_adapter import detect_platform
from ..adapters.process_adapter import (
    get_status_from_process,
    spawn_detached_process,
    stop_process,
)
from ..adapters.service_adapter import(
    get_status_from_systemd,
    install_service,
    is_service_installed,
    start_service,
    stop_service,
)
from ..validation.validation import parse_interval

def install_autoclear_service(interval: str= "1h", system: bool=False)-> tuple[str, list[str]]:

    interval_secs = parse_interval(interval)
    platform = detect_platform()

    if platform == "linux":
        return install_service(interval_secs=interval_secs, system=system)
    
    if platform == "windows":
        return ("Windows uses the process backend for autoclear", 
                ["Use start to lunch autoclear"])

    if platform == "mac":
        return ("MacOs not yet supported for service install", ["Use start to lunch autoclear"])
    
    raise RuntimeError(f"Unsupported platform: {platform}")

def get_autoclear_status()-> AutoclearStatus:
    platform = detect_platform()

    if platform == "linux" and is_service_installed(system=False):
        return get_status_from_systemd(system=False)
    return get_status_from_process()

def start_autoclear(interval: str)-> str:
    interval_secs= parse_interval(interval)
    platform= detect_platform()

    if platform == "linux" and is_service_installed(system=False):
        return start_service(interval_secs=interval_secs, system=False)

    pid = spawn_detached_process(interval_secs=interval_secs)
    return f"Autoclear started in background (PID: {pid})"

def stop_autoclear()-> str:
    platform= detect_platform()

    if platform == "linux" and is_service_installed(system=False):
        return stop_service(system=False)
    
    stopped = stop_process()
    if stopped:
        return "Autoclear process backend stopped"
    return "Autoclear already stopped"

def restart_autoclear(interval: str)-> str:

    stop_autoclear()
    return start_autoclear(interval)
