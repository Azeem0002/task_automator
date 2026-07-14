
from ..models.lifecycle_models import AutoclearStatus
from ..adapters.platform_adapter import detect_platform
from ..adapters.runtime_adapter import is_dev_env
from ..validators.validation import format_duration_seconds, parse_interval
from ..adapters.process_adapter import (
    get_status_from_process,
    spawn_detached_process,
    stop_process,
)
from ..adapters.service_adapter import(
    get_service_status,
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


def _format_autoclear_status(status: AutoclearStatus)-> str:

    state = "running" if status.is_running else "stopped"
    parts = [f"Autoclear status: {state}", f"backend={status.backend}"]

    if status.pid is not None:
        parts.append(f"pid={status.pid}")
    
    if status.interval_secs is not None:
        parts.append(f"interval = {format_duration_seconds(status.interval_secs)}")
    
    if status.last_trigger:
        parts.append(f"last_trigger={status.last_trigger}")
    if status.pid_file is not None and is_dev_env():
        parts.append(f"pid_file= {status.pid_file}")
    
    if status.target_tty is not None and is_dev_env():
        parts.append(f"target_tty= {status.target_tty}")
    
    if status.detail:
        parts.append(f"detail= {status.detail}")
    
    return " | ".join(parts)


# Application

def _resolve_autoclear_backend(*, system: bool = False) -> str:
    """Choose the lifecycle backend before start/stop/status so each command follows one clear route."""
    platform = detect_platform()

    # Explicit --system means the user wants the OS service manager on platforms that support it.
    if system and platform == "linux":
        return "service"

    # Installed services should be controlled by the service adapter so status/start/stop stay consistent.
    if platform in {"linux", "windows"} and is_service_installed(system=system):
        return "service"

    # The process backend is the portable fallback for normal local runs and unsupported service platforms.
    return "process"

def _resolve_interval_text(option_value: str, interval_parts: list[str]) -> str:
    """Accept either `--interval 1h30m` or positional words like `1h 30m`."""
    # Shells split spaces before Typer receives input. Supporting varargs here
    # turns `start 1h 30m` back into the user meaning "one interval value".
    if interval_parts and option_value != "1h":
        raise ValueError("Use either positional interval or --interval, not both")
    if interval_parts:
        return " ".join(interval_parts)
    return option_value


def _start_process_backend(action: str, interval_secs: int) -> str:
    """Start the detached process backend and format the same user message for start/restart."""
    pid = spawn_detached_process(interval_secs=interval_secs)
    status = get_status_from_process()
    return _format_process_start_message(action, pid, interval_secs, status.target_tty)


def get_autoclear_status(*, system: bool = False) -> AutoclearStatus:
    backend = _resolve_autoclear_backend(system=system)

    if backend == "service":
        return get_service_status(system=system)

    return get_status_from_process()

def format_autoclear_status(status: AutoclearStatus)-> str:
    return _format_autoclear_status(status)


def resolve_interval_text(option_value: str, interval_parts: list[str]) -> str:
    return _resolve_interval_text(option_value, interval_parts)

def start_autoclear(interval: str, *, system: bool) -> str:
    interval_secs = parse_interval(interval)
    backend = _resolve_autoclear_backend(system=system)

    if backend == "service":
        return start_service(interval_secs=interval_secs, system=system)

    return _start_process_backend("Started", interval_secs)


def stop_autoclear(*, system: bool = False) -> str:
    backend = _resolve_autoclear_backend(system=system)

    if backend == "service":
        return stop_service(system=system)

    stopped = stop_process()
    if stopped:
        return "Autoclear process backend stopped"
    return "Autoclear already stopped"


def restart_autoclear(interval: str, *, system: bool = False) -> str:
    interval_secs = parse_interval(interval)
    backend = _resolve_autoclear_backend(system=system)

    if backend == "service":
        stop_service(system=system)
        return start_service(interval_secs=interval_secs, system=system)

    stop_process()
    return _start_process_backend("restarted", interval_secs)
