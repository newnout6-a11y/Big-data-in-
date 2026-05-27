"""Импорт knowledge_hybrid_export.jsonl в локальный qdrant_db/.

Принимает на вход JSONL, который сделал scripts/download_snapshot.py --mode jsonl,
и заливает все точки в локальную коллекцию `knowledge_hybrid` (named-vectors:
dense+sparse). Векторы НЕ пересчитывает — берёт готовые из JSONL.

Идемпотентность: повторный запуск пропускает уже загруженные точки (по id).

Использование:
    python scripts/import_snapshot.py
    python scripts/import_snapshot.py --input knowledge_hybrid_export.jsonl
    python scripts/import_snapshot.py --recreate    # удалить локальную и залить заново
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

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


_БАЗА = Path(__file__).resolve().parent.parent
ФАЙЛ_ВХОДНОЙ = _БАЗА / "knowledge_hybrid_export.jsonl"
ПАПКА_БД = _БАЗА / "qdrant_db"
КОЛЛЕКЦИЯ = "knowledge_hybrid"
БАТЧ = 256
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


def _создать_или_получить(клиент: QdrantClient, recreate: bool) -> None:
    коллекции = {к.name for к in клиент.get_collections().collections}
    если_есть = КОЛЛЕКЦИЯ in коллекции
    if recreate and если_есть:
        print(f"Удаляю существующую {КОЛЛЕКЦИЯ}...")
        клиент.delete_collection(КОЛЛЕКЦИЯ)
        если_есть = False
    if not если_есть:
        # Dense-векторы и sparse-индекс на диске, binary quantization в RAM —
        # экономит ~30x RAM vs. полные float32. Recall теряет 2-5%, но reranker
        # восстанавливает качество.
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
                    index=SparseIndexParams(on_disk=True),
                    modifier=Modifier.IDF,
                ),
            },
            quantization_config=BinaryQuantization(
                binary=BinaryQuantizationConfig(always_ram=True),
            ),
        )
        print(f"Создана {КОЛЛЕКЦИЯ} (dense+sparse, on_disk + binary quantization)")
    for поле, тип in ПОЛЯ_ИНДЕКСОВ:
        try:
            клиент.create_payload_index(КОЛЛЕКЦИЯ, поле, тип)
        except Exception:
            pass  # уже существует


def _существующие_id(клиент: QdrantClient) -> set[str]:
    """Сканирует коллекцию и возвращает множество id уже загруженных точек."""
    результат: set[str] = set()
    offset = None
    while True:
        батч, offset = клиент.scroll(
            collection_name=КОЛЛЕКЦИЯ,
            limit=2048,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for точка in батч:
            результат.add(str(точка.id))
        if offset is None:
            break
    return результат


def _точка_из_строки(строка: str) -> PointStruct | None:
    obj = json.loads(строка)
    vec = obj.get("vector") or {}
    if not isinstance(vec, dict):
        # На всякий случай — старый scroll без named vectors отдавал бы list
        # (тогда коллекция dense-only, эта ветка не наш кейс — пропускаем).
        return None
    dense = vec.get("dense")
    sparse = vec.get("sparse") or {}
    if not dense or not sparse.get("indices"):
        return None
    return PointStruct(
        id=obj["id"],
        vector={
            "dense": list(dense),
            "sparse": SparseVector(
                indices=list(sparse["indices"]),
                values=list(sparse["values"]),
            ),
        },
        payload=obj.get("payload") or {},
    )


def main(argv: list[str] | None = None) -> int:
    парсер = argparse.ArgumentParser(description=__doc__)
    парсер.add_argument("--input", default=str(ФАЙЛ_ВХОДНОЙ),
                        help="Путь к JSONL (по умолчанию knowledge_hybrid_export.jsonl)")
    парсер.add_argument("--recreate", action="store_true",
                        help="Удалить локальную коллекцию и залить заново")
    парсер.add_argument("--batch", type=int, default=БАТЧ,
                        help=f"Размер батча upsert (default {БАТЧ})")
    парсер.add_argument("--limit", type=int, default=0,
                        help="Максимум точек для загрузки (0 = все)")
    args = парсер.parse_args(argv)

    путь_jsonl = Path(args.input)
    if not путь_jsonl.exists():
        print(f"Нет файла {путь_jsonl}. Сначала запусти scripts/download_snapshot.py --mode jsonl",
              file=sys.stderr)
        return 1

    # Считаем количество строк (для прогресса).
    print(f"Считаю строки в {путь_jsonl}...", flush=True)
    с_размер = путь_jsonl.stat().st_size
    с_строк = 0
    with путь_jsonl.open("rb") as f:
        for _ in f:
            с_строк += 1
    print(f"Точек в файле: {с_строк} (размер: {с_размер / 1e9:.2f} GB)")

    клиент = QdrantClient(path=str(ПАПКА_БД))
    print(f"Локальная база: {ПАПКА_БД}")

    _создать_или_получить(клиент, args.recreate)

    в_базе = клиент.count(КОЛЛЕКЦИЯ, exact=True).count
    print(f"В коллекции {КОЛЛЕКЦИЯ} уже: {в_базе} точек")

    уже_есть = _существующие_id(клиент) if в_базе else set()
    if уже_есть:
        print(f"Пропущу уже загруженные: {len(уже_есть)}")

    батч_точек: list[PointStruct] = []
    загружено = 0
    пропущено = 0
    битых = 0
    старт = time.time()

    def _flush():
        nonlocal батч_точек, загружено
        if not батч_точек:
            return
        клиент.upsert(collection_name=КОЛЛЕКЦИЯ, points=батч_точек)
        загружено += len(батч_точек)
        батч_точек = []

    with путь_jsonl.open("r", encoding="utf-8") as f:
        for i, строка in enumerate(f, 1):
            строка = строка.strip()
            if not строка:
                continue
            try:
                точка = _точка_из_строки(строка)
            except Exception as e:
                битых += 1
                if битых <= 5:
                    print(f"  битая строка {i}: {e}")
                continue
            if точка is None:
                битых += 1
                continue
            if str(точка.id) in уже_есть:
                пропущено += 1
                continue
            батч_точек.append(точка)
            if len(батч_точек) >= args.batch:
                _flush()
                if загружено and загружено % (args.batch * 10) == 0:
                    скорость = загружено / max(time.time() - старт, 1)
                    осталось = с_строк - i
                    eta = осталось / max(скорость, 1)
                    print(f"  Загружено: {загружено}/{с_строк - len(уже_есть)} "
                          f"({скорость:.0f} pt/s, ETA {eta / 60:.1f} мин",
                          flush=True)
            if args.limit and загружено >= args.limit:
                print(f"Достигнут лимит {args.limit}, останавливаюсь.")
                break
    _flush()

    финал = клиент.count(КОЛЛЕКЦИЯ, exact=True).count
    print(f"\nГотово за {(time.time() - старт) / 60:.1f} мин.")
    print(f"  Загружено новых: {загружено}")
    print(f"  Пропущено (уже было): {пропущено}")
    print(f"  Битых строк: {битых}")
    print(f"  В коллекции {КОЛЛЕКЦИЯ}: {финал} точек")
    return 0


if __name__ == "__main__":
    sys.exit(main())
