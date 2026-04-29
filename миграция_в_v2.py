"""Миграция существующей коллекции `химия` (46k точек) в новую `knowledge`.

НЕ переэмбеддит — копирует векторы как есть, обогащает payload новыми полями
(domain, subdomain, language, text_hash, embed_model). Старая коллекция `химия`
остаётся нетронутой.

Авторазметка domain/subdomain делается через классификатор.py на тексте чанка.

Использование:
    python миграция_в_v2.py
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)


_БАЗА = os.path.dirname(os.path.abspath(__file__))
ПАПКА_БД = os.path.join(_БАЗА, "qdrant_db")
СТАРАЯ_КОЛЛЕКЦИЯ = "химия"
НОВАЯ_КОЛЛЕКЦИЯ = "knowledge"
РАЗМЕР_БАТЧА = 256
EMBED_MODEL_TAG = "e5-base-v1"

ПОЛЯ_ИНДЕКСОВ = [
    ("domain", PayloadSchemaType.KEYWORD),
    ("subdomain", PayloadSchemaType.KEYWORD),
    ("source", PayloadSchemaType.KEYWORD),
    ("language", PayloadSchemaType.KEYWORD),
    ("doc_id", PayloadSchemaType.KEYWORD),
    ("year", PayloadSchemaType.INTEGER),
    ("text_hash", PayloadSchemaType.KEYWORD),
]


def main():
    клиент = QdrantClient(path=ПАПКА_БД)
    коллекции = {к.name for к in клиент.get_collections().collections}
    if СТАРАЯ_КОЛЛЕКЦИЯ not in коллекции:
        print(f"Не найдена коллекция {СТАРАЯ_КОЛЛЕКЦИЯ}. Нечего мигрировать.")
        return 1

    инфо = клиент.get_collection(СТАРАЯ_КОЛЛЕКЦИЯ)
    конфиг_векторов = инфо.config.params.vectors
    if hasattr(конфиг_векторов, "size"):
        размер = конфиг_векторов.size
    else:
        размер = list(конфиг_векторов.values())[0].size

    if НОВАЯ_КОЛЛЕКЦИЯ not in коллекции:
        клиент.create_collection(
            НОВАЯ_КОЛЛЕКЦИЯ,
            vectors_config=VectorParams(size=размер, distance=Distance.COSINE),
        )
    for поле, тип in ПОЛЯ_ИНДЕКСОВ:
        try:
            клиент.create_payload_index(НОВАЯ_КОЛЛЕКЦИЯ, поле, тип)
        except Exception:
            pass

    всего_старых = клиент.count(СТАРАЯ_КОЛЛЕКЦИЯ, exact=True).count
    в_новой = клиент.count(НОВАЯ_КОЛЛЕКЦИЯ, exact=True).count
    print(f"В старой ({СТАРАЯ_КОЛЛЕКЦИЯ}): {всего_старых}, в новой ({НОВАЯ_КОЛЛЕКЦИЯ}): {в_новой}")

    if в_новой >= всего_старых:
        print("Уже мигрировано.")
        return 0

    print("Загружаю модель и прототипы для авторазметки…")
    from sentence_transformers import SentenceTransformer

    from классификатор import (
        детерминировать_язык,
        классифицировать_батч,
        подготовить_прототипы,
    )

    модель = SentenceTransformer("intfloat/multilingual-e5-base")
    метки, прототипы, _ = подготовить_прототипы(модель)

    дата_сегодня = datetime.utcnow().strftime("%Y-%m-%d")
    смещение = в_новой
    скроллер = None
    обработано = 0

    while True:
        точки, скроллер = клиент.scroll(
            СТАРАЯ_КОЛЛЕКЦИЯ,
            limit=РАЗМЕР_БАТЧА,
            offset=скроллер,
            with_payload=True,
            with_vectors=True,
        )
        if not точки:
            break

        тексты = [p.payload.get("text", "") for p in точки]
        авторазметка = классифицировать_батч(тексты, модель, метки, прототипы)

        новые_точки = []
        for p, (домен, суб, скор) in zip(точки, авторазметка):
            текст = p.payload.get("text", "")
            новый_payload = {
                **p.payload,
                "doc_id": p.payload.get("doc_id") or f"local:{p.payload.get('document', '')}",
                "source": p.payload.get("source", "local"),
                "domain": домен,
                "subdomain": суб,
                "topic_score": round(скор, 3),
                "language": детерминировать_язык(текст),
                "embed_model": EMBED_MODEL_TAG,
                "text_hash": hashlib.sha1(текст.encode("utf-8")).hexdigest(),
                "ingested_at": p.payload.get("ingested_at", дата_сегодня),
            }
            вектор = p.vector
            if isinstance(вектор, dict):
                # named vectors
                вектор = list(вектор.values())[0]
            новые_точки.append(PointStruct(
                id=смещение,
                vector=вектор,
                payload=новый_payload,
            ))
            смещение += 1

        клиент.upsert(НОВАЯ_КОЛЛЕКЦИЯ, points=новые_точки)
        обработано += len(новые_точки)
        print(f"  Перенесено: {обработано}/{всего_старых - в_новой}")

        if скроллер is None:
            break

    финал = клиент.count(НОВАЯ_КОЛЛЕКЦИЯ, exact=True).count
    print(f"\nГотово. В коллекции {НОВАЯ_КОЛЛЕКЦИЯ}: {финал} точек")
    return 0


if __name__ == "__main__":
    sys.exit(main())
