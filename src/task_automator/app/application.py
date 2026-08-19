"""Application/orchestration layer for terminal-scoped autoclear."""

from ..adapters.runtime_adapter import is_dev_env
from ..adapters.process_adapter import get_status_from_process, spawn_detached_process, stop_process
from ..models.lifecycle_models import AutoclearStatus
from ..validators.validation import format_duration_seconds, parse_interval


def _format_process_start_message(action: str, pid: int, interval_secs: int, target_tty: str | None = None) -> str:
    """Build the user-facing process backend startup message."""
    interval_label = format_duration_seconds(interval_secs)
    target_text = f"; target terminal {target_tty}" if target_tty else "" # If we know which terminal, mention it. Otherwise, blank.
    return f"Autoclear {action} in background (PID: {pid}) with interval {interval_label}{target_text}; first clear starts immediately, then every {interval_label}"

def _format_autoclear_status(status: AutoclearStatus) -> str:
    """Format autoclear status."""
    # Turn the typed app model into readable terminal text.
    state = "running" if status.is_running else "stopped"
    parts = [f"Autoclear status: {state}", f"backend= {status.backend}"] # default base information
    # Left side: Always included (base information)

    # Right side: Only added when PID exists (conditional information)
    if status.pid is not None: # conditional information
        parts.append(f"pid= {status.pid}")
    interval_seconds = getattr(status, "interval_seconds", getattr(status, "interval_secs", None))
    if interval_seconds is not None:
        parts.append(f"interval= {format_duration_seconds(interval_seconds)}")
    if status.last_trigger:
        parts.append(f"last_trigger= {status.last_trigger}")
    if status.pid_file is not None and is_dev_env():
        parts.append(f"pid_file= {status.pid_file}")
    # The target terminal is operational state, not debug noise. Operators
    # need it in every environment to confirm which terminal autoclear owns.
    if status.target_tty is not None:
        parts.append(f"target_tty= {status.target_tty}")
    if status.detail:
        parts.append(f"detail= {status.detail}")

    return " | ".join(parts)


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
    """Start the detached-process backend and format the user-facing startup message."""
    pid = spawn_detached_process(interval_secs=interval_secs)
    status = get_status_from_process()
    return _format_process_start_message(action, pid, interval_secs, status.target_tty)


# ============================================
# Application / Orchestration - Public use cases
# Start reading internals from here.
# ============================================
def get_autoclear_status() -> AutoclearStatus:
    """
    Return status from autoclear's terminal-scoped detached-process backend.

    Flow:
        status -> get_autoclear_status
        get_autoclear_status
            -> get_status_from_process
    """
    return get_status_from_process()

def format_autoclear_status(status: AutoclearStatus)-> str:
    return _format_autoclear_status(status)


def resolve_interval_text(option_value: str, interval_parts: list[str]) -> str:
    return _resolve_interval_text(option_value, interval_parts)

def start_autoclear(interval: str) -> str:
    """
    Start autoclear only as a terminal-scoped detached process.

    Flow:
        start -> start_autoclear
        start_autoclear
            -> parse_interval
            -> spawn_detached_process
    """
    interval_secs = parse_interval(interval)
    return _start_process_backend("started", interval_secs)


def stop_autoclear() -> str:
    """
    Stop autoclear's terminal-scoped process backend.

    Flow:
        stop -> stop_autoclear
        stop_autoclear
            -> stop_process
    """
    try:
        if stop_process():
            return "Autoclear process backend stopped"
    except (RuntimeError, OSError) as error:
        return f"Unable to stop autoclear: {error}"

    return "Autoclear already stopped"


def restart_autoclear(interval: str) -> str:
    """
    Stop then start autoclear's terminal-scoped process backend.

    Flow:
        restart -> restart_autoclear
        restart_autoclear
            -> stop_autoclear
            -> start_autoclear
    """
    interval_secs = parse_interval(interval)
    stop_autoclear()
    return _start_process_backend("restarted", interval_secs)
