
from ..models.lifecycle_models import AutoclearStatus
from ..adapters.platform_adapter import detect_platform
from ..validators.validation import format_duration_seconds, parse_interval
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

def _format_process_start_message(action: str, pid: int, interval_secs:int, target_tty: str | None)-> str:

    interval_label =  format_duration_seconds(interval_secs)
    target_text= f"; target terminal {target_tty}" if target_tty else ""
    return f"Autoclear {action} in background (PID: {pid}) with interval {interval_label}{target_text}"


# Application
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
    status = get_status_from_process()
    return _format_process_start_message("Started", pid, interval_secs, status.target_tty)

def stop_autoclear()-> str:
    platform= detect_platform()

    if platform == "linux" and is_service_installed(system=False):
        return stop_service(system=False)
    
    stopped = stop_process()
    if stopped:
        return "Autoclear process backend stopped"
    return "Autoclear already stopped"

def restart_autoclear(interval: str)-> str:

    interval_secs = parse_interval(interval)
    platform = detect_platform()
   
    stop_autoclear()

    if platform == "linux" and is_service_installed():
        return start_autoclear(interval_secs=interval_secs, system=False)

    pid = spawn_detached_process(interval_secs = interval_secs)
    status = get_status_from_process()
    return _format_process_start_message("restarted.", pid, interval_secs, status.target_tty)