"""End-to-end оркестратор для GitHub Actions cron.

Делает в одной команде:
  1. harvester.run — собирает PDF/тексты в all_pdfs/
  2. ingest_v2 — обрабатывает только новые файлы (инкрементально)
  3. embed_resume_v2 — догружает чанки в Qdrant (локальный или удалённый)

Пишет короткий отчёт в harvester/logs/run_<timestamp>.json — пригодится для
auto-commit в GH Actions + статистики.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКА_ЛОГОВ = os.path.join(_БАЗА, "harvester", "logs")


def _запустить(команда, окруж=None):
    print(f"\n$ {' '.join(команда)}", flush=True)
    т_старт = time.time()
    try:
        результат = subprocess.run(команда, cwd=_БАЗА, env=окруж, check=False)
        код = результат.returncode
    except Exception as e:
        print(f"ОШИБКА: {e}")
        код = 1
    return код, time.time() - т_старт


def main(argv=None):
    парсер = argparse.ArgumentParser(description="harvest → ingest → embed")
    парсер.add_argument("--budget", type=int, default=300)
    парсер.add_argument("--year-min", type=int, default=2020)
    парсер.add_argument("--email", type=str, default=os.getenv("HARVESTER_EMAIL", ""))
    парсер.add_argument("--sources", type=str, default="arxiv,openalex,europepmc,stackexchange,semanticscholar,chemrxiv")
    парсер.add_argument("--time-limit-min", type=int, default=300, help="Полный лимит на пайплайн")
    парсер.add_argument("--skip-ingest", action="store_true")
    парсер.add_argument("--skip-embed", action="store_true")
    args = парсер.parse_args(argv)

    os.makedirs(ПАПКА_ЛОГОВ, exist_ok=True)
    отчёт = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "args": vars(args),
        "steps": {},
    }

    окруж = os.environ.copy()
    if args.email and "HARVESTER_EMAIL" not in окруж:
        окруж["HARVESTER_EMAIL"] = args.email

    дедлайн = time.time() + args.time_limit_min * 60

    # Шаг 0 — подтянуть state.json из Drive (если rclone настроен).
    # Делается до харвеста, чтобы свежий runner начал с актуального чекпоинта.
    if os.getenv("GDRIVE_REMOTE") or os.getenv("RCLONE_CONFIG"):
        команда_pull = [sys.executable, "-m", "harvester.gdrive_rclone", "pull-state"]
        код0, дл0 = _запустить(команда_pull, окруж)
        отчёт["steps"]["gdrive_pull_state"] = {
            "return_code": код0, "seconds": round(дл0, 1),
        }

    # Шаг 1 — харвестинг
    лимит = max(1, int((дедлайн - time.time()) / 60 * 0.5))
    команда_harvest = [
        sys.executable, "-m", "harvester.run",
        "--budget", str(args.budget),
        "--year-min", str(args.year_min),
        "--sources", args.sources,
        "--time-limit-min", str(лимит),
    ]
    if args.email:
        команда_harvest.extend(["--email", args.email])
    код, длительность = _запустить(команда_harvest, окруж)
    отчёт["steps"]["harvest"] = {"return_code": код, "seconds": round(длительность, 1)}

    # Шаг 2 — ингест
    if not args.skip_ingest and time.time() < дедлайн:
        команда_ingest = [sys.executable, "ingest_v2.py"]
        код2, дл2 = _запустить(команда_ingest, окруж)
        отчёт["steps"]["ingest"] = {"return_code": код2, "seconds": round(дл2, 1)}

    # Шаг 3 — векторизация
    if not args.skip_embed and time.time() < дедлайн:
        команда_embed = [sys.executable, "embed_resume_v2.py"]
        код3, дл3 = _запустить(команда_embed, окруж)
        отчёт["steps"]["embed"] = {"return_code": код3, "seconds": round(дл3, 1)}

    # Шаг 4 — S3 upload (опционально, только если заданы креды и есть время)
    if os.getenv("S3_BUCKET") and time.time() < дедлайн:
        команда_s3 = [sys.executable, "-m", "harvester.s3_upload"]
        код4, дл4 = _запустить(команда_s3, окруж)
        отчёт["steps"]["s3_upload"] = {"return_code": код4, "seconds": round(дл4, 1)}

    # Шаг 5 — Google Drive push через rclone (если задан GDRIVE_REMOTE
    # или указан путь к rclone.conf через RCLONE_CONFIG).
    # Заливает all_pdfs/ (по типам) + harvested_meta/ + harvester/state.json.
    if (os.getenv("GDRIVE_REMOTE") or os.getenv("RCLONE_CONFIG")) and time.time() < дедлайн:
        команда_push = [sys.executable, "-m", "harvester.gdrive_rclone", "push"]
        код5, дл5 = _запустить(команда_push, окруж)
        отчёт["steps"]["gdrive_push"] = {
            "return_code": код5, "seconds": round(дл5, 1),
        }

    отчёт["finished_at"] = datetime.now(timezone.utc).isoformat()
    путь_отчёта = os.path.join(ПАПКА_ЛОГОВ, f"run_{отчёт['started_at'].replace(':','-')}.json")
    with open(путь_отчёта, "w", encoding="utf-8") as f:
        json.dump(отчёт, f, ensure_ascii=False, indent=2)

    print(f"\nОтчёт: {путь_отчёта}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
