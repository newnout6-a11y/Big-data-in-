"""Синхронизация all_pdfs/ + harvested_meta/ в S3-совместимое хранилище.

Заточено под Sber Cloud OBS (или любой S3-совместимый сервис с custom endpoint).
Использует boto3 с AWS Signature V4.

Настройка через env (обязательные):
  S3_ENDPOINT_URL  — например https://obs.ru-moscow-1.hc.sbercloud.ru
  S3_BUCKET        — имя бакета
  S3_ACCESS_KEY    — access key
  S3_SECRET_KEY    — secret key

Опциональные:
  S3_REGION        — regionName (дефолт: ru-moscow-1)
  S3_PREFIX        — префикс в бакете (дефолт: "") — например "harvester/"

Поведение:
  - Загружает только новые файлы из all_pdfs/ и harvested_meta/ (тупо проверяет
    HeadObject — если ключ уже есть, пропускает).
  - Синхронно, по одному файлу, без параллелизма — чтобы не словить rate limit.
  - Если креды не заданы — выходит с кодом 0 и печатает сообщение.
  - Если boto3 не установлен — печатает как поставить и выходит с кодом 0.

CLI:
  python -m harvester.s3_upload          # сихрон из дефолтных папок
  python -m harvester.s3_upload --dry-run  # только показать что заливалось бы
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКИ_ДЛЯ_СИНКА = (
    "all_pdfs",
    "harvested_meta",
)


def _получить_клиент():
    """Создаёт boto3 S3-клиент или возвращает None при проблеме."""
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    bucket = os.getenv("S3_BUCKET", "").strip()
    access_key = os.getenv("S3_ACCESS_KEY", "").strip()
    secret_key = os.getenv("S3_SECRET_KEY", "").strip()
    region = os.getenv("S3_REGION", "ru-moscow-1").strip()

    if not (endpoint and bucket and access_key and secret_key):
        print("[s3] креды не заданы (нужны S3_ENDPOINT_URL, S3_BUCKET, "
              "S3_ACCESS_KEY, S3_SECRET_KEY) — пропускаю загрузку", flush=True)
        return None, None

    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError:
        print("[s3] boto3 не установлен. Запусти: pip install boto3", flush=True)
        return None, None

    клиент = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )
    return клиент, bucket


def _ключ_уже_есть(клиент, bucket: str, ключ: str) -> bool:
    try:
        from botocore.exceptions import ClientError  # type: ignore
    except ImportError:
        return False
    try:
        клиент.head_object(Bucket=bucket, Key=ключ)
        return True
    except ClientError as e:
        код = e.response.get("Error", {}).get("Code", "")
        if код in ("404", "NoSuchKey", "NotFound"):
            return False
        # Любая другая ошибка — считаем что нет, попробуем загрузить (upload даст точный код)
        return False
    except Exception:
        # Сетевые ошибки (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError
        # и пр., от BotoCoreError, а не ClientError) — считаем что ключа нет,
        # upload_file даст точный код. Иначе один timeout ломает весь sync loop.
        return False


def _собрать_локальные_файлы(префикс_ключа: str) -> list[tuple[str, str]]:
    """Возвращает список (локальный_путь, ключ_в_бакете) для всех файлов в ПАПКИ_ДЛЯ_СИНКА."""
    файлы: list[tuple[str, str]] = []
    for папка in ПАПКИ_ДЛЯ_СИНКА:
        полный_путь = Path(_БАЗА) / папка
        if not полный_путь.exists():
            continue
        for файл in полный_путь.rglob("*"):
            if not файл.is_file():
                continue
            относительный = файл.relative_to(_БАЗА).as_posix()
            ключ = (префикс_ключа + относительный) if префикс_ключа else относительный
            файлы.append((str(файл), ключ))
    return файлы


def загрузить(dry_run: bool = False) -> int:
    """Синхронизирует локальные папки в S3. Возвращает число залитых файлов."""
    клиент, bucket = _получить_клиент()
    if not клиент or not bucket:
        return 0

    префикс = os.getenv("S3_PREFIX", "").strip().lstrip("/")
    if префикс and not префикс.endswith("/"):
        префикс += "/"

    файлы = _собрать_локальные_файлы(префикс)
    if not файлы:
        print("[s3] нечего загружать (локальные папки пусты)", flush=True)
        return 0

    залито = 0
    пропущено = 0
    ошибок = 0
    всего = len(файлы)
    for i, (локальный, ключ) in enumerate(файлы, 1):
        if _ключ_уже_есть(клиент, bucket, ключ):
            пропущено += 1
            continue
        if dry_run:
            print(f"[s3 {i}/{всего}] DRY PUT {ключ} ({os.path.getsize(локальный)//1024} КБ)", flush=True)
            залито += 1
            continue
        try:
            клиент.upload_file(локальный, bucket, ключ)
            размер = os.path.getsize(локальный) // 1024
            print(f"[s3 {i}/{всего}] PUT {ключ} ({размер} КБ)", flush=True)
            залито += 1
        except Exception as e:
            print(f"[s3 {i}/{всего}] ОШИБКА {ключ}: {type(e).__name__}: {e}", flush=True)
            ошибок += 1

    print(f"[s3] итого: залито {залито}, пропущено (уже было) {пропущено}, "
          f"ошибок {ошибок}, всего {всего}", flush=True)
    return залито


def main(argv=None) -> int:
    парсер = argparse.ArgumentParser(description="Sync all_pdfs/ + harvested_meta/ в S3")
    парсер.add_argument("--dry-run", action="store_true",
                        help="Показать что заливалось бы, но не заливать")
    args = парсер.parse_args(argv)

    загрузить(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
