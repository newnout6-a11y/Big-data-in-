"""Тесты гибридного поиска и реранкера (без сети, без БД)."""
from __future__ import annotations

import pytest

from hybrid_search import rrf_fuse


def test_rrf_сливает_общие_id():
    """ID появившийся в обоих списках получает выше скор, чем уникальный."""
    dense = ["a", "b", "c", "d", "e"]
    sparse = ["c", "b", "x", "y", "z"]
    итог = rrf_fuse([dense, sparse])
    # 'b' и 'c' видели оба, должны быть в начале
    assert итог.index("b") < итог.index("a")
    assert итог.index("c") < итог.index("d")


def test_rrf_порядок_внутри_общих():
    """При одинаковом наборе общих, более высокий ранг в одном списке выигрывает."""
    итог = rrf_fuse([["a", "b"], ["a", "b"]])
    assert итог == ["a", "b"]


def test_rrf_пустые_списки():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_rrf_один_список():
    итог = rrf_fuse([["a", "b", "c"]])
    assert итог == ["a", "b", "c"]


def test_bm25_векторы_отличаются_по_содержимому():
    """Sparse-вектор должен меняться при разных текстах. Это smoke-тест,
    что FastEmbed BM25 действительно работает."""
    pytest.importorskip("fastembed")
    from hybrid_search import построить_sparse_батч
    тексты = [
        "machine learning for chemistry",
        "история древнего рима",
    ]
    результат = построить_sparse_батч(тексты)
    assert len(результат) == 2
    idx_1, val_1 = результат[0]
    idx_2, val_2 = результат[1]
    # Хоть какие-то токены должны быть, и для разных текстов наборы индексов разные
    assert len(idx_1) > 0 and len(idx_2) > 0
    assert set(idx_1) != set(idx_2)
    # Все веса положительные
    assert all(v > 0 for v in val_1)
    assert all(v > 0 for v in val_2)
