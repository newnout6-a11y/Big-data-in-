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
    python -m harvester.gdrive_rclone push          # залить всё после парсинга
    python -m harvester.gdrive_rclone push --state-only  # быстрый сейв чекпоинта
    python -m harvester.gdrive_rclone push --dry-run

Подключается из `harvester.harvest_full` автоматически: если `rclone`
доступен (или задан `GDRIVE_REMOTE`/`RCLONE_CONFIG`), pull-state
вызывается до харвеста, push — после ingest+embed.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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


def залить(dry_run: bool = False, только_state: bool = False) -> int:
    """Заливает локальные данные в Drive. Возвращает число успешных операций rclone.

    Если `только_state=True` — заливает только `harvester/state.json` (быстрый сейв).
    """
    rclone = _путь_к_rclone()
    if not rclone:
        print("[gdrive] rclone не найден в PATH (env RCLONE_BIN тоже пустой) — "
              "пропускаю загрузку. Установи с https://rclone.org/downloads/",
              flush=True)
        return 0

    remote, base = _получить_remote_и_base()
    общие = [rclone, *_аргументы_конфига()]

    успешных = 0
    путь_state = Path(_БАЗА) / "harvester" / ИМЯ_ФАЙЛА_СОСТОЯНИЯ
    if путь_state.exists():
        # rclone copyto — для одиночного файла с явным именем назначения.
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
            print(f"[gdrive] state.json не залился (rc={код})", flush=True)
    else:
        print(f"[gdrive] {путь_state} не найден — пропускаю state-step",
              flush=True)

    if только_state:
        print(f"[gdrive] state-only: {успешных} операция(й) ОК", flush=True)
        return успешных

    # PDF/DOCX/TXT/meta. Используем `rclone copy` с --include для разделения
    # по расширению: один общий source-каталог, разные dest-каталоги.
    for локальная_папка, drive_подпапка, фильтр in _МАРШРУТЫ:
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
            print(f"[gdrive] FAIL {drive_подпапка} ← {локальная_папка}/"
                  f"{фильтр or '*'} (rc={код})", flush=True)

    print(f"[gdrive] итого: {успешных} операция(й) ОК", flush=True)
    return успешных


def подтянуть_state(dry_run: bool = False) -> int:
    """Скачивает state.json из Drive в `harvester/state.json`.

    Используется в начале прогона — чтобы харвестер продолжил с того места,
    где остановился предыдущий runner. Если в Drive ещё нет state.json
    (первый запуск) — печатает сообщение и возвращает 0 без падения.
    """
    rclone = _путь_к_rclone()
    if not rclone:
        print("[gdrive] rclone не найден — пропускаю pull-state", flush=True)
        return 0

    remote, base = _получить_remote_и_base()
    путь_state = Path(_БАЗА) / "harvester" / ИМЯ_ФАЙЛА_СОСТОЯНИЯ
    путь_state.parent.mkdir(parents=True, exist_ok=True)

    команда = [
        rclone,
        *_аргументы_конфига(),
        "copyto",
        f"{remote}:{base}/state/{ИМЯ_ФАЙЛА_СОСТОЯНИЯ}",
        str(путь_state),
        "--ignore-existing", "--quiet",
    ]
    # --ignore-existing: если у нас уже есть локальный state.json (свежее
    # после прошлой итерации) — не перезаписывать. Это безопасно для loop'а.
    # Для свежего runner'а локального state нет, и rclone скачает свежий.

    if dry_run:
        print(f"[gdrive] DRY $ {' '.join(команда)}", flush=True)
        return 0

    print(f"[gdrive] $ {' '.join(команда)}", flush=True)
    результат = subprocess.run(команда, check=False, capture_output=True, text=True)
    if результат.returncode == 0:
        if путь_state.exists():
            размер = путь_state.stat().st_size // 1024
            print(f"[gdrive] state.json подтянут ({размер} КБ) или уже актуален",
                  flush=True)
        return 0

    # Нет файла в Drive — нормально для первого запуска. rclone в этом случае
    # выводит "directory not found" / "object not found" и rc != 0.
    stderr = (результат.stderr or "").lower()
    if "not found" in stderr or "doesn't exist" in stderr or "no such" in stderr:
        print("[gdrive] state.json в Drive ещё нет — стартуем с нуля",
              flush=True)
        return 0
    print(f"[gdrive] pull-state упал (rc={результат.returncode}): "
          f"{результат.stderr.strip()}", flush=True)
    return результат.returncode


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

    args = парсер.parse_args(argv)
    if args.команда == "push":
        залить(dry_run=args.dry_run, только_state=args.state_only)
        return 0
    if args.команда == "pull-state":
        подтянуть_state(dry_run=args.dry_run)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
