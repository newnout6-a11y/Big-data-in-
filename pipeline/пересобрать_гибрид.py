"""Миграция коллекции `knowledge` → `knowledge_hybrid` с named-vectors.

В новой схеме у точки два вектора: `dense` (e5, 768d, cosine) и `sparse`
(BM25 с серверным IDF). Dense копируется как есть из существующей коллекции
(не пере-эмбеддим), sparse считается локально из текста чанка.

Использование:
    python пересобрать_гибрид.py             # создаёт knowledge_hybrid
    python пересобрать_гибрид.py --resume    # докинуть отсутствующие
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Bootstrap: для прямого запуска `python pipeline/пересобрать_гибрид.py`.
_РЕПО = Path(__file__).resolve().parent.parent
for _подпапка in ("", "core"):
    _путь = str(_РЕПО / _подпапка) if _подпапка else str(_РЕПО)
    if _путь not in sys.path:
        sys.path.insert(0, _путь)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from hybrid_search import построить_sparse_батч


# Скрипт лежит в pipeline/, qdrant_db/ — в корне репо.
_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКА_БД = os.path.join(_БАЗА, "qdrant_db")
ИСХОДНАЯ = "knowledge"
ЦЕЛЕВАЯ = "knowledge_hybrid"
БАТЧ = 256

ПОЛЯ_ИНДЕКСОВ = [
    ("domain", PayloadSchemaType.KEYWORD),
    ("subdomain", PayloadSchemaType.KEYWORD),
    ("source", PayloadSchemaType.KEYWORD),
    ("language", PayloadSchemaType.KEYWORD),
    ("doc_id", PayloadSchemaType.KEYWORD),
    ("year", PayloadSchemaType.INTEGER),
    ("text_hash", PayloadSchemaType.KEYWORD),
]


def _подключиться():
    url = os.getenv("QDRANT_URL", "").strip()
    if url:
        return QdrantClient(
            url=url,
            api_key=os.getenv("QDRANT_API_KEY") or None,
            timeout=120,
        )
    return QdrantClient(path=ПАПКА_БД)


def _создать_целевую(клиент, размер_dense):
    коллекции = {к.name for к in клиент.get_collections().collections}
    if ЦЕЛЕВАЯ in коллекции:
        print(f"Коллекция {ЦЕЛЕВАЯ} уже существует.")
        return
    клиент.create_collection(
        collection_name=ЦЕЛЕВАЯ,
        vectors_config={
            "dense": VectorParams(size=размер_dense, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False),
                modifier=Modifier.IDF,
            ),
        },
    )
    for поле, тип in ПОЛЯ_ИНДЕКСОВ:
        try:
            клиент.create_payload_index(ЦЕЛЕВАЯ, поле, тип)
        except Exception:
            pass
    print(f"Создана коллекция {ЦЕЛЕВАЯ}")


def _получить_размер_dense(клиент):
    инфо = клиент.get_collection(ИСХОДНАЯ)
    конфиг = инфо.config.params.vectors
    if hasattr(конфиг, "size"):
        return конфиг.size
    if isinstance(конфиг, dict):
        return list(конфиг.values())[0].size
    return 768


def main(argv=None):
    парсер = argparse.ArgumentParser()
    парсер.add_argument("--resume", action="store_true", help="Не пересоздавать, докинуть остаток")
    args = парсер.parse_args(argv)

    клиент = _подключиться()
    коллекции = {к.name for к in клиент.get_collections().collections}
    if ИСХОДНАЯ not in коллекции:
        print(f"Нет исходной коллекции {ИСХОДНАЯ}. Сначала ingest_v2.py + embed_resume_v2.py")
        return 1

    размер_dense = _получить_размер_dense(клиент)
    _создать_целевую(клиент, размер_dense)

    исходный_count = клиент.count(ИСХОДНАЯ, exact=True).count
    целевой_count = клиент.count(ЦЕЛЕВАЯ, exact=True).count
    print(f"{ИСХОДНАЯ}: {исходный_count} точек, {ЦЕЛЕВАЯ}: {целевой_count} точек")

    if args.resume and целевой_count >= исходный_count:
        print("Уже всё перенесено.")
        return 0
    if не_resume_overwrite := (not args.resume and целевой_count > 0):
        print("Целевая коллекция уже непустая. Используй --resume или удали её вручную.")
        return 1
    _ = не_resume_overwrite

    обработано = 0
    смещение = None
    while True:
        точки, смещение = клиент.scroll(
            collection_name=ИСХОДНАЯ,
            offset=смещение,
            limit=БАТЧ,
            with_payload=True,
            with_vectors=True,
        )
        if not точки:
            break

        # Пропускаем уже перенесённые id
        существующие = set()
        if args.resume:
            ids = [p.id for p in точки]
            try:
                найденные = клиент.retrieve(
                    collection_name=ЦЕЛЕВАЯ,
                    ids=ids,
                    with_vectors=False,
                    with_payload=False,
                )
                существующие = {p.id for p in найденные}
            except Exception:
                существующие = set()

        новые = [p for p in точки if p.id not in существующие]
        if новые:
            тексты = [(p.payload or {}).get("text", "") for p in новые]
            sparse_пары = построить_sparse_батч(тексты)

            новые_точки = []
            for точка, (idx, val) in zip(новые, sparse_пары):
                dense = точка.vector
                if isinstance(dense, dict):
                    dense = dense.get("dense") or list(dense.values())[0]
                новые_точки.append(PointStruct(
                    id=точка.id,
                    vector={
                        "dense": dense,
                        "sparse": SparseVector(indices=idx, values=val),
                    },
                    payload=точка.payload,
                ))

            клиент.upsert(collection_name=ЦЕЛЕВАЯ, points=новые_точки)
            обработано += len(новые_точки)
            print(f"  перенесено {обработано}/{исходный_count}")

        if смещение is None:
            break

    финал = клиент.count(ЦЕЛЕВАЯ, exact=True).count
    print(f"\nГотово. {ЦЕЛЕВАЯ}: {финал} точек")
    return 0


if __name__ == "__main__":
    sys.exit(main())
