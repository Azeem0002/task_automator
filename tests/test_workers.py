from pathlib import Path

import pytest

from task_automator.workers.disk_health_monitor import check_host_health
from task_automator.workers.scheduled_backup import create_backup


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


def test_check_host_health_accepts_zero_disk_threshold(tmp_path: Path) -> None:
    check_host_health(tmp_path, 0.0)


def test_check_host_health_rejects_unreachable_disk_threshold(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Low disk space"):
        check_host_health(tmp_path, 10**9)
