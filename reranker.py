"""Cross-encoder reranker для финальной сортировки top-K.

Один раз скачивается ~600 МБ модель `BAAI/bge-reranker-v2-m3`, дальше работает
локально на CPU. Прогон 30 пар (вопрос, чанк) занимает ~0.5 сек.
"""
from __future__ import annotations

import os
import threading


_замок = threading.Lock()
_кэш = {}

MODEL_NAME = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")


def получить():
    if "m" in _кэш:
        return _кэш["m"]
    with _замок:
        if "m" in _кэш:
            return _кэш["m"]
        from sentence_transformers import CrossEncoder
        _кэш["m"] = CrossEncoder(MODEL_NAME, max_length=512)
        return _кэш["m"]


def переранжировать(вопрос, документы, top_k=None):
    """documents — list[str]. Возвращает список (индекс_в_исходном, скор)
    отсортированный по убыванию релевантности. top_k — обрезание сверху."""
    if not документы:
        return []
    модель = получить()
    пары = [(вопрос, д) for д in документы]
    скоры = модель.predict(пары, show_progress_bar=False)
    индексы = sorted(range(len(документы)), key=lambda i: -float(скоры[i]))
    if top_k is not None:
        индексы = индексы[:top_k]
    return [(i, float(скоры[i])) for i in индексы]
