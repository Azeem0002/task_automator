"""Application/orchestration layer for autoclear.

Boundary code calls this module with already-parsed inputs.
This layer chooses the right backend and coordinates process/service adapters.
"""

try:
    from ..adapters.runtime_adapter import is_dev_env
    from ..models.lifecycle_models import AutoclearStatus
    from ..adapters.platform_adapter import detect_platform
    from ..validators.validation import format_duration_seconds, parse_interval
    from ..adapters.process_adapter import (
        get_status_from_process,
        spawn_detached_process,
        stop_process,
    )
    from ..adapters.service_adapter import (
        get_service_status,
        install_service,
        start_service,
        stop_service,
    )

except ImportError:
    from task_automator.adapters.runtime_adapter import is_dev_env
    from task_automator.models.lifecycle_models import AutoclearStatus
    from task_automator.adapters.platform_adapter import detect_platform
    from task_automator.validators.validation import format_duration_seconds, parse_interval
    from task_automator.adapters.process_adapter import (
        get_status_from_process,
        spawn_detached_process,
        stop_process,
    )
    from task_automator.adapters.service_adapter import (
        get_service_status,
        install_service,
        start_service,
        stop_service,
    )


def install_autoclear_service(interval: str = "1h", system: bool = False) -> tuple[str, list[str]]:
    """
    Install or update the native background backend after parsing the human interval input.

    Flow:
        install-service -> install_autoclear_service
        install_autoclear_service
            -> parse_interval
            -> detect_platform
            -> install_service
    """
    # Application chooses the native backend that matches the current platform.
    interval_secs = parse_interval(interval)
    platform = detect_platform()

    if platform in {"linux", "windows"}:
        return install_service(interval_secs=interval_secs, system=system)

    if platform == "mac":
        return ("macOS not yet supported for service install", ["Use `start` to launch autoclear"])

    raise RuntimeError(f"Unsupported platform: {platform}")


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


def _resolve_autoclear_backend(*, system: bool = False) -> str:
    """Choose the runtime backend once so start/stop/status follow the same mental path."""
    # Backend resolution is orchestration, not CLI work:
    # 1. explicit `--system` on Linux means "use the native service backend even if it
    #    has not been installed yet" so status can report that fact honestly.
    # 2. detached process is the local default because `autoclear start` should do
    #    what the operator asked, not silently follow an old installed service.
    platform = detect_platform()
    if system and platform == "linux":
        return "service"

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
    """Start the detached-process backend and format the user-facing startup message."""
    pid = spawn_detached_process(interval_secs=interval_secs)
    status = get_status_from_process()
    return _format_process_start_message(action, pid, interval_secs, status.target_tty)


# ============================================
# Application / Orchestration - Public use cases
# Start reading internals from here.
# ============================================
def get_autoclear_status(*, system: bool = False) -> AutoclearStatus:
    """
    Return status from the current default backend: detached worker by default, service on explicit `--system` on Linux.

    Flow:
        status -> get_autoclear_status
        get_autoclear_status
            -> detect_platform
            -> get_service_status | get_status_from_process
    """
    backend = _resolve_autoclear_backend(system=system)
    if backend == "service":
        return get_service_status(system=system)

    return get_status_from_process()

def format_autoclear_status(status: AutoclearStatus)-> str:
    return _format_autoclear_status(status)


def resolve_interval_text(option_value: str, interval_parts: list[str]) -> str:
    return _resolve_interval_text(option_value, interval_parts)

def start_autoclear(interval: str, *, system: bool = False) -> str:
    """
    Start autoclear using the backend that makes sense for the current platform.

    Flow:
        start -> start_autoclear
        start_autoclear
            -> parse_interval
            -> detect_platform
            -> start_service | spawn_detached_process
    """
    # One use-case, different infrastructure by platform.

    interval_secs = parse_interval(interval)
    backend = _resolve_autoclear_backend(system=system)
    if backend == "service":
        return start_service(system=system)

    if detect_platform() == "linux" and get_service_status(system=False).is_running:
        stop_service(system=False)

    return _start_process_backend("started", interval_secs)


def stop_autoclear(*, system: bool = False) -> str:
    """
    Stop autoclear across both process and native service backends.

    Flow:
        stop -> stop_autoclear
        stop_autoclear
            -> stop_service
            -> stop_process
    """
    messages: list[str] = []
    stop_errors: list[str] = []

    platform = detect_platform()
    if platform in {"linux", "windows"}:
        try:
            messages.append(stop_service(system=system))
        except (RuntimeError, OSError) as error:
            stop_errors.append(str(error))

    try:
        if stop_process():
            messages.append("Autoclear process backend stopped")
    except (RuntimeError, OSError) as error:
        stop_errors.append(str(error))

    if messages:
        if stop_errors:
            messages.extend(stop_errors)
        return " | ".join(messages)

    if stop_errors:
        return f"Autoclear already stopped | {' | '.join(stop_errors)}"

    return "Autoclear already stopped"


def restart_autoclear(interval: str, *, system: bool = False) -> str:
    """
    Stop the current autoclear backend and start it again with the requested interval.

    Flow:
        restart -> restart_autoclear
        restart_autoclear
            -> stop_autoclear
            -> start_autoclear
    """
    interval_secs = parse_interval(interval)
    stop_autoclear(system=system)
    backend = _resolve_autoclear_backend(system=system)
    if backend == "service":
        return start_service(system=system)

    if detect_platform() == "linux" and get_service_status(system=False).is_running:
        stop_service(system=False)

    return _start_process_backend("restarted", interval_secs)
