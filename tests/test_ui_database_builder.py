"""Сборка выборок проверяется на временном Qdrant, без рабочей базы."""
from __future__ import annotations

import json
import runpy
import sys
from contextlib import closing
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

import build_balanced_ui_databases as builder


def _point(point_id, domain="chemistry", **overrides):
    point = {
        "id": point_id,
        "vector": {"dense": [1.0, 0.0, 0.0], "sparse": {"indices": [1], "values": [1.0]}},
        "payload": {"domain": domain, "subdomain": "test"},
    }
    point.update(overrides)
    return point


@pytest.fixture(autouse=True)
def small_vectors(monkeypatch):
    monkeypatch.setattr(builder, "РАЗМЕР_ВЕКТОРА", 3)
    monkeypatch.setattr(builder, "ПОЛЯ_ИНДЕКСОВ", [])


def test_invalid_vectors_do_not_consume_sampling_quota(tmp_path):
    source = tmp_path / "input.jsonl"
    rows = [
        _point(1),
        _point(2, vector={"dense": [1.0], "sparse": {"indices": [1], "values": [1.0]}}),
        _point(3),
        _point(4, vector={"dense": [1.0, 0.0, 0.0], "sparse": {"indices": [1, 2], "values": [1.0]}}),
        _point(5, "it"),
        _point(6, "it"),
        _point(7, "it", vector={"dense": [1.0, 0.0, 0.0], "sparse": {"indices": [], "values": []}}),
        _point("invalid-id"),
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\nnull\n{broken\n", encoding="utf-8")
    output = tmp_path / "databases"

    assert builder.main(["--input", str(source), "--output-dir", str(output), "--sizes", "4", "--batch", "2"]) == 0

    with closing(QdrantClient(path=str(output / "4"))) as client:
        points, _ = client.scroll(builder.КОЛЛЕКЦИЯ, limit=10)
        assert len(points) == 4
        assert sum(p.payload["domain"] == "chemistry" for p in points) == 2
        assert sum(p.payload["domain"] == "it" for p in points) == 2


@pytest.mark.parametrize("vector", [
    {"dense": [1.0, float("nan"), 0.0], "sparse": {"indices": [1], "values": [1.0]}},
    {"dense": [10**500, 0.0, 0.0], "sparse": {"indices": [1], "values": [1.0]}},
    {"dense": [1.0, 0.0, 0.0], "sparse": {"indices": [1], "values": [float("inf")]}},
    {"dense": [1.0, 0.0, 0.0], "sparse": {"indices": [-1], "values": [1.0]}},
    {"dense": [1.0, 0.0, 0.0], "sparse": {"indices": [1, 1], "values": [1.0, 1.0]}},
    {"dense": [1.0, 0.0, 0.0]},
])
def test_malformed_vectors_are_rejected(vector):
    assert builder._точка_из_obj(_point(1, vector=vector)) is None


def test_duplicate_ids_are_counted_once_in_both_sampling_passes(tmp_path):
    source = tmp_path / "input.jsonl"
    rows = [_point(1), _point(1, "it"), _point(2, "it"), _point(3, "it")]
    source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    output = tmp_path / "databases"

    assert builder.main(["--input", str(source), "--output-dir", str(output), "--sizes", "3"]) == 0
    with closing(QdrantClient(path=str(output / "3"))) as client:
        points, _ = client.scroll(builder.КОЛЛЕКЦИЯ, limit=10)
        assert {point.id for point in points} == {1, 2, 3}
        assert next(point for point in points if point.id == 1).payload["domain"] == "chemistry"


def test_existing_database_requires_explicit_recreate(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_text(json.dumps(_point(1)), encoding="utf-8")
    output = tmp_path / "databases"
    args = ["--input", str(source), "--output-dir", str(output), "--sizes", "1"]
    assert builder.main(args) == 0
    source.write_text(json.dumps(_point(2)), encoding="utf-8")

    assert builder.main(args) == 1
    with closing(QdrantClient(path=str(output / "1"))) as client:
        assert [p.id for p in client.scroll(builder.КОЛЛЕКЦИЯ)[0]] == [1]

    assert builder.main([*args, "--recreate"]) == 0
    with closing(QdrantClient(path=str(output / "1"))) as client:
        assert [p.id for p in client.scroll(builder.КОЛЛЕКЦИЯ)[0]] == [2]


def test_recreate_does_not_delete_a_database_open_in_another_client(tmp_path):
    path = tmp_path / "database"
    with closing(builder._создать_коллекцию(path, False)) as owner:
        owner.upsert(builder.КОЛЛЕКЦИЯ, [builder._точка_из_obj(_point(1))])
        with pytest.raises(RuntimeError, match="already accessed"):
            builder._создать_коллекцию(path, True)
        assert owner.count(builder.КОЛЛЕКЦИЯ).count == 1
    with closing(QdrantClient(path=str(path))) as client:
        assert client.count(builder.КОЛЛЕКЦИЯ).count == 1


def test_later_database_lock_preserves_all_earlier_databases(tmp_path):
    source = tmp_path / "input.jsonl"
    source.write_text(json.dumps(_point(2)), encoding="utf-8")
    output = tmp_path / "databases"
    with closing(builder._создать_коллекцию(output / "1", False)) as first:
        first.upsert(builder.КОЛЛЕКЦИЯ, [builder._точка_из_obj(_point(1))])
    with closing(builder._создать_коллекцию(output / "2", False)) as owner:
        owner.upsert(builder.КОЛЛЕКЦИЯ, [builder._точка_из_obj(_point(3))])
        with pytest.raises(RuntimeError, match="already accessed"):
            builder.main(["--input", str(source), "--output-dir", str(output),
                          "--sizes", "1,2", "--recreate"])
        # Повторное открытие также подтверждает освобождение первой блокировки.
        with closing(QdrantClient(path=str(output / "1"))) as first:
            assert [p.id for p in first.scroll(builder.КОЛЛЕКЦИЯ)[0]] == [1]
        assert [p.id for p in owner.scroll(builder.КОЛЛЕКЦИЯ)[0]] == [3]


@pytest.mark.parametrize("args", [["--sizes", ""], ["--sizes", "0"], ["--batch", "0"], ["--batch", "-1"]])
def test_invalid_options_fail_before_creating_databases(tmp_path, args):
    output = tmp_path / "databases"
    with pytest.raises(SystemExit) as exc:
        builder.main(["--output-dir", str(output), *args])
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("size", [50, 100, 150, 200])
def test_size_shortcuts_preserve_explicit_recreate_choice(monkeypatch, size):
    calls = []
    monkeypatch.setattr(builder, "main", lambda args: calls.append(args) or 0)
    script = Path(builder.__file__).with_name(f"build_ui_db_{size}k.py")
    for extra in ([], ["--recreate"]):
        monkeypatch.setattr(sys, "argv", [str(script), *extra])
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(script), run_name="__main__")
        assert exc.value.code == 0
        assert calls[-1] == ["--sizes", str(size * 1000), *extra]


def test_balancing_remainder_is_repeatable():
    assert builder._waterfill({"b": 10, "a": 10}, 3) == {"a": 2, "b": 1}
