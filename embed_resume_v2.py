"""Инкрементальная векторизация чанков из chunks_v2.jsonl в Qdrant.

Создаёт коллекцию `knowledge_hybrid` с named-vectors:
  - dense  — multilingual-e5-base, 768d, cosine
  - sparse — BM25 с серверным IDF (через FastEmbed Qdrant/bm25)

Старые коллекции (`химия`, `knowledge`) не трогаются — приложение умеет
работать как с гибридной, так и с устаревшими.

Идемпотентность: ID точек в Qdrant вычисляется как UUIDv5 от text_hash.
Это даёт два преимущества:
  1. Перезапуск после частичной записи не дублирует данные и не ломает
     уже загруженные точки (повторный upsert = no-op).
  2. Если chunks_v2.jsonl перегенерировали (например, --full), порядок
     не важен — каждый чанк всегда попадает на свой стабильный ID.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    BinaryQuantization,
    BinaryQuantizationConfig,
    Distance,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from hybrid_search import построить_sparse_батч


_БАЗА = os.path.dirname(os.path.abspath(__file__))
ФАЙЛ_ЧАНКОВ = os.path.join(_БАЗА, "chunks_v2.jsonl")
ПАПКА_БД = os.path.join(_БАЗА, "qdrant_db")
КОЛЛЕКЦИЯ = "knowledge_hybrid"
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
    """Удалённый Qdrant если задан QDRANT_URL, иначе локальный qdrant_db/."""
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
        # Dense vectors лежат на диске, в RAM держим только бинарные кодировки
        # (32× меньше). На Qdrant Cloud Free (1 GB RAM) это даёт запас на ~3-5M
        # точек вместо ~1M без квантования. Recall теряет 2-5%, но reranker
        # сверху восстанавливает качество практически до оригинала.
        клиент.create_collection(
            collection_name=КОЛЛЕКЦИЯ,
            vectors_config={
                "dense": VectorParams(
                    size=РАЗМЕР_ВЕКТОРА,
                    distance=Distance.COSINE,
                    on_disk=True,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                    modifier=Modifier.IDF,
                ),
            },
            quantization_config=BinaryQuantization(
                binary=BinaryQuantizationConfig(always_ram=True),
            ),
        )
        print(f"Создана гибридная коллекция {КОЛЛЕКЦИЯ} (binary quantization)")
    for поле, тип in ПОЛЯ_ИНДЕКСОВ:
        try:
            клиент.create_payload_index(КОЛЛЕКЦИЯ, поле, тип)
        except Exception:
            pass  # уже существует
    return клиент


def _id_для_чанка(чанк: dict) -> str:
    """Стабильный UUIDv5 от text_hash. Один и тот же текст всегда даёт один id."""
    text_hash = чанк.get("text_hash") or ""
    if not text_hash:
        # На всякий случай — fallback на хэш самого текста, чтобы не падать.
        # ingest_v2 всегда выставляет text_hash, поэтому в норме сюда не зайдём.
        import hashlib
        text_hash = hashlib.sha1(
            (чанк.get("text") or "").encode("utf-8", errors="ignore")
        ).hexdigest()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text_hash))


def _существующие_text_hashes(клиент: QdrantClient, коллекция: str) -> set[str]:
    """Сканирует коллекцию и возвращает множество text_hash уже загруженных точек."""
    результат: set[str] = set()
    offset = None
    while True:
        батч, offset = клиент.scroll(
            collection_name=коллекция,
            limit=512,
            offset=offset,
            with_payload=["text_hash"],
            with_vectors=False,
        )
        for точка in батч:
            text_hash = (точка.payload or {}).get("text_hash")
            if text_hash:
                результат.add(text_hash)
        if offset is None:
            break
    return результат


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

    # Идемпотентность: дедуп по text_hash, а не по позиции в файле. Если хоть
    # один upsert упал ранее — повторный запуск догрузит ровно то, чего нет в
    # коллекции, не дублируя и не перезатирая полезные точки.
    existing = _существующие_text_hashes(клиент, КОЛЛЕКЦИЯ) if в_базе else set()
    if existing:
        print(f"Уже в коллекции (по text_hash): {len(existing)}")
    осталось = [ч for ч in все_чанки if ч.get("text_hash") not in existing]
    print(f"Осталось загрузить: {len(осталось)}")
    if not осталось:
        return 0

    модель = SentenceTransformer("intfloat/multilingual-e5-base")
    print("Модель dense загружена")

    загружено = 0
    for старт in range(0, len(осталось), РАЗМЕР_БАТЧА):
        батч = осталось[старт:старт + РАЗМЕР_БАТЧА]
        тексты = [ч["text"] for ч in батч]
        векторы = модель.encode(
            ["passage: " + т for т in тексты],
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        sparse_пары = построить_sparse_батч(тексты)

        точки = []
        for i, чанк in enumerate(батч):
            idx, val = sparse_пары[i]
            точки.append(PointStruct(
                id=_id_для_чанка(чанк),
                vector={
                    "dense": векторы[i].tolist(),
                    "sparse": SparseVector(indices=idx, values=val),
                },
                payload=чанк,
            ))

        клиент.upsert(collection_name=КОЛЛЕКЦИЯ, points=точки)
        загружено += len(батч)

        if (старт // РАЗМЕР_БАТЧА + 1) % 10 == 0 or старт + РАЗМЕР_БАТЧА >= len(осталось):
            print(f"  Загружено: {загружено}/{len(осталось)}")

    финал = клиент.count(КОЛЛЕКЦИЯ, exact=True).count
    print(f"\nГотово. В коллекции {КОЛЛЕКЦИЯ}: {финал} точек")
    return 0


if __name__ == "__main__":
    sys.exit(main())
