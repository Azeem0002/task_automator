
import getpass
import shlex
import subprocess
import sys
from pathlib import Path

from loguru import logger

from ..models.lifecycle_models import AutoclearStatus
from ..adapters.runtime_adapter import get_worker_module, get_worker_working_dir

SYSTEMD_SERVICE_NAME = "autoclear.service"
SYSTEMD_TIMER_NAME = "autoclear.timer"

def _format_exec_args(args: list[str])-> str:
    return " ".join(shlex.quote(arg) for arg in args)

def _get_systemd_user_dir()-> Path:
    return Path.home() / ".config/systemd/user"

def _run_system_command(command: list[str], *, input_text: str | None = None)-> subprocess.CompletedProcess[str]:

    return subprocess.run(
        command,
        input= input_text,
        text=True,
        capture_output=True,
        check=False
    )

def _run_systemctl(args: list[str], *, system:bool)-> subprocess.CompletedProcess[str]:

    base = ["systemctl"]
    if not system:
        base.append("--user")
    return _run_system_command(base + args)

def _read_systemd_property(unit_name: str, property_name: str, system:bool)-> str | None:

    result = _run_systemctl(["show", unit_name, f"--property={property_name}", "--value"], system=system)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _build_systemd_service(*, interval_secs: int, system: bool)-> str:

    service_lines = [
        "[Unit]",
        "Description=Autoclear terminal worker",
        "",
        "[Service]",
        "Type=simple"
    ]

    if system:
        service_lines.append(f"User={getpass.getuser()}")
    
    service_lines.extend([
        f"WorkingDirectory={get_worker_working_dir()}",
        f"ExecStart={_format_exec_args([sys.executable, '-m', get_worker_module(), str(interval_secs)])}",
        "Environment=APP_ENV=prod",
        "Nice=10",
        "",
        "[Install]",
        f"WantedBy={'multi-user.target' if system else 'default.target'}",
        "",
    ])
    return "\n".join(service_lines)

def _build_systemd_timer(interval_secs: int)-> str:
    timer_lines = [
        "[Unit]",
        "Description= Run autoclear on a fixed interval",
        "",
        "[Timer]",
        "OnBootSec=1m",
        f"OnUnitActiveSec={interval_secs}",
        f"Unit={SYSTEMD_SERVICE_NAME}",
        "Persistent=true",
        "AccuracySec=1s",
        "",
        "[Install]",
        "WantedBy=timers.target",
        "",
    ]
    return "\n".join(timer_lines)

def _is_systemd_timer_enabled(*, system:bool)-> bool:
    return _read_systemd_property(SYSTEMD_TIMER_NAME, "UnitFileState", system=system)=="enabled"

def _install_systemd_system(service_content: str, timer_content: str)-> tuple[Path, Path]:

    service_path = Path("/etc/systemd/system") / SYSTEMD_SERVICE_NAME
    timer_path = Path("/etc/systemd/system") / SYSTEMD_TIMER_NAME

    service_result = _run_system_command(["sudo", "tee", str(service_path)], input_text= service_content)
    if service_result.returncode != 0:
        raise RuntimeError(service_result.stderr.strip() or "Failed to install_systemd service")
    
    timer_result = _run_system_command(["sudo", "tee", str(timer_path)], input_text=timer_content)
    if timer_result.returncode != 0:
        raise RuntimeError(timer_result.stderr.strip() or "Failed to install systemd timer")
    
    return service_path, timer_path


def _reload_systemd(*, system:bool)-> None:
    reload_result = _run_systemctl(["daemon-reload"], system=system)
    if reload_result.returncode != 0:
        raise RuntimeError(reload_result.stderr.strip() or "Failed to install systemd_timer")



def _is_systemd_timer_installed(*, system: bool)-> bool:

    unit_path = Path("/etc/systemd/system") / SYSTEMD_TIMER_NAME if system else _get_systemd_user_dir() / SYSTEMD_TIMER_NAME
    return unit_path.exists()

