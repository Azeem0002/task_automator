"""Crash-recoverable backup worker for systemd or another supervisor."""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import typer
from loguru import logger


def create_backup(source: Path, destination: Path) -> Path:
    """Create one timestamped snapshot and return its path."""
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    source = source.resolve()
    destination = destination.expanduser().resolve()
    if destination == source or source in destination.parents:
        raise ValueError("Backup destination must not be inside the source directory")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{source.name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    # A failed copy raises so systemd can restart the worker instead of
    # reporting a false success.
    shutil.copytree(source, target)
    return target


def run_backup_worker(source: Path, destination: Path, interval: int) -> None:
    """Run backups continuously; supervisors own crash recovery."""
    if interval < 1:
        raise ValueError("Backup interval must be at least one second")
    while True:
        backup_path = create_backup(source, destination)
        logger.success("Backup created: {}", backup_path)
        time.sleep(interval)


app = typer.Typer(help="Run the crash-recoverable backup worker.")


@app.command()
def main(source: Path, destination: Path, interval: int = typer.Option(3600, min=1)) -> None:
    """Create periodic directory snapshots."""
    run_backup_worker(source.expanduser(), destination.expanduser(), interval)


if __name__ == "__main__":
    app()
