"""Filesystem and process adapter for convention-based worker discovery."""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
from pathlib import Path


_WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
_WORKER_PACKAGE = "task_automator.workers"
_RESERVED_WORKER_STEMS = {"__init__"}


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


def discover_worker_names() -> list[str]:
    """Return safe, runnable worker names from the workers directory."""
    if not _WORKERS_DIR.is_dir():
        return []
    return sorted(
        path.stem
        for path in _WORKERS_DIR.glob("*.py")
        if path.stem not in _RESERVED_WORKER_STEMS
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
    """Start a long-running worker and return its PID plus its observable log."""
    module = require_discovered_worker_module(worker_name)
    log_dir = Path(tempfile.gettempdir()) / "task_automator" / "workers"
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = log_dir / f"{worker_name}.log"
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
    return process.pid, log_path
