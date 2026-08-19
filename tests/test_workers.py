from pathlib import Path

import pytest
from typer.testing import CliRunner

from task_automator.cli import controller
from task_automator.adapters.worker_catalog_adapter import discover_background_worker_names
from task_automator.workers import scheduled_backup
from task_automator.workers.disk_health_monitor import check_host_health
from task_automator.workers.scheduled_backup import create_backup


runner = CliRunner()


def test_create_backup_copies_a_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.txt").write_text("safe copy", encoding="utf-8")

    result = create_backup(source, tmp_path / "backups")

    assert result.name.startswith("source-")
    assert (result / "note.txt").read_text(encoding="utf-8") == "safe copy"


def test_create_backup_rejects_destination_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(ValueError, match="must not be inside"):
        create_backup(source, source / "backups")


def test_create_backup_uses_app_owned_default_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.txt").write_text("safe copy", encoding="utf-8")
    default_destination = tmp_path / "app-data" / "backups"
    monkeypatch.setattr(scheduled_backup, "get_default_backup_directory", lambda: default_destination)

    result = scheduled_backup.create_backup(source)

    assert result.parent == default_destination
    assert (result / "note.txt").read_text(encoding="utf-8") == "safe copy"


def test_check_host_health_accepts_zero_disk_threshold(tmp_path: Path) -> None:
    check_host_health(tmp_path, 0.0)


def test_check_host_health_rejects_unreachable_disk_threshold(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Low disk space"):
        check_host_health(tmp_path, 10**9)


def test_only_explicitly_opted_in_workers_are_background_safe() -> None:
    assert {"disk_health_monitor", "scheduled_backup"}.issubset(discover_background_worker_names())
    assert "autoclear" not in discover_background_worker_names()


def test_worker_cli_exposes_lifecycle_commands_and_forwards_duration_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """The generic CLI must preserve worker options instead of parsing them itself."""
    received: dict[str, object] = {}
    monkeypatch.setattr(
        controller,
        "run_discovered_worker",
        lambda name, arguments: received.update(name=name, arguments=arguments) or 0,
    )

    help_result = runner.invoke(controller.app, ["workers", "--help"])
    run_result = runner.invoke(
        controller.app,
        ["workers", "run", "disk_health_monitor", "--interval", "60s"],
    )

    assert help_result.exit_code == 0
    assert all(command in help_result.stdout for command in ("start", "status", "stop", "logs"))
    assert run_result.exit_code == 0
    assert received == {"name": "disk_health_monitor", "arguments": ["--interval", "60s"]}
