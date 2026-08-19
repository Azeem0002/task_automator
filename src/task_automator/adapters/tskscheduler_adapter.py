
import subprocess
import sys

from ..adapters.runtime_adapter import get_worker_module
from ..models.lifecycle_models import AutoclearStatus

WINDOWS_TASK_NAME = "Autoclear"

def _run_system_command(command: list[str], *, input_text: str | None= None)-> subprocess.CompletedProcess[str]:

    return subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )

def _build_windows_task_command(interval_secs: int)-> list[str]:

    # Task Scheduler needs a stable task name and a distinct command to run.
    # Module mode preserves package-relative imports on Windows too.
    task_target = subprocess.list2cmdline([sys.executable, "-m", get_worker_module(), str(interval_secs)])

    return [
        "schtasks",
        "/create",
        "/tn",
        WINDOWS_TASK_NAME,
        "/tr",
        task_target,
        "/sc",
        "onlogon",
        "/rl",
        "limited",
        "/f",
    ]

def _is_windows_task_installed()-> bool:

    result = _run_system_command(["schtasks", "/query", "/tn", WINDOWS_TASK_NAME]) 
    return result.returncode == 0

def _install_windows_task(interval_secs:int)-> str:

    result = _run_system_command(_build_windows_task_command(interval_secs))
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to create windows task")
    return f"Windows task installed successfully"

def _start_windows_task()-> str:

    result = _run_system_command(["schtasks", "/run", "/tn", WINDOWS_TASK_NAME])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to start windows task")
    return f"STARTED: Windows Task '{WINDOWS_TASK_NAME}'"

def _stop_windows_task()-> str:

    result = _run_system_command(["schtasks", "/end", "/tn", WINDOWS_TASK_NAME])
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Failed to stop windows task"
        if "not currently running" in message.casefold():
            return f"STOPPED: Windows Task '{WINDOWS_TASK_NAME}' already stopped"
        raise RuntimeError(message)
    return f"STOPPED: Windows Task '{WINDOWS_TASK_NAME}'"

def _get_windows_task_status()-> str | None:

    result = _run_system_command(["schtasks", "/query", "/tn", WINDOWS_TASK_NAME, "/fo", "LIST", "/v"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.casefold().startswith("status:"):
            return line.split(":", 1)[1].strip()
    return "installed"

def _get_status_from_task_scheduler()-> AutoclearStatus:

    task_status = _get_windows_task_status()
    if task_status is None:
        return AutoclearStatus(
            backend= "task_scheduler",
            is_running=False,
            pid=None,
            interval_secs=None,
            last_trigger=None,
            detail="Autoclear Windows task not installed"
        )
    
    return AutoclearStatus(
        backend="task_scheduler",
        is_running=task_status.casefold() == "running",
        pid=None,
        interval_secs=None,
        last_trigger=None,
        detail=f"task={task_status}"
    )

# public adapter API

def is_task_scheduler_service_installed():
    return _is_windows_task_installed()

def start_task_scheduler_service()-> str:
    return _start_windows_task()

def stop_task_scheduler_service()-> str:
        return _stop_windows_task()

def get_status_from_task_scheduler()-> AutoclearStatus:
    return _get_status_from_task_scheduler()

def install_task_scheduler_service(*, interval_secs: int)-> tuple[str, list[str]]:

    _install_windows_task(interval_secs=interval_secs)
    return (
        f"Windows Task '{WINDOWS_TASK_NAME}' created",
        ["Task will run when the current user logs on and lunch the autoclear worker"],
    )
