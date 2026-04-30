# Отправка корпуса в Google Drive

Модуль `harvester/gdrive_upload.py` синхронизирует результаты парсинга
прямо в твою папку на Google Drive — без коммитов в git, без S3, без
постоянных пушей. Парсер крутится локально (`harvester.loop`), а свежие
PDF/метаданные/чекпоинт `state.json` уходят в Drive.

## Что и куда заливается

Внутри корневой папки (`GDRIVE_FOLDER_ID`) автоматически создаются
подпапки:

```
<твоя папка>/
├── all_pdfs/         ← PDF и DOCX, скачанные парсером
├── harvested_meta/   ← JSON-метаданные по каждому документу (источник, DOI, год…)
└── state/
    └── state.json    ← чекпоинт парсера (курсоры + список скачанных)
```

`state.json` **обновляется** на каждом прогоне (не дублируется),
PDF/метаданные **не перезаливаются** — модуль перед загрузкой смотрит
список существующих имён в подпапках и пропускает дубли.

## Настройка через Service Account (рекомендуется)

Подходит для серверных/headless-запусков, ничего не требует в браузере
после первого шага.

### 1. Создать Service Account

1. Открыть [Google Cloud Console → IAM & Admin → Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts).
2. Если проекта нет — создать любой (название значения не имеет).
3. **Create Service Account**: имя любое (например `harvester-uploader`).
4. Роли можно не выбирать (доступ к Drive выдаём через шаринг папки).
5. После создания зайти в созданный аккаунт → вкладка **Keys → Add Key →
   Create new key → JSON**. Скачается файл вида
   `<project>-<hash>.json`. Это и есть твой ключ.
6. На той же странице запомнить email вида
   `harvester-uploader@<project>.iam.gserviceaccount.com`.

### 2. Включить Drive API

[APIs & Services → Library → Google Drive API → Enable](https://console.cloud.google.com/apis/library/drive.googleapis.com).

### 3. Создать папку в Drive и расшарить её

1. Заходишь на https://drive.google.com, создаёшь папку (например
   «Парсер химии»).
2. Правый клик → **Share** → вставляешь email сервисного аккаунта
   (`harvester-uploader@…`) → выбираешь роль **Editor** → **Send**.
3. Копируешь ID папки из URL:
   `https://drive.google.com/drive/folders/`**`1AbCdEfGhIjKlMn…`** ←
   вот это и есть `GDRIVE_FOLDER_ID`.

### 4. Прописать env

Создай `.env` в корне репо (или экспортируй в шелл):

```env
GDRIVE_FOLDER_ID=1AbCdEfGhIjKlMn...
GDRIVE_CREDENTIALS_FILE=/абсолютный/путь/к/service-account.json
HARVESTER_EMAIL=ты@example.com
```

Альтернатива — содержимое JSON одной строкой (удобно для
GitHub Actions и контейнеров):

```env
GDRIVE_CREDENTIALS_JSON={"type":"service_account","project_id":"…","private_key_id":"…","private_key":"-----BEGIN PRIVATE KEY-----\n…","client_email":"…","client_id":"…","token_uri":"https://oauth2.googleapis.com/token",...}
```

### 5. Установить зависимости

```bash
pip install -r harvester/requirements.txt
# или (с основными зависимостями приложения):
pip install -r requirements.txt
```

Это поставит `google-api-python-client` и `google-auth`.

### 6. Проверить, что всё работает

```bash
# Сухой прогон — покажет, что заливалось бы, но ничего не зальёт:
python -m harvester.gdrive_upload --dry-run

# Залить только state.json (быстрая проверка кредов):
python -m harvester.gdrive_upload --state-only
```

Если видишь `[gdrive] PUT state/state.json` — ок, всё работает. Зайди
в свою папку на Drive и проверь, что файл там есть.

### 7. Запустить бесконечный парсер

```bash
python -m harvester.loop --budget 500
```

Каждая итерация после `ingest_v2` + `embed_resume_v2` автоматически
дёргает `harvester.gdrive_upload` и заливает только новые PDF +
актуальный `state.json`.

## Альтернатива: OAuth user-credentials

Нужен, если хочешь чтобы файлы в Drive **принадлежали лично тебе**
(а не сервисному аккаунту). Минус: нужно один раз авторизоваться в
браузере, потом подложить полученный refresh-token в env.

```env
GDRIVE_OAUTH_TOKEN_FILE=/абсолютный/путь/к/oauth-token.json
# Или одной строкой:
# GDRIVE_OAUTH_TOKEN_JSON={"refresh_token":"…","client_id":"…","client_secret":"…","token_uri":"https://oauth2.googleapis.com/token"}
```

Файл должен быть JSON формата `Credentials.from_authorized_user_info()`.

Если заданы оба варианта — Service Account имеет приоритет.

## CLI-флаги `harvester.gdrive_upload`

| Флаг | Что делает |
|---|---|
| `--dry-run` | Показать список файлов, которые заливались бы, ничего не заливая |
| `--state-only` | Залить (или обновить) только `harvester/state.json` |
| (без флагов) | Полный sync: все новые PDF/метаданные + state.json |

## Если что-то идёт не так

- **`[gdrive] креды не заданы`** — не заданы env `GDRIVE_CREDENTIALS_FILE`
  и `GDRIVE_CREDENTIALS_JSON` (или OAuth-аналоги). Перечитай шаг 4.
- **`HttpError 403: File not found`** при попытке залить** — папка не
  расшарена на email сервисного аккаунта. Перечитай шаг 3.
- **`HttpError 403: Service Accounts do not have storage quota`** — у
  Drive у сервисного аккаунта нет своего квоты, нужно лить в **Shared
  Drive** или в папку, расшаренную обычным юзером. Папка из шага 3
  как раз второй вариант — лимит считается из квоты владельца папки.
- **`ImportError: googleapiclient`** — зависимости не установлены,
  выполни `pip install -r harvester/requirements.txt`.
- **Файлы видны в Drive у юзера, но при попытке скачать пишет «нет
  доступа»** — это нормально для Service Account: владельцем файлов
  является сам сервисный аккаунт. Открывай через папку, в которой ты
  Editor (т.е. через `GDRIVE_FOLDER_ID`).
