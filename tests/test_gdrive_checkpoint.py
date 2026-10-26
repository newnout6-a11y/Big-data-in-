"""Безопасное восстановление checkpoint: сеть и rclone полностью подменены."""
from __future__ import annotations

import json
import shutil
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


def _download(monkeypatch, payload, *, returncode=0, stderr="", restore_code=0, restore_stderr=""):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "copyto" in command:
            destination = Path(command[command.index("copyto") + 2])
            destination.write_text(payload, encoding="utf-8")
            return SimpleNamespace(returncode=returncode, stderr=stderr)
        destination = Path(command[command.index("copy") + 2])
        if restore_code == 0 and command[command.index("copy") + 1].endswith("/pdf/"):
            (destination / "sample.pdf").write_bytes(b"backed up PDF")
        return SimpleNamespace(returncode=restore_code, stderr=restore_stderr)

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


def test_sources_restore_before_installing_checkpoint(monkeypatch, checkpoint):
    checkpoint.write_text("old checkout", encoding="utf-8")
    payload = json.dumps({"sources": {}, "downloaded_ids": ["arxiv:1"]})
    calls = _download(monkeypatch, payload)
    replace = gdrive_rclone.os.replace

    def install(source, destination):
        assert (checkpoint.parent.parent / "all_pdfs" / "sample.pdf").exists()
        assert len(calls) == 6
        replace(source, destination)

    monkeypatch.setattr(gdrive_rclone.os, "replace", install)
    assert gdrive_rclone.подтянуть_state(force=True) == 0
    assert all("copy" in command for command in calls[1:])
    for command, (local, remote, pattern) in zip(calls[1:], gdrive_rclone._МАРШРУТЫ):
        index = command.index("copy")
        assert command[index + 1].endswith(f"/{remote}/")
        assert Path(command[index + 2]) == checkpoint.parent.parent / local
        if pattern:
            assert command[command.index("--include") + 1] == pattern


@pytest.mark.parametrize("code,stderr", [(7, "network down"), (3, "permission denied")])
def test_failed_source_restore_does_not_install_downloaded_ids(monkeypatch, checkpoint, code, stderr):
    checkpoint.write_text("keep checkout", encoding="utf-8")
    payload = json.dumps({"sources": {}, "downloaded_ids": ["arxiv:1"]})
    _download(monkeypatch, payload, restore_code=code, restore_stderr=stderr)
    assert gdrive_rclone.подтянуть_state(force=True) == code
    assert checkpoint.read_text(encoding="utf-8") == "keep checkout"
    assert list(checkpoint.parent.iterdir()) == [checkpoint]


def test_checkpoint_with_no_recoverable_sources_is_rejected(monkeypatch, checkpoint):
    checkpoint.write_text("keep checkout", encoding="utf-8")
    payload = json.dumps({"sources": {}, "downloaded_ids": ["arxiv:1"]})
    _download(monkeypatch, payload, restore_code=3, restore_stderr="ERROR: directory not found")
    assert gdrive_rclone.подтянуть_state(force=True) == 1
    assert checkpoint.read_text(encoding="utf-8") == "keep checkout"


