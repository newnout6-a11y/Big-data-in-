"""Выкачивает snapshot коллекции из Qdrant Cloud себе на ПК.

Использование:

    # 1. Положить в .env:
    #    QDRANT_URL=https://...
    #    QDRANT_API_KEY=...

    python download_snapshot.py

После запуска получишь два файла:
  knowledge_hybrid.snapshot — бинарный дамп всей коллекции (вектора + payload)
  vectors_export.jsonl       — экспорт всех точек как JSONL (опционально, через --export-jsonl)

Восстановление снапшота локально (если хочешь поднять Qdrant у себя на ПК):

    from qdrant_client import QdrantClient
    c = QdrantClient(path="./qdrant_db")
    c.recover_snapshot("knowledge_hybrid", "./knowledge_hybrid.snapshot")
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx
from qdrant_client import QdrantClient


КОЛЛЕКЦИЯ = "knowledge_hybrid"


def _загрузить_env() -> None:
    """Подтягивает переменные из .env, если он есть."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _конфиг() -> tuple[str, str | None]:
    url = os.getenv("QDRANT_URL", "").strip()
    key = os.getenv("QDRANT_API_KEY", "").strip() or None
    if not url:
        print("Ошибка: не задан QDRANT_URL (.env или переменная окружения).",
              file=sys.stderr)
        sys.exit(2)
    return url, key


def сделать_снапшот(args: argparse.Namespace) -> int:
    """Создаёт snapshot на сервере и качает его HTTP'ом в локальный файл."""
    url, key = _конфиг()
    клиент = QdrantClient(url=url, api_key=key, prefer_grpc=False, timeout=600)

    print(f"Создаю snapshot коллекции {args.collection}...")
    snap = клиент.create_snapshot(collection_name=args.collection)
    if snap is None:
        print("Snapshot не создан (вернулся None).", file=sys.stderr)
        return 1
    snap_name = snap.name
    print(f"Snapshot готов: {snap_name} (creation_time={snap.creation_time})")

    выходной = args.output or f"{args.collection}.snapshot"
    download_url = f"{url.rstrip('/')}/collections/{args.collection}/snapshots/{snap_name}"
    headers = {"api-key": key} if key else {}

    print(f"Скачиваю в {выходной} ...")
    with httpx.stream("GET", download_url, headers=headers, timeout=None) as r:
        r.raise_for_status()
        размер = int(r.headers.get("content-length", "0"))
        получено = 0
        старт = time.time()
        with open(выходной, "wb") as f:
            for батч in r.iter_bytes(chunk_size=1024 * 1024):
                f.write(батч)
                получено += len(батч)
                if размер:
                    pct = получено * 100 // размер
                    print(f"  {получено / 1e6:.1f} MB / {размер / 1e6:.1f} MB "
                          f"({pct}%)", end="\r")
        дельта = time.time() - старт
    print(f"\nГотово за {дельта:.1f}с. Файл: {выходной}")

    if args.cleanup:
        print(f"Удаляю snapshot {snap_name} с сервера...")
        клиент.delete_snapshot(collection_name=args.collection, snapshot_name=snap_name)
        print("Удалено.")

    return 0


def _serializable_vector(v):
    """Преобразует named-vectors dict для json.dumps.

    Для гибридной коллекции scroll возвращает {"dense": [...], "sparse": SparseVector(...)}.
    SparseVector не сериализуется напрямую — конвертируем в {"indices": [...], "values": [...]}.
    """
    if v is None:
        return None
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        результат = {}
        for имя, значение in v.items():
            if hasattr(значение, 'indices') and hasattr(значение, 'values'):
                результат[имя] = {
                    'indices': list(значение.indices),
                    'values': list(значение.values),
                }
            else:
                результат[имя] = значение
        return результат
    return v


