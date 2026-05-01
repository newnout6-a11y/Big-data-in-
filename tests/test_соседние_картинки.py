"""Тесты `notebooks.собрать_картинки_по_страницам`.

Тестируем что индекс `(file_hash, page) -> [images]` строится корректно по
содержимому коллекции, не включает чанки других тетрадей и других файлов,
и дедупит картинки в пределах одной страницы.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notebooks  # noqa: E402


def _точка(payload: dict):
    return SimpleNamespace(payload=payload)


def test_собирает_картинки_по_странице(monkeypatch):
    клиент = MagicMock()
    клиент.scroll.return_value = (
        [
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
                "page": 1, "images": [{"path": "extracted_images/h1/p1.png", "page": 1}],
            }),
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
                "page": 2, "images": [
                    {"path": "extracted_images/h1/p2_a.png", "page": 2},
                    {"path": "extracted_images/h1/p2_b.png", "page": 2},
                ],
            }),
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
                "page": 3, "images": [],
            }),
        ],
        None,
    )
    monkeypatch.setattr(notebooks, "ensure_collection", lambda *a, **kw: None)

    индекс = notebooks.собрать_картинки_по_страницам(
        клиент, {"id": "nb1", "collection": "user_nb1"}, {"h1"}, user_id="u1",
    )
    assert ("h1", 1) in индекс
    assert ("h1", 2) in индекс
    assert ("h1", 3) not in индекс  # пустые images не попадают
    assert len(индекс[("h1", 2)]) == 2


def test_фильтрует_по_file_hash(monkeypatch):
    клиент = MagicMock()
    клиент.scroll.return_value = (
        [
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
                "page": 1, "images": [{"path": "p1.png"}],
            }),
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "ДРУГОЙ",
                "page": 1, "images": [{"path": "drugoy.png"}],
            }),
        ],
        None,
    )
    monkeypatch.setattr(notebooks, "ensure_collection", lambda *a, **kw: None)

    индекс = notebooks.собрать_картинки_по_страницам(
        клиент, {"id": "nb1", "collection": "c1"}, {"h1"}, user_id="u1",
    )
    assert ("h1", 1) in индекс
    assert ("ДРУГОЙ", 1) not in индекс


def test_дедуп_по_path_внутри_страницы(monkeypatch):
    клиент = MagicMock()
    клиент.scroll.return_value = (
        [
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
                "page": 5, "images": [{"path": "same.png"}],
            }),
            _точка({
                "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
                "page": 5, "images": [{"path": "same.png"}, {"path": "other.png"}],
            }),
        ],
        None,
    )
    monkeypatch.setattr(notebooks, "ensure_collection", lambda *a, **kw: None)

    индекс = notebooks.собрать_картинки_по_страницам(
        клиент, {"id": "nb1", "collection": "c1"}, {"h1"}, user_id="u1",
    )
    пути = [img["path"] for img in индекс[("h1", 5)]]
    assert sorted(пути) == ["other.png", "same.png"]


def test_пустой_список_file_hashes_возвращает_пустой_словарь():
    клиент = MagicMock()
    индекс = notebooks.собрать_картинки_по_страницам(
        клиент, {"id": "nb1", "collection": "c1"}, set(), user_id="u1",
    )
    assert индекс == {}
    клиент.scroll.assert_not_called()


def test_paginates_через_offset(monkeypatch):
    клиент = MagicMock()
    клиент.scroll.side_effect = [
        ([_точка({
            "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
            "page": 1, "images": [{"path": "a.png"}],
        })], "next-offset"),
        ([_точка({
            "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
            "page": 2, "images": [{"path": "b.png"}],
        })], None),
    ]
    monkeypatch.setattr(notebooks, "ensure_collection", lambda *a, **kw: None)

    индекс = notebooks.собрать_картинки_по_страницам(
        клиент, {"id": "nb1", "collection": "c1"}, {"h1"}, user_id="u1",
    )
    assert ("h1", 1) in индекс
    assert ("h1", 2) in индекс
    assert клиент.scroll.call_count == 2
