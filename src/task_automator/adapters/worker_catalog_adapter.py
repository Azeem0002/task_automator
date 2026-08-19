"""Filesystem and process adapter for convention-based worker discovery."""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import psutil
from platformdirs import PlatformDirs


_WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
_WORKER_PACKAGE = "task_automator.workers"
_RESERVED_WORKER_STEMS = {"__init__"}


@dataclass(frozen=True)
class BackgroundWorkerStatus:
    """Observable lifecycle state for one controller-managed worker."""

    worker_name: str
    is_running: bool
    pid: int | None
    log_path: Path


def _background_state_dir() -> Path:
    """Return the app-owned directory for generic worker PID files."""
    return Path(PlatformDirs("task-automator", "Al-Azeem").user_state_dir) / "workers"


def _background_pid_path(worker_name: str) -> Path:
    require_discovered_worker_module(worker_name)
    return _background_state_dir() / f"{worker_name}.pid"


def _background_log_path(worker_name: str) -> Path:
    """Return the durable preferred log path, with a writable /tmp fallback."""
    preferred = _background_state_dir() / f"{worker_name}.log"
    try:
        preferred.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with preferred.open("a", encoding="utf-8"):
            pass
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "task_automator" / "workers" / f"{worker_name}.log"
        fallback.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return fallback


def _managed_worker_pid(worker_name: str) -> int | None:
    """Return a live PID only when it still runs this exact discovered module."""
    pid_path = _background_pid_path(worker_name)
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        process = psutil.Process(pid)
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            raise psutil.NoSuchProcess(pid)
        if require_discovered_worker_module(worker_name) not in process.cmdline():
            raise psutil.NoSuchProcess(pid)
        return pid
    except (FileNotFoundError, ValueError, OSError, psutil.Error):
        pid_path.unlink(missing_ok=True)
        return None


def worker_details(worker_name: str) -> tuple[str, str]:
    """Read optional worker metadata without importing arbitrary worker code."""
    require_discovered_worker_module(worker_name)
    tree = ast.parse((_WORKERS_DIR / f"{worker_name}.py").read_text(encoding="utf-8"))
    purpose = (ast.get_docstring(tree) or "No worker description provided.").splitlines()[0]
    hint = "Use `-- --help` to view this worker's options."
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            if any(isinstance(target, ast.Name) and target.id == "WORKER_DESCRIPTION" for target in node.targets):
                purpose = node.value.value
            if any(isinstance(target, ast.Name) and target.id == "WORKER_ARGUMENT_HINT" for target in node.targets):
                hint = node.value.value
    return purpose, hint


def is_background_worker(worker_name: str) -> bool:
    """Return whether a worker explicitly opts into detached execution.

    Defaulting to ``False`` is deliberate. A future worker might need a TTY,
    be a short one-shot task, or have unsafe detach semantics; file discovery
    alone is not enough authority to run it in the background.
    """
    require_discovered_worker_module(worker_name)
    tree = ast.parse((_WORKERS_DIR / f"{worker_name}.py").read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and node.value.value is True
        and any(isinstance(target, ast.Name) and target.id == "WORKER_BACKGROUND_SAFE" for target in node.targets)
        for node in tree.body
    )


def discover_background_worker_names() -> list[str]:
    """Return only workers that explicitly declared detached execution safe."""
    return [name for name in discover_worker_names() if is_background_worker(name)]


def require_background_worker(worker_name: str) -> None:
    """Reject workers that were not explicitly designed for detached execution."""
    if not is_background_worker(worker_name):
        raise ValueError(f"Worker '{worker_name}' is foreground-only; set WORKER_BACKGROUND_SAFE = True to opt in.")


def discover_worker_names(*, include_terminal_bound: bool = False) -> list[str]:
    """Return safe worker modules; hide terminal-bound autoclear by default.

    Autoclear has its own explicit lifecycle group and is not a generic worker
    the user should start through ``workers run`` or ``workers start``.
    """
    if not _WORKERS_DIR.is_dir():
        return []
    return sorted(
        path.stem
        for path in _WORKERS_DIR.glob("*.py")
        if path.stem not in _RESERVED_WORKER_STEMS
        and (include_terminal_bound or path.stem != "autoclear")
        and not path.stem.startswith("_")
        and path.stem.isidentifier()
    )


def require_discovered_worker_module(worker_name: str) -> str:
    """Return an approved module path or reject traversal and unknown workers."""
    normalized = worker_name.strip()
    worker_names = discover_worker_names()
    if normalized not in worker_names:
        available = ", ".join(worker_names) or "none"
        raise ValueError(f"Unknown worker '{worker_name}'. Available workers: {available}")
    return f"{_WORKER_PACKAGE}.{normalized}"


def run_discovered_worker(worker_name: str, arguments: list[str]) -> int:
    """Run one discovered worker in the foreground without invoking a shell."""
    return subprocess.run(
        [sys.executable, "-m", require_discovered_worker_module(worker_name), *arguments],
        cwd=str(Path(__file__).resolve().parents[2]),
        check=False,
    ).returncode


def spawn_discovered_worker(worker_name: str, arguments: list[str]) -> tuple[int, Path]:
    """Start one managed background worker and persist its PID for later control."""
    module = require_discovered_worker_module(worker_name)
    require_background_worker(worker_name)
    if _managed_worker_pid(worker_name) is not None:
        raise RuntimeError(f"Worker '{worker_name}' is already running")
    log_path = _background_log_path(worker_name)
    log_file = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", module, *arguments],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_file.close()
    pid_path = _background_pid_path(worker_name)
    pid_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    pid_path.write_text(str(process.pid), encoding="utf-8")
    return process.pid, log_path


def get_background_worker_status(worker_name: str) -> BackgroundWorkerStatus:
    """Report whether one controller-managed background worker is still alive."""
    return BackgroundWorkerStatus(
        worker_name=worker_name,
        is_running=(pid := _managed_worker_pid(worker_name)) is not None,
        pid=pid,
        log_path=_background_log_path(worker_name),
    )


def stop_background_worker(worker_name: str) -> BackgroundWorkerStatus:
    """Stop one managed worker without trusting a stale or reused PID."""
    pid = _managed_worker_pid(worker_name)
    if pid is None:
        return get_background_worker_status(worker_name)
    process = psutil.Process(pid)
    process.terminate()
    try:
        process.wait(timeout=5)
    except psutil.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    _background_pid_path(worker_name).unlink(missing_ok=True)
    return get_background_worker_status(worker_name)