def _get_status_from_systemd(*, system: bool)-> AutoclearStatus:

    if not _is_systemd_timer_installed(system=system):
        return AutoclearStatus(
            backend="systemd",
            is_running= False,
            pid=None,
            interval_secs= None,
            last_trigger= None,
            detail= "Autoclear systemd timer not installed"
        )
    
    timer_state = _read_systemd_property(SYSTEMD_TIMER_NAME, "ActiveState", system=system) or "unknown"
    service_state = _read_systemd_property(SYSTEMD_SERVICE_NAME, "ActiveState", system=system) or "unknown"
    last_trigger = _read_systemd_property(SYSTEMD_TIMER_NAME, "LastTriggerUSec", system=system) or "n/a"
    main_pid = _read_systemd_property(SYSTEMD_SERVICE_NAME, "MainPID", system=system) or ""
    pid = int(main_pid) if main_pid.isdigit() and int(main_pid) > 0 else None
    next_elapse = _read_systemd_property(SYSTEMD_TIMER_NAME, "NextElapseUSecRealtime", system=system)
    detail = f"timer={timer_state}, service={service_state}"
    if timer_state == "active" and service_state == "inactive":
        detail += " (worker service is idle between timer runs)"
    return AutoclearStatus(
        backend= "systemd",
        is_running= timer_state == "active",
        pid=pid,
        interval_secs = None,
        last_trigger= last_trigger if last_trigger != "n/a" else next_elapse,
        detail=detail
    )

def _start_with_systemd(*, system:bool)-> str:

    _reload_systemd(system=system)

    if _is_systemd_timer_installed(system=system):
        start_result = _run_systemctl(["start", SYSTEMD_TIMER_NAME], system=system)
        if start_result.returncode != 0:
            raise RuntimeError(start_result.stderr.strip() or "systemctl start timer failed")
        logger.info("Autoclear started with installed systemd timer")
        return "STARTED: Autoclear systemd backend"
    
    enable_result = _run_systemctl(["enable", "--now", SYSTEMD_TIMER_NAME], system=system)
    if enable_result.returncode != 0:
        raise RuntimeError(enable_result.stderr.strip(), "systemctl enable timer failed")

    logger.info("Autoclear started with installed systemd timer")
    return "STARTED: Autoclear systemd backend"

def _stop_with_systemd(*, system:bool)-> str:

    if not _is_systemd_timer_installed(system=system):
        return "STOPPED: Autoclear already stopped"
    
    timer_result = _run_systemctl(["disable", "--now", SYSTEMD_TIMER_NAME], system=system)
    if timer_result.returncode != 0:
        raise RuntimeError(timer_result.stderr.strip() or "Failed to stop systemd timer")
    
    service_result = _run_systemctl(["stop", SYSTEMD_SERVICE_NAME], system=system)
    if service_result.returncode != 0:
        raise RuntimeError(service_result.stderr.strip() or "Failed to stop systemd service")
    
    return "STOPPED: Autoclear systemd backend stopped"

        
def _install_systemd_user(service_content: str, timer_content: str)-> tuple[Path, Path]:

    systemd_dir = _get_systemd_user_dir()
    systemd_dir.mkdir(parents=True, exist_ok=True)

    service_path = systemd_dir / SYSTEMD_SERVICE_NAME
    service_path.write_text(service_content)

    timer_path =  systemd_dir / SYSTEMD_TIMER_NAME 
    timer_path.write_text(timer_content)
    return service_path, timer_path


# public adapter API

def install_systemd_service(*, interval_secs: int, system: bool= False)-> tuple[str, list[str]]:

    service_content = _build_systemd_service(interval_secs=interval_secs, system=system)
    timer_content = _build_systemd_timer(interval_secs)

    if system:
        service_path, timer_path= _install_systemd_system(service_content, timer_content)
        _reload_systemd(system=system)
        return (
            f"Installed/updated system service at {service_path} and timer at {timer_path}",
            [
                "Then run `autoclear start --system` to enable/start the installed timer.",
                "Rerun install-service with a new interval to update the timer.",
            ],
        )

    service_path, timer_path = _install_systemd_user(service_content, timer_content)
    _reload_systemd(system=system)
    return (
        f"Installed/updated user service at {service_path} and timer at {timer_path}",
        [
            f"loginctl enable-linger {getpass.getuser()}",
            "Then run `autoclear start` to enable and start the installed timer.",
            "Rerun install-service with a new interval to update the timer.",
        ],
    )


def is_systemd_service_installed(*, system: bool= False)-> bool:
    
    return _is_systemd_timer_installed(system=system)

def start_systemd_service(*, system:bool = False)-> str:

    return _start_with_systemd(system=system)

def stop_systemd_service(*, system:bool= False)-> str:

    return _stop_with_systemd(system=system)

def get_status_from_systemd(*, system:bool)-> AutoclearStatus:

    return _get_status_from_systemd(system=system)
