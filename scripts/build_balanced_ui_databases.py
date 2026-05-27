"""Создаёт маленькие сбалансированные Qdrant-базы для Streamlit UI.

Берёт JSONL-экспорт `knowledge_hybrid_export.jsonl` и строит отдельные
локальные базы:

    qdrant_ui/50000/
    qdrant_ui/100000/
    qdrant_ui/150000/
    qdrant_ui/200000/

В каждой базе коллекция называется `knowledge_hybrid`, чтобы UI мог работать
с ней так же, как с полной базой. Векторы не пересчитываются.

Балансировка:
1. Первый проход считает точки по группам `(domain, subdomain)`.
2. Для каждого размера выдаёт равные квоты доменам, затем равные квоты
   subdomain внутри домена, с учётом фактической ёмкости.
3. Второй проход берёт равномерный срез по всему JSONL внутри каждой группы,
   чтобы база не состояла только из первых документов экспорта.

Использование:
    python scripts/build_balanced_ui_databases.py
    python scripts/build_balanced_ui_databases.py --sizes 50000,100000
    python scripts/build_balanced_ui_databases.py --recreate
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
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
ПАПКА_UI = _БАЗА / "qdrant_ui"
КОЛЛЕКЦИЯ = "knowledge_hybrid"
РАЗМЕР_ВЕКТОРА = 768
БАТЧ = 256
РАЗМЕРЫ_ПО_УМОЛЧАНИЮ = (50_000, 100_000, 150_000, 200_000)

ПОЛЯ_ИНДЕКСОВ = [
    ("domain", PayloadSchemaType.KEYWORD),
    ("subdomain", PayloadSchemaType.KEYWORD),
    ("source", PayloadSchemaType.KEYWORD),
    ("language", PayloadSchemaType.KEYWORD),
    ("doc_id", PayloadSchemaType.KEYWORD),
    ("year", PayloadSchemaType.INTEGER),
    ("text_hash", PayloadSchemaType.KEYWORD),
]


def _группа(payload: dict) -> tuple[str, str]:
    domain = str(payload.get("domain") or "unknown").strip() or "unknown"
    subdomain = str(payload.get("subdomain") or "unknown").strip() or "unknown"
    return domain, subdomain


def _точка_из_obj(obj: dict) -> PointStruct | None:
    vec = obj.get("vector") or {}
    if not isinstance(vec, dict):
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


def _waterfill(capacity: dict, total: int) -> dict:
    """Распределяет total почти поровну между ключами, не превышая capacity."""
    result = {key: 0 for key in capacity}
    active = {key for key, cap in capacity.items() if cap > 0}
    remaining = min(total, sum(capacity.values()))
    while remaining > 0 and active:
        share = max(1, remaining // len(active))
        changed = False
        for key in list(active):
            room = capacity[key] - result[key]
            if room <= 0:
                active.remove(key)
                continue
            give = min(room, share, remaining)
            if give <= 0:
                continue
            result[key] += give
            remaining -= give
            changed = True
            if result[key] >= capacity[key]:
                active.remove(key)
            if remaining <= 0:
                break
        if not changed:
            break
    return result


def _квоты_для_размера(counts: Counter, size: int) -> dict[tuple[str, str], int]:
    domains: dict[str, int] = defaultdict(int)
    for (domain, _subdomain), count in counts.items():
        domains[domain] += count

    domain_quota = _waterfill(dict(domains), size)
    quotas: dict[tuple[str, str], int] = {}
    for domain, quota in domain_quota.items():
        sub_caps = {
            group: count
            for group, count in counts.items()
            if group[0] == domain
        }
        quotas.update(_waterfill(sub_caps, quota))
    return quotas


def _нужно_взять(seen_in_group: int, group_total: int, quota: int) -> bool:
    """Равномерный exact-sampling без хранения строк.

    Если quota=10, group_total=1000, берём примерно каждую сотую запись.
    """
    if quota <= 0 or group_total <= 0:
        return False
    before = ((seen_in_group - 1) * quota) // group_total
    after = (seen_in_group * quota) // group_total
    return after > before


def _создать_коллекцию(path: Path, recreate: bool) -> QdrantClient:
    if recreate and path.exists():
        print(f"Удаляю {path}...")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

    client = QdrantClient(path=str(path))
    collections = {c.name for c in client.get_collections().collections}
    if КОЛЛЕКЦИЯ not in collections:
        client.create_collection(
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
    for field, schema_type in ПОЛЯ_ИНДЕКСОВ:
        try:
            client.create_payload_index(КОЛЛЕКЦИЯ, field, schema_type)
        except Exception:
            pass
    return client


def _parse_sizes(raw: str) -> list[int]:
    sizes = []
    for part in raw.split(","):
        part = part.strip().replace("_", "")
        if not part:
            continue
        value = int(part)
        if value <= 0:
            raise ValueError("Размеры должны быть положительными")
        sizes.append(value)
    return sorted(set(sizes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ФАЙЛ_ВХОДНОЙ))
    parser.add_argument("--output-dir", default=str(ПАПКА_UI))
    parser.add_argument(
        "--sizes",
        default=",".join(str(s) for s in РАЗМЕРЫ_ПО_УМОЛЧАНИЮ),
        help="Размеры UI-баз через запятую",
    )
    parser.add_argument("--batch", type=int, default=БАТЧ)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    sizes = _parse_sizes(args.sizes)
    if not input_path.exists():
        print(f"Нет файла {input_path}", file=sys.stderr)
        return 1

    print(f"Считаю распределение в {input_path}...", flush=True)
    counts: Counter = Counter()
    bad = 0
    started = time.time()
    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = (json.loads(line).get("payload") or {})
                counts[_группа(payload)] += 1
            except Exception:
                bad += 1
            if line_no % 100_000 == 0:
                print(f"  просмотрено строк: {line_no}", flush=True)

    total_points = sum(counts.values())
    print(f"Валидных точек: {total_points}; битых строк: {bad}")
    if not total_points:
        return 1

    quotas_by_size = {
        size: _квоты_для_размера(counts, min(size, total_points))
        for size in sizes
    }
    for size in sizes:
        planned = sum(quotas_by_size[size].values())
        print(f"План {size}: {planned} точек, групп: {sum(1 for q in quotas_by_size[size].values() if q)}")

    clients = {}
    batches: dict[int, list[PointStruct]] = {}
    loaded = {size: 0 for size in sizes}
    try:
        for size in sizes:
            path = output_dir / str(size)
            clients[size] = _создать_коллекцию(path, args.recreate)
            batches[size] = []

        seen_by_group: Counter = Counter()
        print("Заполняю UI-базы...", flush=True)
        with input_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    payload = obj.get("payload") or {}
                    group = _группа(payload)
                except Exception:
                    continue

                seen_by_group[group] += 1
                selected_sizes = [
                    size for size in sizes
                    if _нужно_взять(
                        seen_by_group[group],
                        counts[group],
                        quotas_by_size[size].get(group, 0),
                    )
                ]
                if not selected_sizes:
                    continue

                point = _точка_из_obj(obj)
                if point is None:
                    continue
                for size in selected_sizes:
                    batches[size].append(point)
                    if len(batches[size]) >= args.batch:
                        clients[size].upsert(collection_name=КОЛЛЕКЦИЯ, points=batches[size])
                        loaded[size] += len(batches[size])
                        batches[size] = []

                if line_no % 100_000 == 0:
                    status = ", ".join(f"{s}: {loaded[s]}" for s in sizes)
                    print(f"  строка {line_no}; загружено: {status}", flush=True)

        for size in sizes:
            if batches[size]:
                clients[size].upsert(collection_name=КОЛЛЕКЦИЯ, points=batches[size])
                loaded[size] += len(batches[size])
                batches[size] = []

        print(f"\nГотово за {(time.time() - started) / 60:.1f} мин.")
        for size in sizes:
            count = clients[size].count(КОЛЛЕКЦИЯ, exact=True).count
            print(f"  {output_dir / str(size)}: {count} точек")
        return 0
    finally:
        for client in clients.values():
            close = getattr(client, "close", None)
            if callable(close):
                close()


if __name__ == "__main__":
    sys.exit(main())
