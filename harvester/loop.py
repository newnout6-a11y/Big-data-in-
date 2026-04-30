"""Бесконечный цикл harvester'а с рандомными таймингами.

Каждая итерация:
  1. Запускает `harvester.harvest_full` с лимитом work_min (рандом из диапазона).
  2. Опционально пушит новые PDF/metadata в S3 (если заданы креды).
  3. Спит sleep_min минут (рандом из диапазона), с jitter'ом +/-10%.

Поведение:
  - Auto-restart: если harvest_full упал — логируем, ждём SLEEP_ON_ERROR_MIN и идём на
    следующую итерацию. Цикл не прерывается.
  - Ctrl+C / SIGTERM — корректный выход.
  - Для auto-restart при перезагрузке ПК — см. документация/ЛОКАЛЬНЫЙ_ЗАПУСК.md,
    там инструкция по Task Scheduler с «при входе в систему».

Настройка (env или CLI):
  HARVEST_WORK_MIN_LOW=100   — нижняя граница времени работы (минут)
  HARVEST_WORK_MIN_HIGH=140  — верхняя граница
  HARVEST_SLEEP_MIN_LOW=20
  HARVEST_SLEEP_MIN_HIGH=40
  HARVEST_MAX_ITERATIONS=0   — 0 = бесконечно, N = остановиться после N итераций
                                (удобно для тестов)
"""
from __future__ import annotations

import argparse
import os
import random
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Минимальная пауза после ошибки, чтобы не долбить API при проблемах с сетью.
SLEEP_ON_ERROR_MIN = 5

_прервано = False


def _обработчик_сигнала(signum, frame):
    global _прервано
    _прервано = True
    print(f"\n[loop] получен сигнал {signum}, завершаюсь после текущей итерации…", flush=True)


def _сон_минут(минут: float) -> None:
    """Сон с проверкой флага прерывания каждые 5 секунд."""
    осталось = минут * 60.0
    while осталось > 0 and not _прервано:
        time.sleep(min(5.0, осталось))
        осталось -= 5.0


def _сейчас() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _запустить_итерацию(args, work_min: int) -> int:
    """Запускает harvest_full как subprocess, возвращает returncode."""
    команда = [
        sys.executable, "-m", "harvester.harvest_full",
        "--budget", str(args.budget),
        "--year-min", str(args.year_min),
        "--sources", args.sources,
        "--time-limit-min", str(work_min),
    ]
    if args.email:
        команда.extend(["--email", args.email])

    print(f"\n[loop] {_сейчас()} — итерация старт, work={work_min} мин", flush=True)
    print(f"[loop] $ {' '.join(команда)}", flush=True)
    try:
        результат = subprocess.run(команда, cwd=_БАЗА, check=False)
        return результат.returncode
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"[loop] subprocess упал: {type(e).__name__}: {e}", flush=True)
        return 1


def main(argv=None) -> int:
    парсер = argparse.ArgumentParser(description="Бесконечный цикл harvester'а")
    парсер.add_argument("--budget", type=int, default=int(os.getenv("HARVESTER_BUDGET", "2000")))
    парсер.add_argument("--year-min", type=int, default=int(os.getenv("HARVESTER_YEAR_MIN", "2020")))
    парсер.add_argument("--email", type=str, default=os.getenv("HARVESTER_EMAIL", ""))
    парсер.add_argument("--sources", type=str, default=os.getenv(
        "HARVESTER_SOURCES",
        "arxiv,chemrxiv,openalex,europepmc,cyberleninka,stackexchange,semanticscholar",
    ))
    парсер.add_argument("--work-min-low", type=int, default=int(os.getenv("HARVEST_WORK_MIN_LOW", "100")))
    парсер.add_argument("--work-min-high", type=int, default=int(os.getenv("HARVEST_WORK_MIN_HIGH", "140")))
    парсер.add_argument("--sleep-min-low", type=int, default=int(os.getenv("HARVEST_SLEEP_MIN_LOW", "20")))
    парсер.add_argument("--sleep-min-high", type=int, default=int(os.getenv("HARVEST_SLEEP_MIN_HIGH", "40")))
    парсер.add_argument("--max-iterations", type=int, default=int(os.getenv("HARVEST_MAX_ITERATIONS", "0")),
                        help="0 = бесконечно")
    args = парсер.parse_args(argv)

    if args.work_min_low > args.work_min_high or args.work_min_low <= 0:
        print("Ошибка: work-min-low должен быть <= work-min-high и > 0", flush=True)
        return 2
    if args.sleep_min_low > args.sleep_min_high or args.sleep_min_low < 0:
        print("Ошибка: sleep-min-low должен быть <= sleep-min-high и >= 0", flush=True)
        return 2

    signal.signal(signal.SIGINT, _обработчик_сигнала)
    try:
        signal.signal(signal.SIGTERM, _обработчик_сигнала)
    except (AttributeError, ValueError):
        pass  # Windows не всегда принимает SIGTERM

    print(f"[loop] старт. work=[{args.work_min_low}..{args.work_min_high}] мин, "
          f"sleep=[{args.sleep_min_low}..{args.sleep_min_high}] мин, "
          f"max_iterations={args.max_iterations or '∞'}", flush=True)
    if os.getenv("S3_BUCKET"):
        print(f"[loop] S3 upload включён (bucket={os.getenv('S3_BUCKET')}) — "
              f"вызывается внутри harvest_full", flush=True)
    else:
        print("[loop] S3 upload выключен (S3_BUCKET не задан)", flush=True)

    if os.getenv("GDRIVE_FOLDER_ID"):
        print(f"[loop] Google Drive upload включён "
              f"(folder={os.getenv('GDRIVE_FOLDER_ID')}) — "
              f"вызывается внутри harvest_full", flush=True)
    else:
        print("[loop] Google Drive upload выключен "
              "(GDRIVE_FOLDER_ID не задан — чисто локально)", flush=True)

    # Сбрасываем флаг на случай повторного вызова main() в том же процессе
    # (напр. тесты или программный запуск). Иначе сигнал из прошлого вызова
    # останется и новый цикл не сделает ни одной итерации.
    global _прервано
    _прервано = False

    итерация = 0
    while not _прервано:
        if args.max_iterations and итерация >= args.max_iterations:
            print(f"[loop] достигнут лимит итераций ({args.max_iterations}), выхожу", flush=True)
            break
        итерация += 1

        work_min = random.randint(args.work_min_low, args.work_min_high)
        код = _запустить_итерацию(args, work_min)
        if код != 0:
            print(f"[loop] итерация {итерация}: harvest_full вернул {код}, "
                  f"sleep {SLEEP_ON_ERROR_MIN} мин и продолжаем", flush=True)
            _сон_минут(SLEEP_ON_ERROR_MIN)
            continue

        # S3 upload делается внутри harvest_full (шаг 4) — здесь повторять не нужно.

        if _прервано:
            break

        sleep_min = random.randint(args.sleep_min_low, args.sleep_min_high)
        # Джиттер +/-10%, чтобы не было ровно на минуту
        sleep_min_с_джиттером = sleep_min * random.uniform(0.9, 1.1)
        print(f"[loop] итерация {итерация} ок, спим {sleep_min_с_джиттером:.1f} мин", flush=True)
        _сон_минут(sleep_min_с_джиттером)

    print(f"[loop] остановлен. всего итераций: {итерация}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
