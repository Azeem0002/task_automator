"""Periodically check disk free space and fail when it drops below a limit."""

from __future__ import annotations

# ``from __future__`` imports must come directly after the module docstring.
# Put catalog metadata after it so the module stays importable.
WORKER_ARGUMENT_HINT = "Example: --path /home --interval 60s --minimum-free-gb 1"
WORKER_BACKGROUND_SAFE = True

import shutil
import time
from pathlib import Path

import psutil
import typer
from loguru import logger

from ..validators.validation import parse_duration_seconds


def check_host_health(path: Path, minimum_free_gb: float) -> None:
    """Check disk policy and log disk, RAM, and CPU usage for this host."""
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024**3)
    if free_gb < minimum_free_gb:
        raise RuntimeError(f"Low disk space on {path}: {free_gb:.2f} GB free")
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    available_ram_gb = memory.available / (1024**3)
    logger.info(
        "Health check passed: disk {} {:.2f} GB free | RAM {:.1f}% used ({:.2f} GB available) | CPU {:.1f}% used",
        path,
        free_gb,
        memory.percent,
        available_ram_gb,
        cpu_percent,
    )


def run_disk_health_monitor(path: Path, interval: int, minimum_free_gb: float) -> None:
    """Check disk health repeatedly; a supervisor restarts failures."""
    if interval < 1:
        raise ValueError("Health-check interval must be at least one second")
    if minimum_free_gb < 0:
        raise ValueError("Minimum free space cannot be negative")
    while True:
        check_host_health(path, minimum_free_gb)
        time.sleep(interval)


app = typer.Typer(help="Periodically check host disk free space.")


@app.command()
def main(
    path: Path = typer.Option(Path.home(), exists=True, file_okay=False),
    interval: str = typer.Option("60s", "--interval", "-i", help="Interval, e.g. 60s, 5m, or 2h"),
    minimum_free_gb: float = typer.Option(1.0, min=0.0),
) -> None:
    """Start continuous disk-health monitoring."""
    try:
        interval_seconds = parse_duration_seconds(interval, field_name="health-check interval")
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--interval") from error
    run_disk_health_monitor(path.expanduser(), interval_seconds, minimum_free_gb)


if __name__ == "__main__":
    app()
