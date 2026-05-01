# Отправка корпуса в Google Drive (rclone)

Парсер шлёт результаты прямо в твою папку на Google Drive — без коммитов
в git, без S3, без постоянных пушей. Работает локально (`harvester.loop`)
и в GitHub Actions.

Под капотом — [`rclone`](https://rclone.org/), стандартный CLI для
синхронизации с облачными хранилищами. Все вызовы делаются через
маленькую обёртку `harvester/gdrive_rclone.py`.

## Что и куда заливается

Структура папок в Drive (под корнем `<remote>:<base>/`, по умолчанию
`gdrive:big-data/`):

```
gdrive:big-data/
├── pdf/         ← все *.pdf из all_pdfs/
├── docx/        ← все *.docx из all_pdfs/
├── txt/         ← все *.txt  из all_pdfs/ (StackExchange Q+A и т. п.)
├── meta/        ← JSON-метаданные из harvested_meta/
├── images/      ← картинки из PDF, извлечённые в extracted_images/
└── state/
    └── state.json   ← чекпоинт парсера (cursor'ы + downloaded_ids)
```

`state.json` синкается на каждом прогоне (rclone сам сравнивает по mtime
и size, не льёт зря). PDF/DOCX/TXT/meta/images дедуплицируются rclone'ом по
имени и размеру — повторно те же файлы не уезжают.

Корневую папку и имя remote'а можно сменить через env:
- `GDRIVE_REMOTE` (default `gdrive`)
- `GDRIVE_BASE` (default `big-data`)

## Шаг 1. Установить rclone

### Windows

```powershell
winget install Rclone.Rclone
```

Или скачать zip с https://rclone.org/downloads/, распаковать куда
угодно и добавить директорию с `rclone.exe` в `PATH`.

### Linux / WSL / macOS

```bash
curl -fsSL https://rclone.org/install.sh | sudo bash
```

Проверить:

```bash
rclone version
```

## Шаг 2. Авторизовать Google Drive remote

```powershell
rclone config
```

Дальше пошагово (в скобках — что нажимать):

1. `n` — New remote
2. Имя: **`gdrive`** (если назвать иначе — придётся прописать
   `GDRIVE_REMOTE=…` в env)
3. Storage type: набери `drive` и Enter (Google Drive)
4. `client_id` — пусто (Enter)
5. `client_secret` — пусто (Enter)
6. Scope: `1` (full access — `drive`)
7. `service_account_file` — пусто (Enter)
8. Edit advanced config? — `n`
9. Use auto config? — `y` → откроется браузер, **залогинься в нужный
   Google аккаунт**, разреши доступ.
10. Configure as Shared Drive? — `n` (если не используешь Shared Drives)
11. Yes this is OK — `y`
12. `q` — Quit config

Проверка:

```bash
rclone lsd gdrive:        # должен показать список папок твоего Drive
```

## Шаг 3. Прописать env (для парсера)

Создай в корне репо `.env`:

```env
# Парсер увидит эти переменные через python-dotenv (или через явный export).
# Минимум для работы Drive:
GDRIVE_REMOTE=gdrive
GDRIVE_BASE=big-data

# Email для User-Agent OpenAlex / Unpaywall:
HARVESTER_EMAIL=ты@example.com
```

`rclone.conf` обычно лежит в:
- Windows: `%APPDATA%\rclone\rclone.conf`
- Linux/macOS: `~/.config/rclone/rclone.conf`

Если он лежит в нестандартном месте, прописать `RCLONE_CONFIG=/полный/путь/rclone.conf`.

## Шаг 4. Запустить парсер

```bash
pip install -r harvester/requirements.txt   # на всякий случай
python -m harvester.loop --budget 500
```

Что произойдёт:
1. **Перед** парсингом — `rclone copyto gdrive:big-data/state/state.json
   harvester/state.json` (если файла в Drive нет — стартуем с нуля).
2. Парсер качает свежие документы → `all_pdfs/` + `harvested_meta/`,
   ингестит, пушит чанки в Qdrant.
3. **После** парсинга — `rclone copy ...` для PDF/DOCX/TXT/meta/images и
   обновление `state.json` в Drive.
4. Loop спит 20–40 минут, повторяет.

В Drive ты сразу увидишь как растёт `pdf/`, `docx/`, `txt/`, `meta/`, `images/`,
а `state/state.json` обновляется на каждой итерации.

## Полезные команды

```bash
# Проверить всё (без реальной заливки):
python -m harvester.gdrive_rclone push --dry-run

# Залить только state.json (быстрая проверка кредов после rclone config):
python -m harvester.gdrive_rclone push --state-only

# Полный sync:
python -m harvester.gdrive_rclone push

# Скачать актуальный state.json из Drive:
python -m harvester.gdrive_rclone pull-state
```

## GitHub Actions (опционально)

Workflow `.github/workflows/harvest.yml` тоже умеет в rclone — для
ручных прогонов через `workflow_dispatch`. Что нужно настроить:

1. Создать секрет **`RCLONE_CONFIG`** в Settings → Secrets and variables
   → Actions. Содержимое — вывод команды:
   ```powershell
   type "$env:APPDATA\rclone\rclone.conf"
   ```
   (на Linux/macOS: `cat ~/.config/rclone/rclone.conf`)

   Один блок `[gdrive] … token = {…}`, ничего не редактируй, просто
   вставь как есть.

2. (Опционально) Создать переменные `GDRIVE_REMOTE` / `GDRIVE_BASE`
   в Settings → Variables, если используешь не дефолтные имена.

3. Запустить workflow вручную: Actions → harvest → Run workflow.

CI-runner поднимет rclone, положит конфиг из секрета, прогонит парсер,
зальёт в Drive. State.json между прогонами автоматически подтягивается
из Drive в начале каждого прогона.

## Если что-то идёт не так

- **`rclone не найден в PATH`** — установи rclone (см. шаг 1) и
  перезапусти терминал/IDE.
- **`state.json в Drive ещё нет — стартуем с нуля`** — нормально для
  первого запуска, на следующей итерации будет уже не nuля.
- **`Failed to copy: googleapi: Error 403`** — Google revoke OAuth
  токен (бывает раз в полгода-год). Запусти `rclone config reconnect
  gdrive:` или повтори `rclone config` с тем же именем.
- **В Drive файлов меньше, чем спарсилось** — проверь `harvester/logs/run_*.json`
  → `steps.gdrive_push.return_code`. Не 0 — посмотри в стандартном
  выводе ошибку rclone.
- **`gdrive` remote не виден в Actions** — проверь что секрет
  `RCLONE_CONFIG` действительно содержит блок `[gdrive]`. Часто секрет
  вставляется без `[gdrive]` строки сверху.

## Секрет в Devin / Cognition

В сессиях Devin удобно сохранить `RCLONE_CONFIG` как **org-level**
секрет (один раз) — тогда любая будущая сессия с этим репо
автоматически получит его в env. См. [Devin secrets](https://docs.devin.ai/).
