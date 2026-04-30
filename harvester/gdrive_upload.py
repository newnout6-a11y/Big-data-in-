"""Синхронизация all_pdfs/ + harvested_meta/ + harvester/state.json в Google Drive.

Альтернатива `harvester.s3_upload`: пушит данные напрямую в Google Drive,
без S3-совместимого хранилища и без коммитов в git. Это и есть "просто
парсинг и отправка": локально работает бесконечный `harvester.loop`, а
свежие PDF/метаданные/state.json уезжают в твою папку на Drive.

Аутентификация — два варианта (один из двух обязателен):

1. Service Account (рекомендуется для серверных/headless-запусков).
   - В Google Cloud Console создаёшь сервисный аккаунт, скачиваешь JSON-ключ.
   - В Drive создаёшь папку и **расшариваешь её** на email сервисного
     аккаунта (`<name>@<project>.iam.gserviceaccount.com`) с ролью Editor.
   - Берёшь ID папки из URL (`https://drive.google.com/drive/folders/<ID>`).
   - Задаёшь env:
       GDRIVE_FOLDER_ID=<ID>
       GDRIVE_CREDENTIALS_FILE=/path/to/service-account.json
       (или GDRIVE_CREDENTIALS_JSON='<содержимое JSON одной строкой>')

2. OAuth user credentials (если нужно, чтобы файлы принадлежали лично тебе).
   - Один раз авторизуешься через `google-auth-oauthlib` (см. документацию).
   - Сохраняешь refresh-token в JSON.
   - Задаёшь env:
       GDRIVE_FOLDER_ID=<ID>
       GDRIVE_OAUTH_TOKEN_FILE=/path/to/token.json
       (или GDRIVE_OAUTH_TOKEN_JSON='<содержимое JSON одной строкой>')

Поведение:
  - Перед загрузкой получает список файлов в `<folder>/all_pdfs/`,
    `<folder>/harvested_meta/`, `<folder>/state/` и пропускает уже
    существующие имена. Один раз на запуск, без head-запроса на каждый файл.
  - `harvester/state.json` всегда обновляется (если файл с таким именем
    уже есть в `state/` — делаем `update`, иначе `create`). Это гарантия,
    что на Drive всегда лежит свежий чекпоинт прогресса.
  - Если креды не заданы — выходит с кодом 0 и печатает сообщение, чтобы
    `harvest_full` мог пропустить шаг без падения.
  - Если зависимости не установлены — печатает как поставить и выходит
    с кодом 0.

CLI:
  python -m harvester.gdrive_upload                # обычный sync
  python -m harvester.gdrive_upload --dry-run      # показать что заливалось бы
  python -m harvester.gdrive_upload --state-only   # только state.json (быстрый сейв)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКИ_ДЛЯ_СИНКА = (
    "all_pdfs",
    "harvested_meta",
)
ИМЯ_ПАПКИ_СОСТОЯНИЯ = "state"
ИМЯ_ФАЙЛА_СОСТОЯНИЯ = "state.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]
MIME_FOLDER = "application/vnd.google-apps.folder"


def _получить_креды():
    """Возвращает google.auth.credentials.Credentials или None при проблеме.

    Поддерживает два варианта: Service Account и OAuth user-credentials.
    Service Account имеет приоритет, если заданы оба.
    """
    sa_file = os.getenv("GDRIVE_CREDENTIALS_FILE", "").strip()
    sa_json = os.getenv("GDRIVE_CREDENTIALS_JSON", "").strip()
    oauth_file = os.getenv("GDRIVE_OAUTH_TOKEN_FILE", "").strip()
    oauth_json = os.getenv("GDRIVE_OAUTH_TOKEN_JSON", "").strip()

    if not (sa_file or sa_json or oauth_file or oauth_json):
        print("[gdrive] креды не заданы (нужен GDRIVE_CREDENTIALS_FILE / "
              "GDRIVE_CREDENTIALS_JSON или GDRIVE_OAUTH_TOKEN_FILE / "
              "GDRIVE_OAUTH_TOKEN_JSON) — пропускаю загрузку", flush=True)
        return None

    if sa_file or sa_json:
        try:
            from google.oauth2 import service_account  # type: ignore
        except ImportError:
            print("[gdrive] google-auth не установлен. Запусти: "
                  "pip install google-api-python-client google-auth", flush=True)
            return None
        try:
            if sa_json:
                info = json.loads(sa_json)
                return service_account.Credentials.from_service_account_info(
                    info, scopes=SCOPES
                )
            return service_account.Credentials.from_service_account_file(
                sa_file, scopes=SCOPES
            )
        except Exception as e:
            print(f"[gdrive] ошибка загрузки service-account кредов: "
                  f"{type(e).__name__}: {e}", flush=True)
            return None

    # OAuth user-credentials
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError:
        print("[gdrive] google-auth не установлен. Запусти: "
              "pip install google-api-python-client google-auth", flush=True)
        return None
    try:
        if oauth_json:
            info = json.loads(oauth_json)
        else:
            with open(oauth_file, "r", encoding="utf-8") as f:
                info = json.load(f)
        # google-auth ожидает поля token, refresh_token, client_id, client_secret,
        # token_uri (обычно https://oauth2.googleapis.com/token).
        return Credentials.from_authorized_user_info(info, scopes=SCOPES)
    except Exception as e:
        print(f"[gdrive] ошибка загрузки OAuth-кредов: "
              f"{type(e).__name__}: {e}", flush=True)
        return None


def _получить_сервис(креды):
    """Создаёт googleapiclient.discovery.Resource или None."""
    try:
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        print("[gdrive] google-api-python-client не установлен. Запусти: "
              "pip install google-api-python-client google-auth", flush=True)
        return None
    try:
        # cache_discovery=False — иначе ругается на отсутствие file_cache в python>=3.7
        return build("drive", "v3", credentials=креды, cache_discovery=False)
    except Exception as e:
        print(f"[gdrive] ошибка инициализации Drive API: "
              f"{type(e).__name__}: {e}", flush=True)
        return None


def _найти_подпапку(сервис, имя: str, родитель: str) -> str | None:
    """Возвращает folderId подпапки с именем `имя` внутри `родитель` или None."""
    запрос = (
        f"name = '{имя}' and "
        f"mimeType = '{MIME_FOLDER}' and "
        f"'{родитель}' in parents and "
        "trashed = false"
    )
    ответ = сервис.files().list(
        q=запрос,
        fields="files(id, name)",
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    файлы = ответ.get("files", [])
    return файлы[0]["id"] if файлы else None


def _создать_подпапку(сервис, имя: str, родитель: str) -> str:
    """Создаёт подпапку и возвращает её id."""
    мета = {
        "name": имя,
        "mimeType": MIME_FOLDER,
        "parents": [родитель],
    }
    созданный = сервис.files().create(
        body=мета,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return созданный["id"]


def _получить_или_создать_подпапку(сервис, имя: str, родитель: str) -> str:
    найденный = _найти_подпапку(сервис, имя, родитель)
    if найденный:
        return найденный
    return _создать_подпапку(сервис, имя, родитель)


def _список_файлов_в_папке(сервис, folder_id: str) -> dict[str, str]:
    """Возвращает словарь {имя_файла: file_id} всех нескрытых файлов в папке.

    Используется для дедупа: уже залитые имена пропускаем.
    """
    результат: dict[str, str] = {}
    page_token: str | None = None
    while True:
        ответ = сервис.files().list(
            q=(f"'{folder_id}' in parents and "
               f"mimeType != '{MIME_FOLDER}' and "
               "trashed = false"),
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        for файл in ответ.get("files", []):
            результат[файл["name"]] = файл["id"]
        page_token = ответ.get("nextPageToken")
        if not page_token:
            break
    return результат


def _собрать_локальные_файлы() -> list[tuple[str, str, str]]:
    """Возвращает список (локальный_путь, имя, имя_папки_назначения).

    Имя_папки_назначения — это `all_pdfs` или `harvested_meta` (без слешей).
    Имена файлов делаем плоскими (basename) — Drive хранит в подпапке.
    """
    файлы: list[tuple[str, str, str]] = []
    for папка in ПАПКИ_ДЛЯ_СИНКА:
        полный_путь = Path(_БАЗА) / папка
        if not полный_путь.exists():
            continue
        for файл in полный_путь.rglob("*"):
            if not файл.is_file():
                continue
            файлы.append((str(файл), файл.name, папка))
    return файлы


def _угадать_mime(имя: str) -> str:
    н = имя.lower()
    if н.endswith(".pdf"):
        return "application/pdf"
    if н.endswith(".json"):
        return "application/json"
    if н.endswith(".txt"):
        return "text/plain"
    if н.endswith(".docx"):
        return ("application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document")
    return "application/octet-stream"


def _залить_файл(сервис, путь: str, имя: str, parent_id: str) -> str:
    """Загружает новый файл в папку, возвращает file_id."""
    from googleapiclient.http import MediaFileUpload  # type: ignore

    мета = {"name": имя, "parents": [parent_id]}
    media = MediaFileUpload(путь, mimetype=_угадать_mime(имя), resumable=False)
    созданный = сервис.files().create(
        body=мета,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return созданный["id"]


def _обновить_файл(сервис, file_id: str, путь: str, имя: str) -> None:
    """Заменяет содержимое существующего файла (для state.json)."""
    from googleapiclient.http import MediaFileUpload  # type: ignore

    media = MediaFileUpload(путь, mimetype=_угадать_mime(имя), resumable=False)
    сервис.files().update(
        fileId=file_id,
        media_body=media,
        supportsAllDrives=True,
    ).execute()


def загрузить(dry_run: bool = False, только_state: bool = False) -> int:
    """Синхронизирует локальные папки в Drive. Возвращает число залитых файлов.

    Если `только_state=True` — заливает (или обновляет) только
    `harvester/state.json`. Удобно вызывать чаще, чем полный sync.
    """
    folder_id = os.getenv("GDRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        print("[gdrive] GDRIVE_FOLDER_ID не задан — пропускаю загрузку",
              flush=True)
        return 0

    креды = _получить_креды()
    if креды is None:
        return 0

    сервис = _получить_сервис(креды)
    if сервис is None:
        return 0

    залито = 0

    # state.json — особый случай: обновляем по имени, не по содержимому.
    путь_state = os.path.join(_БАЗА, "harvester", ИМЯ_ФАЙЛА_СОСТОЯНИЯ)
    if os.path.exists(путь_state):
        try:
            state_folder = _получить_или_создать_подпапку(
                сервис, ИМЯ_ПАПКИ_СОСТОЯНИЯ, folder_id
            )
            существующие_state = _список_файлов_в_папке(сервис, state_folder)
            if dry_run:
                режим = ("UPDATE" if ИМЯ_ФАЙЛА_СОСТОЯНИЯ in существующие_state
                         else "PUT")
                print(f"[gdrive] DRY {режим} state/{ИМЯ_ФАЙЛА_СОСТОЯНИЯ} "
                      f"({os.path.getsize(путь_state)//1024} КБ)", flush=True)
            elif ИМЯ_ФАЙЛА_СОСТОЯНИЯ in существующие_state:
                _обновить_файл(
                    сервис,
                    существующие_state[ИМЯ_ФАЙЛА_СОСТОЯНИЯ],
                    путь_state,
                    ИМЯ_ФАЙЛА_СОСТОЯНИЯ,
                )
                print(f"[gdrive] UPDATE state/{ИМЯ_ФАЙЛА_СОСТОЯНИЯ}",
                      flush=True)
            else:
                _залить_файл(
                    сервис, путь_state, ИМЯ_ФАЙЛА_СОСТОЯНИЯ, state_folder
                )
                print(f"[gdrive] PUT state/{ИМЯ_ФАЙЛА_СОСТОЯНИЯ}", flush=True)
            залито += 1
        except Exception as e:
            print(f"[gdrive] ОШИБКА state.json: {type(e).__name__}: {e}",
                  flush=True)

    if только_state:
        print(f"[gdrive] state-only режим: затронуто {залито} файлов",
              flush=True)
        return залито

    файлы = _собрать_локальные_файлы()
    if not файлы:
        print("[gdrive] нечего загружать (локальные all_pdfs/ и "
              "harvested_meta/ пусты)", flush=True)
        return залито

    # Группируем по подпапкам — для каждой получаем (или создаём) folder_id
    # и снимок уже залитых имён один раз.
    подпапки: dict[str, dict[str, str]] = {}
    подпапки_id: dict[str, str] = {}
    for имя_подпапки in {p[2] for p in файлы}:
        подпапки_id[имя_подпапки] = _получить_или_создать_подпапку(
            сервис, имя_подпапки, folder_id
        )
        подпапки[имя_подпапки] = _список_файлов_в_папке(
            сервис, подпапки_id[имя_подпапки]
        )

    пропущено = 0
    ошибок = 0
    всего = len(файлы)
    for i, (локальный, имя, подпапка) in enumerate(файлы, 1):
        if имя in подпапки[подпапка]:
            пропущено += 1
            continue
        if dry_run:
            print(f"[gdrive {i}/{всего}] DRY PUT {подпапка}/{имя} "
                  f"({os.path.getsize(локальный)//1024} КБ)", flush=True)
            залито += 1
            continue
        try:
            _залить_файл(сервис, локальный, имя, подпапки_id[подпапка])
            размер = os.path.getsize(локальный) // 1024
            print(f"[gdrive {i}/{всего}] PUT {подпапка}/{имя} ({размер} КБ)",
                  flush=True)
            залито += 1
        except Exception as e:
            print(f"[gdrive {i}/{всего}] ОШИБКА {подпапка}/{имя}: "
                  f"{type(e).__name__}: {e}", flush=True)
            ошибок += 1

    print(f"[gdrive] итого: залито {залито}, пропущено (уже было) "
          f"{пропущено}, ошибок {ошибок}, файлов в обработке {всего}",
          flush=True)
    return залито


def main(argv=None) -> int:
    парсер = argparse.ArgumentParser(
        description="Sync all_pdfs/ + harvested_meta/ + state.json в Google Drive"
    )
    парсер.add_argument("--dry-run", action="store_true",
                        help="Показать что заливалось бы, но не заливать")
    парсер.add_argument("--state-only", action="store_true",
                        help="Залить только harvester/state.json (быстрый сейв)")
    args = парсер.parse_args(argv)

    загрузить(dry_run=args.dry_run, только_state=args.state_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