def test_fresh_runner_recovers_failed_embedding_from_sources(monkeypatch, tmp_path):
    """Реальные ingest/embed и временный Qdrant, подменены только сеть и модели."""
    import numpy as np
    import sentence_transformers
    import ingest_v2 as ingest
    import embed_resume_v2 as embed
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, SparseVectorParams, VectorParams

    cloud = tmp_path / "cloud"
    cloud.mkdir()
    first = tmp_path / "first-runner"
    (first / "harvester").mkdir(parents=True)
    (first / "all_pdfs").mkdir()
    (first / "harvested_meta").mkdir()
    (first / "all_pdfs" / "sample.txt").write_text("Chemical reaction recovery regression. " * 15, encoding="utf-8")
    (first / "harvested_meta" / "sample.json").write_text(
        json.dumps({"doc_id": "test:1", "дата": "2024-01-01"}), encoding="utf-8")
    (first / "harvester" / "state.json").write_text(
        json.dumps({"sources": {}, "downloaded_ids": ["test:1"]}), encoding="utf-8")
    monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(first))
    monkeypatch.setattr(gdrive_rclone, "_путь_к_rclone", lambda: "fake-rclone")
    monkeypatch.setenv("GDRIVE_REMOTE", "backup")
    monkeypatch.setenv("GDRIVE_BASE", "corpus")
    monkeypatch.delenv("RCLONE_CONFIG", raising=False)

    def rclone(command, **kwargs):
        operation = "copyto" if "copyto" in command else "copy"
        index = command.index(operation)
        def local(path):
            return cloud / path.split(":", 1)[1] if path.startswith("backup:") else Path(path)
        source, destination = map(local, command[index + 1:index + 3])
        if not source.exists():
            return SimpleNamespace(returncode=3, stderr="directory not found")
        if operation == "copyto":
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        else:
            pattern = command[command.index("--include") + 1] if "--include" in command else "*"
            for file in source.rglob(pattern):
                if file.is_file():
                    target = destination / file.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, target)
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(gdrive_rclone.subprocess, "run", rclone)

    class Model:
        def encode(self, texts, **kwargs):
            return np.array([[1., 0., 0.] for _ in texts])

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda *a: Model())
    monkeypatch.setattr(embed, "SentenceTransformer", lambda *a: Model())
    monkeypatch.setattr(ingest, "подготовить_прототипы", lambda model: ([], [], None))
    monkeypatch.setattr(ingest, "классифицировать_батч", lambda texts, *a: [("chem", "test", 1.) for _ in texts])
    monkeypatch.setattr(embed, "построить_sparse_батч", lambda texts: [([1], [1.]) for _ in texts])

    def use_runner(root):
        monkeypatch.setattr(gdrive_rclone, "_БАЗА", str(root))
        monkeypatch.setattr(ingest, "ПАПКА_PDF", str(root / "all_pdfs"))
        monkeypatch.setattr(ingest, "ПАПКА_МЕТА", str(root / "harvested_meta"))
        monkeypatch.setattr(ingest, "ФАЙЛ_ЧАНКОВ", str(root / "chunks_v2.jsonl"))
        monkeypatch.setattr(embed, "ФАЙЛ_ЧАНКОВ", str(root / "chunks_v2.jsonl"))

    client = QdrantClient(":memory:")
    try:
        client.create_collection(embed.КОЛЛЕКЦИЯ,
                                 vectors_config={"dense": VectorParams(size=3, distance=Distance.COSINE)},
                                 sparse_vectors_config={"sparse": SparseVectorParams()})
        monkeypatch.setattr(embed, "подключиться", lambda: client)
        use_runner(first)
        assert ingest.main([]) == 0
        assert gdrive_rclone.main(["push"]) == 0  # ранний бэкап до embed
        upsert = client.upsert
        def fail(*args, **kwargs):
            raise RuntimeError("runner interrupted during embedding")
        monkeypatch.setattr(client, "upsert", fail)
        with pytest.raises(RuntimeError, match="runner interrupted"):
            embed.main()

        fresh = tmp_path / "fresh-runner"
        use_runner(fresh)
        assert not (fresh / "chunks_v2.jsonl").exists()
        assert gdrive_rclone.main(["pull-state", "--force"]) == 0
        assert json.loads((fresh / "harvester" / "state.json").read_text())["downloaded_ids"] == ["test:1"]
        assert ingest.main([]) == 0
        monkeypatch.setattr(client, "upsert", upsert)
        assert embed.main() == 0
        points = client.scroll(embed.КОЛЛЕКЦИЯ)[0]
        assert points and all(p.payload["doc_id"] == "test:1" for p in points)
        assert embed.main() == 0  # повторная обработка не создаёт дубликаты
        assert client.count(embed.КОЛЛЕКЦИЯ).count == len(points)
    finally:
        client.close()
