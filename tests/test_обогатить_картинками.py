"""Тесты `app.обогатить_картинками_соседних_страниц`.

Когда фрагмент ничего не имеет в `images` (например, он со страницы
библиографии), но в результатах поиска ЕСТЬ соседние страницы того же
документа со встроенными картинками — UI должен подставить их через
`images_neighbors`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def app_module(monkeypatch):
    """Импортирует `app.py` с заглушками для streamlit-побочки.

    Сам импорт уже проверялся, но тут просто гарантируем, что модуль
    загружен и сделанные нами правки видны.
    """
    if "app" in sys.modules:
        return sys.modules["app"]
    import app  # noqa: F401
    return sys.modules["app"]


def test_подставляет_картинки_с_соседних_страниц(app_module, monkeypatch):
    """Фрагмент со стр. 12 (библиография, без картинок) получает картинку
    со стр. 10 того же документа (delta=2)."""
    фрагменты = [
        {
            "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
            "page": 12, "images": [], "text": "References",
        },
    ]

    индекс = {
        ("h1", 10): [{"path": "extracted_images/h1/p10_a.png", "page": 10}],
    }
    monkeypatch.setattr(
        app_module.notebooks, "собрать_картинки_по_страницам",
        lambda *a, **kw: индекс,
    )
    monkeypatch.setattr(
        app_module.notebooks, "load_store",
        lambda uid: {"users": {uid: {"notebooks": [
            {"id": "nb1", "title": "T", "collection": "c1"}
        ]}}},
    )
    monkeypatch.setattr(app_module, "загрузить_qdrant", lambda: MagicMock())

    app_module.обогатить_картинками_соседних_страниц(фрагменты, окно=2)

    assert "images_neighbors" in фрагменты[0]
    пути = [img["path"] for img in фрагменты[0]["images_neighbors"]]
    assert "extracted_images/h1/p10_a.png" in пути


def test_не_подставляет_если_у_страницы_уже_есть_свои_картинки(app_module, monkeypatch):
    фрагменты = [
        {
            "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
            "page": 8, "images": [{"path": "extracted_images/h1/p8.png"}],
        },
    ]
    monkeypatch.setattr(
        app_module.notebooks, "load_store",
        lambda uid: {"users": {uid: {"notebooks": [
            {"id": "nb1", "title": "T", "collection": "c1"}
        ]}}},
    )
    клиент = MagicMock()
    monkeypatch.setattr(app_module, "загрузить_qdrant", lambda: клиент)

    индекс_должен_быть_не_вызван = MagicMock()
    monkeypatch.setattr(
        app_module.notebooks, "собрать_картинки_по_страницам",
        индекс_должен_быть_не_вызван,
    )

    app_module.обогатить_картинками_соседних_страниц(фрагменты)

    assert "images_neighbors" not in фрагменты[0]


def test_фрагменты_корпуса_без_notebook_id_пропускаются(app_module, monkeypatch):
    """Корпусные фрагменты не имеют notebook_id — их трогать нельзя."""
    фрагменты = [
        {"document": "harvested.pdf", "page": 5, "images": []},
    ]
    клиент = MagicMock()
    monkeypatch.setattr(app_module, "загрузить_qdrant", lambda: клиент)

    app_module.обогатить_картинками_соседних_страниц(фрагменты)

    assert "images_neighbors" not in фрагменты[0]
    клиент.scroll.assert_not_called()


def test_окно_ограничивает_расстояние_до_соседей(app_module, monkeypatch):
    """С окном=1 нельзя подтянуть картинку со стр. 5, если фрагмент на стр. 12."""
    фрагменты = [
        {
            "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
            "page": 12, "images": [], "text": "References",
        },
    ]
    индекс = {
        ("h1", 5): [{"path": "extracted_images/h1/p5.png", "page": 5}],
    }
    monkeypatch.setattr(
        app_module.notebooks, "собрать_картинки_по_страницам",
        lambda *a, **kw: индекс,
    )
    monkeypatch.setattr(
        app_module.notebooks, "load_store",
        lambda uid: {"users": {uid: {"notebooks": [
            {"id": "nb1", "title": "T", "collection": "c1"}
        ]}}},
    )
    monkeypatch.setattr(app_module, "загрузить_qdrant", lambda: MagicMock())

    app_module.обогатить_картинками_соседних_страниц(фрагменты, окно=1)

    assert фрагменты[0].get("images_neighbors") is None or фрагменты[0]["images_neighbors"] == []


def test_остановка_на_первом_расстоянии_с_попаданием(app_module, monkeypatch):
    """С окном=2 если есть на ±1 — не идём на ±2. Это уменьшает шум."""
    фрагменты = [
        {
            "user_id": "u1", "notebook_id": "nb1", "file_hash": "h1",
            "page": 12, "images": [], "text": "References",
        },
    ]
    индекс = {
        ("h1", 11): [{"path": "p11.png", "page": 11}],
        ("h1", 13): [{"path": "p13.png", "page": 13}],
        ("h1", 10): [{"path": "p10.png", "page": 10}],
        ("h1", 14): [{"path": "p14.png", "page": 14}],
    }
    monkeypatch.setattr(
        app_module.notebooks, "собрать_картинки_по_страницам",
        lambda *a, **kw: индекс,
    )
    monkeypatch.setattr(
        app_module.notebooks, "load_store",
        lambda uid: {"users": {uid: {"notebooks": [
            {"id": "nb1", "title": "T", "collection": "c1"}
        ]}}},
    )
    monkeypatch.setattr(app_module, "загрузить_qdrant", lambda: MagicMock())

    app_module.обогатить_картинками_соседних_страниц(фрагменты, окно=2)

    пути = sorted(img["path"] for img in фрагменты[0]["images_neighbors"])
    assert пути == ["p11.png", "p13.png"]
