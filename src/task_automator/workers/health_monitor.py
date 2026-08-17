"""Lightweight host health monitor intended for systemd supervision."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import typer
from loguru import logger


def check_disk(path: Path, minimum_free_gb: float) -> None:
    """Raise when free space falls below the configured operational floor."""
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024**3)
    if free_gb < minimum_free_gb:
        raise RuntimeError(f"Low disk space on {path}: {free_gb:.2f} GB free")
    logger.info("Health check passed: {} has {:.2f} GB free", path, free_gb)


def run_health_monitor(path: Path, interval: int, minimum_free_gb: float) -> None:
    """Run checks continuously; an uncaught failure lets systemd restart us."""
    if interval < 1:
        raise ValueError("Health-check interval must be at least one second")
    if minimum_free_gb < 0:
        raise ValueError("Minimum free space cannot be negative")
    while True:
        check_disk(path, minimum_free_gb)
        time.sleep(interval)


app = typer.Typer(help="Run the host health monitor worker.")


@app.command()
def main(
    path: Path = typer.Option(Path.home(), exists=True, file_okay=False),
    interval: int = typer.Option(60, min=1),
    minimum_free_gb: float = typer.Option(1.0, min=0.0),
) -> None:
    """Monitor disk health until stopped by the supervisor."""
    run_health_monitor(path.expanduser(), interval, minimum_free_gb)


if __name__ == "__main__":
    app()
