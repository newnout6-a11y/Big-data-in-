"""Безопасное восстановление checkpoint: сеть и rclone полностью подменены."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from harvester import gdrive_rclone


@pytest.fixture
def checkpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(tmp_path))
    monkeypatch.setattr(gdrive_rclone, "_путь_к_rclone", lambda: "rclone")
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)
    state = tmp_path / "harvester" / "state.json"
    state.parent.mkdir()
    return state


def _download(monkeypatch, payload, *, returncode=0, stderr=""):
    calls = []

    def run(command, **kwargs):
        destination = Path(command[command.index("copyto") + 2])
        destination.write_text(payload, encoding="utf-8")
        calls.append(command)
        return SimpleNamespace(returncode=returncode, stderr=stderr)

    monkeypatch.setattr(gdrive_rclone.subprocess, "run", run)
    return calls


def test_regular_pull_preserves_newer_local_loop_state(monkeypatch, checkpoint):
    checkpoint.write_text("local checkpoint", encoding="utf-8")
    calls = _download(monkeypatch, json.dumps({"sources": {}, "downloaded_ids": []}))

    assert gdrive_rclone.подтянуть_state() == 0
    assert checkpoint.read_text(encoding="utf-8") == "local checkpoint"
    assert calls == []


@pytest.mark.parametrize("version", [2, 3, 4])
def test_force_replaces_checkout_state_only_after_valid_download(monkeypatch, checkpoint, version):
    checkpoint.write_text("old Git checkout", encoding="utf-8")
    payload = json.dumps({"version": version, "sources": {"arxiv": {"last_index": 12}}, "downloaded_ids": ["arxiv:1"]})
    calls = _download(monkeypatch, payload)
    replace = gdrive_rclone.os.replace
    replacements = []

    def atomic_replace(source, destination):
        assert checkpoint.read_text(encoding="utf-8") == "old Git checkout"
        assert json.loads(Path(source).read_text(encoding="utf-8"))["downloaded_ids"] == ["arxiv:1"]
        replacements.append((source, destination))
        replace(source, destination)

    monkeypatch.setattr(gdrive_rclone.os, "replace", atomic_replace)
    assert gdrive_rclone.подтянуть_state(force=True) == 0
    assert checkpoint.read_text(encoding="utf-8") == payload
    assert len(replacements) == 1
    assert str(checkpoint) not in calls[0]
    assert "--ignore-existing" not in calls[0]
    assert list(checkpoint.parent.iterdir()) == [checkpoint]


@pytest.mark.parametrize(
    "payload",
    [
        "{broken",
        "[]",
        "{}",
        '{"sources": [], "downloaded_ids": []}',
        '{"sources": {}, "downloaded_ids": {}}',
        '{"sources": {}, "downloaded_ids": [{}]}',
        '{"sources": {}, "downloaded_ids": [], "normalized_ids": {}}',
    ],
)
def test_invalid_remote_checkpoint_never_replaces_local(monkeypatch, checkpoint, payload):
    checkpoint.write_text("keep local", encoding="utf-8")
    _download(monkeypatch, payload)
    assert gdrive_rclone.подтянуть_state(force=True) != 0
    assert checkpoint.read_text(encoding="utf-8") == "keep local"
    assert list(checkpoint.parent.iterdir()) == [checkpoint]


def test_failed_download_keeps_local_and_removes_partial_file(monkeypatch, checkpoint):
    checkpoint.write_text("keep local", encoding="utf-8")
    _download(monkeypatch, "partial download", returncode=7, stderr="network connection failed")
    assert gdrive_rclone.подтянуть_state(force=True) == 7
    assert checkpoint.read_text(encoding="utf-8") == "keep local"
    assert list(checkpoint.parent.iterdir()) == [checkpoint]


def test_missing_remote_checkpoint_is_a_valid_first_run(monkeypatch, checkpoint):
    checkpoint.write_text("keep checkout", encoding="utf-8")
    _download(monkeypatch, "", returncode=3, stderr="ERROR: object not found")
    assert gdrive_rclone.подтянуть_state(force=True) == 0
    assert checkpoint.read_text(encoding="utf-8") == "keep checkout"
    assert list(checkpoint.parent.iterdir()) == [checkpoint]


def test_pull_without_local_checkpoint_installs_valid_remote(monkeypatch, checkpoint):
    payload = json.dumps({"sources": {}, "downloaded_ids": []})
    _download(monkeypatch, payload)
    assert gdrive_rclone.подтянуть_state() == 0
    assert checkpoint.read_text(encoding="utf-8") == payload


def test_force_dry_run_does_not_touch_local_checkpoint(monkeypatch, checkpoint):
    checkpoint.write_text("keep local", encoding="utf-8")
    calls = _download(monkeypatch, "")
    assert gdrive_rclone.подтянуть_state(force=True, dry_run=True) == 0
    assert checkpoint.read_text(encoding="utf-8") == "keep local"
    assert calls == []
    assert list(checkpoint.parent.iterdir()) == [checkpoint]


def test_cli_propagates_pull_failure_and_force(monkeypatch):
    calls = []

    def pull(**kwargs):
        calls.append(kwargs)
        return 7

    monkeypatch.setattr(gdrive_rclone, "подтянуть_state", pull)
    assert gdrive_rclone.main(["pull-state", "--force"]) == 7
    assert calls == [{"dry_run": False, "force": True}]


def test_explicit_restore_reports_missing_rclone(monkeypatch, checkpoint):
    checkpoint.write_text("keep local", encoding="utf-8")
    monkeypatch.setattr(gdrive_rclone, "_путь_к_rclone", lambda: None)
    assert gdrive_rclone.main(["pull-state", "--force"]) == 127
    assert checkpoint.read_text(encoding="utf-8") == "keep local"
