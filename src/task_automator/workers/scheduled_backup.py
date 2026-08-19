"""Periodically copy one source directory into timestamped backup snapshots."""

from __future__ import annotations

# ``from __future__`` imports must come directly after the module docstring.
# Put catalog metadata after it so the module stays importable.
WORKER_ARGUMENT_HINT = "Example: /source/path --interval 1h (optional: --destination /backup/path)"
WORKER_BACKGROUND_SAFE = True

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import typer
from loguru import logger
from platformdirs import PlatformDirs

from ..validators.validation import parse_duration_seconds


def get_default_backup_directory() -> Path:
    """Return the Organizer-style OS-native location for Task Automator backups.

    On Linux this is normally ``~/.local/share/task-automator/backups``.
    The directory is app-owned, rather than being guessed from the current
    working directory or forced on every user as a CLI argument.
    """
    return Path(PlatformDirs("task-automator", "Al-Azeem").user_data_dir) / "backups"


def create_backup(source: Path, destination: Path | None = None) -> Path:
    """Create one timestamped snapshot and return its path."""
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    source = source.resolve()
    destination = (destination or get_default_backup_directory()).expanduser().resolve()
    if destination == source or source in destination.parents:
        raise ValueError("Backup destination must not be inside the source directory")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{source.name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    shutil.copytree(source, target)
    return target


def run_scheduled_backup(source: Path, destination: Path | None, interval: int) -> None:
    """Create snapshots repeatedly; a supervisor owns crash recovery."""
    if interval < 1:
        raise ValueError("Backup interval must be at least one second")
    while True:
        backup_path = create_backup(source, destination)
        logger.success("Backup created: {}", backup_path)
        typer.echo(f"BACKUP_PATH={backup_path}")
        time.sleep(interval)


app = typer.Typer(help="Periodically create timestamped directory backups.")


@app.command()
def main(
    source: Path,
    destination: Path | None = typer.Option(None, "--destination", "-d", help="Optional backup directory"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Interval, e.g. 60s, 5m, or 2h"),
) -> None:
    """Start scheduled directory backups."""
    try:
        interval_seconds = parse_duration_seconds(interval, field_name="backup interval")
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--interval") from error
    run_scheduled_backup(source.expanduser(), destination.expanduser() if destination else None, interval_seconds)


if __name__ == "__main__":
    app()
