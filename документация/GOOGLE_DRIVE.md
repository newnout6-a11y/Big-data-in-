# Синхронизация с Google Drive

## Зачем

Харвестер собирает PDF и метаданные, которые не коммитятся в git (слишком большие). Вместо этого они синхронизируются в Google Drive через `rclone` — бесплатно, надёжно, доступно отовсюду.

---

## Установка rclone

### Windows
```bash
winget install Rclone.Rclone
# или скачать: https://rclone.org/downloads/
```

### Linux/macOS
```bash
curl https://rclone.org/install.sh | sudo bash
```

---

## Настройка remote

```bash
rclone config
```

Шаги:
1. `n` (new remote)
2. Имя: `gdrive`
3. Storage: `drive` (Google Drive)
4. Client ID/Secret: оставить пустым (используется встроенный)
5. Scope: `drive` (полный доступ)
6. Root folder ID: оставить пустым
7. Авторизация: откроется браузер → войти в Google аккаунт → разрешить
8. Team drive: `n`
9. Подтвердить

Проверка:
```bash
rclone lsd gdrive:
```

---

## Конфигурация проекта

В `.env`:
```env
GDRIVE_REMOTE=gdrive
GDRIVE_BASE=big-data
```

- `GDRIVE_REMOTE` — имя rclone remote (по умолчанию `gdrive`)
- `GDRIVE_BASE` — корневая папка в Drive (по умолчанию `big-data`)

---

## Структура в Drive

```
gdrive:big-data/
├── pdf/              ← all_pdfs/*.pdf
├── docx/             ← all_pdfs/*.docx
├── txt/              ← all_pdfs/*.txt
├── meta/             ← harvested_meta/*.json
└── state.json        ← harvester/state.json
```

---

## Использование

### Загрузить в Drive

```bash
python -m harvester.gdrive_rclone upload
```

Загружает:
- Все файлы из `all_pdfs/` (разделённые по типу: pdf/, docx/, txt/)
- Все JSON из `harvested_meta/`
- Текущий `harvester/state.json`

### Скачать state.json из Drive

```bash
python -m harvester.gdrive_rclone pull-state
```

Полезно для CI: перед запуском харвестера скачиваем последний state, после — загружаем обновлённый.

---

## В GitHub Actions

В workflow `harvest.yml` rclone настраивается через секрет `RCLONE_CONFIG`:

1. Локально: `cat ~/.config/rclone/rclone.conf` (или `%APPDATA%\rclone\rclone.conf`)
2. Скопировать содержимое в секрет `RCLONE_CONFIG` (Settings → Secrets → Actions)
3. Установить секрет `GDRIVE_BASE` (например `big-data`)

Workflow автоматически:
1. Создаёт `rclone.conf` из секрета
2. Скачивает `state.json` перед harvest
3. Загружает новые файлы после harvest

---

## Проверка

```bash
# Что лежит в Drive:
rclone ls gdrive:big-data/ | head -20

# Сколько файлов:
rclone size gdrive:big-data/pdf/

# Скачать всё локально (для отладки):
rclone sync gdrive:big-data/ ./drive_backup/ --progress
```

---

## Альтернатива: S3

Если предпочитаете S3-совместимое хранилище (Sber Cloud OBS, Yandex Object Storage, MinIO):

```env
S3_ENDPOINT_URL=https://obs.ru-moscow-1.hc.sbercloud.ru
S3_BUCKET=my-bucket
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_REGION=ru-moscow-1
S3_PREFIX=big-data/
```

```bash
python -m harvester.s3_upload
```

См. также [ORACLE_CLOUD.md](ORACLE_CLOUD.md) для настройки Oracle Object Storage.
