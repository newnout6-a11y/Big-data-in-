"""CLI-коды ошибок не должны скрывать сбои загрузки и этапов пайплайна."""
from __future__ import annotations

import json

import pytest

from harvester import gdrive_rclone, harvest_full


@pytest.fixture
def drive_data(tmp_path, monkeypatch):
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    monkeypatch.setattr(gdrive_rclone, "_путь_к_rclone", lambda: "fake-rclone")
    for folder, filename in [
        ("harvester", "state.json"), ("all_pdfs", "sample.pdf"),
        ("harvested_meta", "sample.json"), ("extracted_images", "sample.png"),
    ]:
        directory = tmp_path / folder
        directory.mkdir()
        (directory / filename).write_text("sample", encoding="utf-8")


@pytest.mark.parametrize("codes", [[1, 1, 1, 1, 1], [1, 0, 0, 0, 0], [0, 0, 1, 0, 0]])
def test_push_reports_failure_after_attempting_every_backup_route(drive_data, monkeypatch, codes):
    calls = []
    def execute(command, dry_run):
        calls.append(command)
        return codes[len(calls) - 1]
    monkeypatch.setattr(gdrive_rclone, "_выполнить", execute)

    assert gdrive_rclone.main(["push"]) == 1
    assert len(calls) == 5
    assert all("copyto" not in command for command in calls)
    assert calls[-1][calls[-1].index("copy") + 2].endswith("/images/")


def test_checkpoint_is_published_only_after_successful_data_uploads(drive_data, monkeypatch):
    calls = []
    def execute(command, dry_run):
        calls.append(command)
        return 0
    monkeypatch.setattr(gdrive_rclone, "_выполнить", execute)

    assert gdrive_rclone.залить(strict=True) == 6
    assert len(calls) == 6
    assert all("copy" in command for command in calls[:-1])
    assert "copyto" in calls[-1]
    assert calls[-1][calls[-1].index("copyto") + 2].endswith("/state/state.json")


def test_failed_checkpoint_upload_is_reported_after_data_backup(drive_data, monkeypatch):
    calls = []
    def execute(command, dry_run):
        calls.append(command)
        return 1 if "copyto" in command else 0
    monkeypatch.setattr(gdrive_rclone, "_выполнить", execute)

    assert gdrive_rclone.main(["push"]) == 1
    assert len(calls) == 6
    assert "copyto" in calls[-1]


def test_legacy_push_still_returns_number_of_successful_routes(drive_data, monkeypatch):
    codes = iter([1, 0, 0, 0, 0])
    monkeypatch.setattr(gdrive_rclone, "_выполнить", lambda *args: next(codes))
    assert gdrive_rclone.залить() == 4


def test_state_only_cli_returns_failure(drive_data, monkeypatch):
    monkeypatch.setattr(gdrive_rclone, "_выполнить", lambda *args: 1)
    assert gdrive_rclone.main(["push", "--state-only"]) == 1


def test_state_only_cli_fails_when_local_checkpoint_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    monkeypatch.setattr(gdrive_rclone, "_путь_к_rclone", lambda: "fake-rclone")
    def unexpected(*args):
        pytest.fail("Нет файла для загрузки")
    monkeypatch.setattr(gdrive_rclone, "_выполнить", unexpected)
    assert gdrive_rclone.main(["push", "--state-only"]) == 1
    assert gdrive_rclone.залить(только_state=True) == 0


def test_push_dry_run_is_successful_without_running_rclone(drive_data, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("dry-run must not execute subprocess")
    monkeypatch.setattr(gdrive_rclone.subprocess, "run", unexpected)
    assert gdrive_rclone.main(["push", "--dry-run"]) == 0


@pytest.fixture
def pipeline_run(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    monkeypatch.setattr(harvest_full, "ПАПКА_ЛОГОВ", str(logs))
    monkeypatch.setenv("GDRIVE_REMOTE", "test-drive")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)
    return logs


_STEPS = ["gdrive_pull_state", "harvest", "ingest", "gdrive_push_after_ingest", "embed", "s3_upload", "gdrive_push"]


@pytest.mark.parametrize("failed_step", [None, *_STEPS])
def test_pipeline_reports_errors_after_all_backups(pipeline_run, monkeypatch, failed_step):
    commands = []
    def run(command, env=None):
        step = _STEPS[len(commands)]
        commands.append(command)
        return (7 if step == failed_step else 0), 0.1
    monkeypatch.setattr(harvest_full, "_запустить", run)

    assert harvest_full.main(["--budget", "1", "--time-limit-min", "5"]) == int(failed_step is not None)
    assert len(commands) == len(_STEPS)
    assert commands[-1][-1] == "push"
    report = json.loads(next(pipeline_run.glob("run_*.json")).read_text(encoding="utf-8"))
    assert list(report["steps"]) == _STEPS
    if failed_step:
        assert report["steps"][failed_step]["return_code"] == 7
    assert report["finished_at"]


def test_deadline_marks_unfinished_required_steps_but_still_backs_up(pipeline_run, monkeypatch):
    clock = [0.0]
    commands = []
    monkeypatch.setattr(harvest_full.time, "time", lambda: clock[0])
    def run(command, env=None):
        commands.append(command)
        if "harvester.run" in command:
            clock[0] = 61.0
        return 0, 0.1
    monkeypatch.setattr(harvest_full, "_запустить", run)

    assert harvest_full.main(["--budget", "1", "--time-limit-min", "1"]) == 1
    assert [command[-1] for command in commands if "harvester.gdrive_rclone" in command] == ["pull-state", "push", "push"]
    report = json.loads(next(pipeline_run.glob("run_*.json")).read_text(encoding="utf-8"))
    assert report["steps"]["ingest"]["return_code"] == 124
    assert report["steps"]["embed"]["return_code"] == 124


def test_intentionally_skipped_steps_are_not_failures(pipeline_run, monkeypatch):
    monkeypatch.setattr(harvest_full, "_запустить", lambda *args: (0, 0.1))
    assert harvest_full.main(["--skip-ingest", "--skip-embed"]) == 0
