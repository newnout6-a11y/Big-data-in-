"""Синхронизация корпуса в Google Drive через rclone.

Альтернатива git push: парсер крутится локально (или в GH Actions), а
свежие PDF/DOCX/TXT/метаданные/state.json уезжают прямо в твою папку
на Drive через `rclone`. Никаких коммитов с данными в репо.

Структура папок в Drive (под корнем `<remote>:<base>/`):

    pdf/      — *.pdf из all_pdfs/
    docx/     — *.docx из all_pdfs/
    txt/      — *.txt из all_pdfs/ (StackExchange Q+A и т. п.)
    meta/     — JSON-метаданные из harvested_meta/
    images/   — картинки из PDF, извлечённые в extracted_images/
    state/    — state.json (чекпоинт парсера)

По умолчанию: remote=`gdrive`, base=`big-data`. Меняется через env
`GDRIVE_REMOTE`, `GDRIVE_BASE`.

Команды CLI:

    python -m harvester.gdrive_rclone pull-state    # скачать state.json до парсинга
    python -m harvester.gdrive_rclone pull-state --force  # восстановить свежий runner
    python -m harvester.gdrive_rclone push          # залить всё после парсинга
    python -m harvester.gdrive_rclone push --state-only  # быстрый сейв чекпоинта
    python -m harvester.gdrive_rclone push --dry-run

Подключается из `harvester.harvest_full` автоматически: если `rclone`
доступен (или задан `GDRIVE_REMOTE`/`RCLONE_CONFIG`), pull-state
вызывается до харвеста, push — после ingest+embed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ИМЯ_ФАЙЛА_СОСТОЯНИЯ = "state.json"

# Соответствие "локальная папка → имя подпапки в Drive → glob фильтр".
# Используется для разруливания файлов из all_pdfs/ по типам.
_МАРШРУТЫ = (
    # (local_dir relative to repo root, drive subdir, include glob)
    ("all_pdfs", "pdf", "*.pdf"),
    ("all_pdfs", "docx", "*.docx"),
    ("all_pdfs", "txt", "*.txt"),
    ("harvested_meta", "meta", None),  # без фильтра — все файлы
    ("extracted_images", "images", None),
)


def _путь_к_rclone() -> str | None:
    """Возвращает путь к исполняемому rclone (env RCLONE_BIN или PATH) или None."""
    кастом = os.getenv("RCLONE_BIN", "").strip()
    if кастом:
        return кастом if os.path.exists(кастом) else None
    return shutil.which("rclone")


def _аргументы_конфига() -> list[str]:
    """Если задан `RCLONE_CONFIG` (путь к rclone.conf) — добавит --config <путь>."""
    конфиг = os.getenv("RCLONE_CONFIG", "").strip()
    if конфиг:
        return ["--config", конфиг]
    return []


def _получить_remote_и_base() -> tuple[str, str]:
    remote = os.getenv("GDRIVE_REMOTE", "gdrive").strip() or "gdrive"
    base = os.getenv("GDRIVE_BASE", "big-data").strip() or "big-data"
    base = base.strip("/")
    return remote, base


def _выполнить(команда: list[str], dry_run: bool) -> int:
    """Запускает rclone (или показывает команду в dry-run). Возвращает returncode."""
    отображаемая = " ".join(команда)
    if dry_run:
        print(f"[gdrive] DRY $ {отображаемая}", flush=True)
        return 0
    print(f"[gdrive] $ {отображаемая}", flush=True)
    try:
        результат = subprocess.run(команда, check=False)
        return результат.returncode
    except FileNotFoundError:
        print("[gdrive] rclone не найден — установи его с https://rclone.org/downloads/",
              flush=True)
        return 127
    except Exception as e:
        print(f"[gdrive] ОШИБКА запуска rclone: {type(e).__name__}: {e}",
              flush=True)
        return 1


def доступен() -> bool:
    """True если rclone установлен и есть `GDRIVE_REMOTE`/дефолт + конфиг готов."""
    return _путь_к_rclone() is not None


def залить(dry_run: bool = False, только_state: bool = False, *, strict: bool = False) -> int:
    """Заливает локальные данные в Drive. Возвращает число успешных операций rclone.

    Если `только_state=True` — заливает только `harvester/state.json` (быстрый сейв).
    Полный push публикует checkpoint после успешной загрузки всех данных.
    При strict=True сообщает об ошибках исключением после попытки всех маршрутов.
    """
    rclone = _путь_к_rclone()
    if not rclone:
        print("[gdrive] rclone не найден в PATH (env RCLONE_BIN тоже пустой) — "
              "пропускаю загрузку. Установи с https://rclone.org/downloads/",
              flush=True)
        if strict:
            raise RuntimeError("rclone не найден: загрузка не выполнена")
        return 0

    remote, base = _получить_remote_и_base()
    общие = [rclone, *_аргументы_конфига()]

    успешных = 0
    ошибок = 0
    # PDF/DOCX/TXT/meta. Используем `rclone copy` с --include для разделения
    # по расширению: один общий source-каталог, разные dest-каталоги.
    for локальная_папка, drive_подпапка, фильтр in (() if только_state else _МАРШРУТЫ):
        источник = Path(_БАЗА) / локальная_папка
        if not источник.exists():
            continue
        if not any(источник.iterdir()):
            continue

        команда = [
            *общие,
            "copy",
            str(источник),
            f"{remote}:{base}/{drive_подпапка}/",
            "--no-traverse",     # быстрее на каталоге с тысячами файлов
            "--transfers", "8",
            "--checkers", "8",
            "--stats", "0",       # без периодического спама прогресса
        ]
        if фильтр:
            команда.extend(["--include", фильтр])

        код = _выполнить(команда, dry_run)
        if код == 0:
            успешных += 1
            print(f"[gdrive] OK {drive_подпапка} ← {локальная_папка}/"
                  f"{фильтр or '*'}", flush=True)
        else:
            ошибок += 1
            print(f"[gdrive] FAIL {drive_подпапка} ← {локальная_папка}/"
                  f"{фильтр or '*'} (rc={код})", flush=True)

    # Checkpoint содержит downloaded_ids: следующий runner не скачает эти
    # документы заново. Поэтому нельзя публиковать его раньше исходников
    # или после неудачной загрузки хотя бы одного маршрута данных.
    путь_state = Path(_БАЗА) / "harvester" / ИМЯ_ФАЙЛА_СОСТОЯНИЯ
    if ошибок:
        print("[gdrive] state.json не публикуется: загрузка данных не завершена", flush=True)
    elif путь_state.exists():
        команда = [
            *общие,
            "copyto",
            str(путь_state),
            f"{remote}:{base}/state/{ИМЯ_ФАЙЛА_СОСТОЯНИЯ}",
            "--quiet",
        ]
        код = _выполнить(команда, dry_run)
        if код == 0:
            успешных += 1
        else:
            ошибок += 1
            print(f"[gdrive] state.json не залился (rc={код})", flush=True)
    else:
        print(f"[gdrive] {путь_state} не найден — пропускаю state-step", flush=True)

    if только_state:
        print(f"[gdrive] state-only: {успешных} операция(й) ОК", flush=True)
        if strict and (ошибок or not успешных):
            raise RuntimeError("state.json не загружен в Drive")
        return успешных

    print(f"[gdrive] итого: {успешных} операция(й) ОК", flush=True)
    if strict and ошибок:
        raise RuntimeError(f"Загрузка в Drive: {ошибок} операция(й) завершились ошибкой")
    return успешных


def подтянуть_state(dry_run: bool = False, *, force: bool = False) -> int:
    """Скачивает state.json из Drive в `harvester/state.json`.

    По умолчанию сохраняет локальный прогресс между итерациями loop.
    Свежий checkout уже содержит state.json из Git: перед loop нужен один
    вызов с force=True. Скачанное проверяется до атомарной замены файла.
    Отсутствие checkpoint в Drive нормально для первого запуска.
    """
    путь_state = Path(_БАЗА) / "harvester" / ИМЯ_ФАЙЛА_СОСТОЯНИЯ
    if путь_state.exists() and not force:
        print("[gdrive] локальный state.json сохранён (для восстановления из Drive: --force)",
              flush=True)
        return 0

    rclone = _путь_к_rclone()
    if not rclone:
        print("[gdrive] rclone не найден — пропускаю pull-state", flush=True)
        return 127 if force else 0

    remote, base = _получить_remote_и_base()
    команда = [
        rclone,
        *_аргументы_конфига(),
        "copyto",
        f"{remote}:{base}/state/{ИМЯ_ФАЙЛА_СОСТОЯНИЯ}",
        str(путь_state.with_suffix(".download.tmp")),
        "--quiet",
    ]

    if dry_run:
        print(f"[gdrive] DRY $ {' '.join(команда)}", flush=True)
        return 0

    временный = None
    try:
        путь_state.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=путь_state.parent, prefix=".state-", suffix=".download.tmp", delete=False,
        ) as файл:
            временный = Path(файл.name)
        команда[команда.index("copyto") + 2] = str(временный)
        print(f"[gdrive] $ {' '.join(команда)}", flush=True)
        результат = subprocess.run(команда, check=False, capture_output=True, text=True)
        if результат.returncode != 0:
            stderr = (результат.stderr or "").lower()
            if "object not found" in stderr or "directory not found" in stderr:
                print("[gdrive] state.json в Drive ещё нет — стартуем с нуля", flush=True)
                return 0
            print(f"[gdrive] pull-state упал (rc={результат.returncode}): "
                  f"{(результат.stderr or '').strip()}", flush=True)
            return результат.returncode

        данные = json.loads(временный.read_text(encoding="utf-8"))
        # v2 ещё не содержит normalized_ids/domain_counts: миграция остаётся
        # в state.прочитать(). Но пустой/чужой JSON не должен стирать прогресс.
        if not isinstance(данные, dict) or not isinstance(данные.get("sources"), dict):
            raise ValueError("checkpoint должен содержать объект sources")
        for поле in ("downloaded_ids", "normalized_ids"):
            if поле == "normalized_ids" and поле not in данные:
                continue
            список = данные.get(поле)
            if not isinstance(список, list) or not all(isinstance(ид, str) for ид in список):
                raise ValueError(f"checkpoint должен содержать список строк {поле}")
        if путь_state.exists() and not force:
            return 0
        os.replace(временный, путь_state)
        print(f"[gdrive] state.json подтянут ({путь_state.stat().st_size // 1024} КБ)", flush=True)
        return 0
    except (OSError, ValueError) as ошибка:
        print(f"[gdrive] pull-state не восстановлен: {ошибка}", flush=True)
        return 1
    finally:
        if временный is not None:
            временный.unlink(missing_ok=True)


def main(argv=None) -> int:
    парсер = argparse.ArgumentParser(
        description="rclone-синхронизация корпуса харвестера с Google Drive"
    )
    под = парсер.add_subparsers(dest="команда", required=True)

    pp = под.add_parser("push", help="Залить корпус в Drive")
    pp.add_argument("--dry-run", action="store_true",
                    help="Показать команды rclone, но не запускать их")
    pp.add_argument("--state-only", action="store_true",
                    help="Залить только harvester/state.json")

    ps = под.add_parser("pull-state",
                        help="Скачать state.json из Drive до парсинга")
    ps.add_argument("--dry-run", action="store_true")
    ps.add_argument("--force", action="store_true",
                    help="Заменить Git/локальный checkpoint проверенным файлом из Drive")

    args = парсер.parse_args(argv)
    if args.команда == "push":
        try:
            залить(dry_run=args.dry_run, только_state=args.state_only, strict=True)
        except RuntimeError as ошибка:
            print(f"[gdrive] ОШИБКА: {ошибка}", flush=True)
            return 1
        return 0
    if args.команда == "pull-state":
        return подтянуть_state(dry_run=args.dry_run, force=args.force)
    return 2


if __name__ == "__main__":
    sys.exit(main())