def _последний_id(путь: str) -> tuple[str | None, int]:
    """Читает JSONL и возвращает (last_id, количество_строк) для резюма."""
    if not os.path.exists(путь) or os.path.getsize(путь) == 0:
        return None, 0
    last_id = None
    count = 0
    with open(путь, "r", encoding="utf-8", errors="ignore") as f:
        for строка in f:
            строка = строка.strip()
            if not строка:
                continue
            count += 1
            try:
                last_id = json.loads(строка).get("id")
            except Exception:
                pass
    return last_id, count


def экспорт_jsonl(args: argparse.Namespace) -> int:
    """Экспорт всех точек как JSONL (id + vector + payload). С резюмом и retry."""
    url, key = _конфиг()
    клиент = QdrantClient(url=url, api_key=key, prefer_grpc=False, timeout=600)

    выходной = args.output or f"{args.collection}_export.jsonl"
    последний, уже_было = _последний_id(выходной)
    if последний:
        print(f"Резюм: в {выходной} уже {уже_было} точек, продолжаю с offset={последний}",
              flush=True)
        offset = последний
        режим = "a"
    else:
        print(f"Скан коллекции {args.collection} → {выходной}", flush=True)
        offset = None
        режим = "w"

    всего_итог = None
    try:
        всего_итог = клиент.count(args.collection, exact=True).count
    except Exception:
        pass

    всего = уже_было
    старт = time.time()
    подряд_ошибок = 0
    МАКС_ОШИБОК = 5

    with open(выходной, режим, encoding="utf-8") as f:
        while True:
            try:
                батч, offset = клиент.scroll(
                    collection_name=args.collection,
                    limit=128,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )
            except Exception as e:
                подряд_ошибок += 1
                if подряд_ошибок > МАКС_ОШИБОК:
                    print(f"Слишком много ошибок подряд ({МАКС_ОШИБОК}): {e}",
                          file=sys.stderr, flush=True)
                    raise
                задержка = min(60, 2 ** подряд_ошибок)
                print(f"  ! сетевая ошибка ({type(e).__name__}: {str(e)[:100]}); "
                      f"retry через {задержка}с (попытка {подряд_ошибок}/{МАКС_ОШИБОК})",
                      flush=True)
                time.sleep(задержка)
                continue
            подряд_ошибок = 0

            for точка in батч:
                f.write(json.dumps({
                    "id": точка.id,
                    "vector": _serializable_vector(точка.vector),
                    "payload": точка.payload,
                }, ensure_ascii=False) + "\n")
            f.flush()
            всего += len(батч)
            if всего % 1280 == 0 or offset is None:
                итого = всего_итог or 472528
                pct = всего * 100 // max(итого, 1)
                скорость = (всего - уже_было) / max(time.time() - старт, 1)
                eta = (итого - всего) / max(скорость, 1)
                print(f"  Экспортировано: {всего}/{итого} точек ({pct}%) "
                      f"({скорость:.0f} pt/s, ETA {eta / 60:.1f} мин)",
                      flush=True)
            if offset is None:
                break

    print(f"Готово. Всего {всего} точек за {(time.time() - старт) / 60:.1f} мин. "
          f"Файл: {выходной}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _загрузить_env()
    парсер = argparse.ArgumentParser(description=__doc__)
    парсер.add_argument("--collection", default=КОЛЛЕКЦИЯ,
                        help=f"Имя коллекции (default {КОЛЛЕКЦИЯ})")
    парсер.add_argument("--output", default=None,
                        help="Куда сохранить (по умолчанию <collection>.snapshot или _export.jsonl)")
    парсер.add_argument("--mode", choices=["snapshot", "jsonl"], default="snapshot",
                        help="snapshot — бинарный дамп для Qdrant.recover_snapshot; "
                             "jsonl — построчный экспорт для других тулов")
    парсер.add_argument("--cleanup", action="store_true",
                        help="Удалить snapshot с сервера после скачивания")
    args = парсер.parse_args(argv)

    if args.mode == "snapshot":
        return сделать_снапшот(args)
    else:
        return экспорт_jsonl(args)


if __name__ == "__main__":
    sys.exit(main())
