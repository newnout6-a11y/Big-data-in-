"""Гибридный поиск: dense (e5) + sparse (BM25) с RRF-фьюжеом.

Без новых нейросетей — sparse-векторы это просто BM25 (TF + статический IDF на
стороне Qdrant). FastEmbed используется только для токенизации/лемматизации.
"""
from __future__ import annotations

import threading


_замок_bm25 = threading.Lock()
_кэш_bm25 = {}


def получить_bm25():
    """Ленивая загрузка модели BM25 (~25 КБ — это не нейросеть, просто словарь)."""
    if "model" in _кэш_bm25:
        return _кэш_bm25["model"]
    with _замок_bm25:
        if "model" in _кэш_bm25:
            return _кэш_bm25["model"]
        from fastembed import SparseTextEmbedding
        _кэш_bm25["model"] = SparseTextEmbedding(model_name="Qdrant/bm25")
        return _кэш_bm25["model"]


def построить_sparse_батч(тексты):
    """Возвращает список (indices, values) для каждого текста."""
    модель = получить_bm25()
    результат = []
    for э in модель.embed(list(тексты)):
        результат.append((э.indices.tolist(), э.values.tolist()))
    return результат


def построить_sparse_один(текст):
    """Один текст → (indices, values)."""
    return построить_sparse_батч([текст])[0]


def rrf_fuse(списки_id, k=60):
    """Reciprocal Rank Fusion. На вход — несколько ранжированных списков id,
    возвращает единый список id, отсортированный по сумме 1/(k+rank)."""
    очки = {}
    for список in списки_id:
        for ранг, ид in enumerate(список):
            очки[ид] = очки.get(ид, 0.0) + 1.0 / (k + ранг + 1)
    return sorted(очки.keys(), key=lambda x: -очки[x])
