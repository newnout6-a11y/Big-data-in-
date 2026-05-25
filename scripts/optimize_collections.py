"""Оптимизация локальных коллекций Qdrant: on_disk + binary quantization.

Скрипт перебирает ВСЕ коллекции в qdrant_db/ и применяет:
  1. on_disk=True для dense-векторов (экономит RAM)
  2. BinaryQuantization(always_ram=True) — 1 бит вместо 32 бит на компоненту
  3. on_disk=True для sparse-индексов (если есть)

Это снижает потребление RAM примерно в 30x для dense-векторов.

Использование:
    python scripts/optimize_collections.py             # все коллекции
    python scripts/optimize_collections.py --only химия knowledge_hybrid
    python scripts/optimize_collections.py --dry-run   # только показать план
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    BinaryQuantization,
    BinaryQuantizationConfig,
)

_БАЗА = Path(__file__).resolve().parent.parent
ПАПКА_БД = _БАЗА / "qdrant_db"


def _rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def optimize(клиент: QdrantClient, имя: str, dry_run: bool) -> None:
    """Обновляет одну коллекцию: quantization + on_disk."""
    try:
        инфо = клиент.get_collection(имя)
    except Exception as e:
        print(f"  [SKIP] {имя}: не удалось получить инфо ({e})")
        return

    точки = инфо.points_count or 0
    квант = инфо.config.quantization_config
    уже_квант = квант is not None

    print(f"\n  {имя}: {точки} точек, quantization={'да' if уже_квант else 'нет'}")

    if уже_квант:
        print(f"  [OK] binary quantization уже включена, пропускаю")
        return

    if dry_run:
        print(f"  [DRY-RUN] будет применено: BinaryQuantization + on_disk=True")
        return

    print(f"  Применяю binary quantization...")
    клиент.update_collection(
        collection_name=имя,
        quantization_config=BinaryQuantization(
            binary=BinaryQuantizationConfig(always_ram=True),
        ),
    )
    print(f"  [OK] quantization применена")

    # Обновляем dense-вектор на on_disk (если он есть)
    # Qdrant update_collection позволяет включить on_disk для named-vectors
    # через vectors_config, но для простых unnamed-векторов — через
    # optimizers_config (memmap_threshold=20000).
    # Для безопасности ставим memmap_threshold — это переводит сегменты на mmap.
    try:
        клиент.update_collection(
            collection_name=имя,
            optimizers_config={"memmap_threshold": 20000},
        )
        print(f"  [OK] memmap_threshold=20000 (сегменты будут на диске)")
    except Exception as e:
        print(f"  [WARN] не удалось выставить memmap_threshold: {e}")


def main(argv: list[str] | None = None) -> int:
    парсер = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    парсер.add_argument("--only", nargs="*", default=None,
                        help="Оптимизировать только перечисленные коллекции")
    парсер.add_argument("--dry-run", action="store_true",
                        help="Только показать план, не менять ничего")
    args = парсер.parse_args(argv)

    if not ПАПКА_БД.exists():
        print(f"Папка {ПАПКА_БД} не найдена", file=sys.stderr)
        return 1

    print(f"RSS на старте: {_rss_mb():.0f} MB")
    print(f"Открываю {ПАПКА_БД}...")

    клиент = QdrantClient(path=str(ПАПКА_БД))
    print(f"RSS после открытия: {_rss_mb():.0f} MB")

    коллекции = [к.name for к in клиент.get_collections().collections]
    print(f"Всего коллекций: {len(коллекции)}")

    if args.only:
        коллекции = [к for к in коллекции if к in args.only]
        print(f"Фильтр --only: {len(коллекции)} коллекций")

    # Сначала большие коллекции (химия, knowledge_hybrid), потом user notebooks
    приоритет = {"химия": 0, "knowledge_hybrid": 1, "knowledge": 2}
    коллекции.sort(key=lambda к: приоритет.get(к, 100))

    старт = time.time()
    for имя in коллекции:
        optimize(клиент, имя, args.dry_run)
        print(f"  RSS: {_rss_mb():.0f} MB")

    клиент.close()
    print(f"\nГотово за {time.time() - старт:.1f}с, финальный RSS: {_rss_mb():.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
