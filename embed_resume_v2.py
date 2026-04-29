"""Инкрементальная векторизация чанков из chunks_v2.jsonl в Qdrant.

Создаёт коллекцию `knowledge` (новая схема). Старая `химия` не трогается.
Если коллекции нет — создаёт. Если есть — догружает остаток.
Также создаёт payload-индексы для быстрых фильтров.
"""
from __future__ import annotations

import json
import os
import sys

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer


_БАЗА = os.path.dirname(os.path.abspath(__file__))
ФАЙЛ_ЧАНКОВ = os.path.join(_БАЗА, "chunks_v2.jsonl")
ПАПКА_БД = os.path.join(_БАЗА, "qdrant_db")
КОЛЛЕКЦИЯ = "knowledge"
РАЗМЕР_БАТЧА = 64
РАЗМЕР_ВЕКТОРА = 768

ПОЛЯ_ИНДЕКСОВ = [
    ("domain", PayloadSchemaType.KEYWORD),
    ("subdomain", PayloadSchemaType.KEYWORD),
    ("source", PayloadSchemaType.KEYWORD),
    ("language", PayloadSchemaType.KEYWORD),
    ("doc_id", PayloadSchemaType.KEYWORD),
    ("year", PayloadSchemaType.INTEGER),
    ("text_hash", PayloadSchemaType.KEYWORD),
]


def подключиться():
    """Подключается к Qdrant. Если есть QDRANT_URL/QDRANT_API_KEY — на сервер,
    иначе локально в qdrant_db/. Это позволяет запускать на GitHub Actions
    с пушем в Qdrant Cloud, и локально для разработки.
    """
    url = os.getenv("QDRANT_URL", "").strip()
    if url:
        клиент = QdrantClient(
            url=url,
            api_key=os.getenv("QDRANT_API_KEY") or None,
            prefer_grpc=False,
            timeout=120,
        )
        print(f"Qdrant: удалённый сервер {url}")
    else:
        клиент = QdrantClient(path=ПАПКА_БД)
        print(f"Qdrant: локальный {ПАПКА_БД}")
    коллекции = {к.name for к in клиент.get_collections().collections}
    if КОЛЛЕКЦИЯ not in коллекции:
        клиент.create_collection(
            collection_name=КОЛЛЕКЦИЯ,
            vectors_config=VectorParams(size=РАЗМЕР_ВЕКТОРА, distance=Distance.COSINE),
        )
        print(f"Создана коллекция {КОЛЛЕКЦИЯ}")
    for поле, тип in ПОЛЯ_ИНДЕКСОВ:
        try:
            клиент.create_payload_index(КОЛЛЕКЦИЯ, поле, тип)
        except Exception:
            pass  # уже существует
    return клиент


def main():
    if not os.path.exists(ФАЙЛ_ЧАНКОВ):
        print(f"Нет файла {ФАЙЛ_ЧАНКОВ}. Сначала запусти python ingest_v2.py")
        return 1

    клиент = подключиться()
    в_базе = клиент.count(КОЛЛЕКЦИЯ, exact=True).count
    print(f"В коллекции {КОЛЛЕКЦИЯ}: {в_базе} точек")

    все_чанки = []
    with open(ФАЙЛ_ЧАНКОВ, "r", encoding="utf-8") as f:
        for строка in f:
            строка = строка.strip()
            if строка:
                все_чанки.append(json.loads(строка))
    print(f"Всего чанков в файле: {len(все_чанки)}")

    осталось = все_чанки[в_базе:]
    print(f"Осталось загрузить: {len(осталось)}")
    if not осталось:
        return 0

    модель = SentenceTransformer("intfloat/multilingual-e5-base")
    print("Модель загружена")

    текущий = в_базе
    for старт in range(0, len(осталось), РАЗМЕР_БАТЧА):
        батч = осталось[старт:старт + РАЗМЕР_БАТЧА]
        тексты = ["passage: " + ч["text"] for ч in батч]
        векторы = модель.encode(тексты, show_progress_bar=False, normalize_embeddings=True)

        точки = []
        for i, чанк in enumerate(батч):
            payload = {ключ: значение for ключ, значение in чанк.items() if ключ != "text" or True}
            точки.append(PointStruct(
                id=текущий,
                vector=векторы[i].tolist(),
                payload=payload,
            ))
            текущий += 1

        клиент.upsert(collection_name=КОЛЛЕКЦИЯ, points=точки)

        if (старт // РАЗМЕР_БАТЧА + 1) % 10 == 0 or старт + РАЗМЕР_БАТЧА >= len(осталось):
            готово = в_базе + min(старт + РАЗМЕР_БАТЧА, len(осталось))
            print(f"  Загружено: {готово}/{len(все_чанки)}")

    финал = клиент.count(КОЛЛЕКЦИЯ, exact=True).count
    print(f"\nГотово. В коллекции {КОЛЛЕКЦИЯ}: {финал} точек")
    return 0


if __name__ == "__main__":
    sys.exit(main())
