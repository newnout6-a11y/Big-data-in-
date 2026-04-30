# Бесконечный харвестер

Есть два режима — **локальный** (рекомендуется, без коммитов в репо) и
GitHub Actions (без коммитов с данными в main).

## Локальный режим — `harvester.loop` + Google Drive

Парсер крутится у тебя на машине, спарсенные PDF/DOCX/TXT/метаданные и
`state.json` уходят прямо в твою папку на Google Drive через rclone.
Никаких git push'ей.

См. подробный гайд: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md).

После настройки rclone:

```bash
python -m harvester.loop --budget 500
```

`harvester.loop` перезапускается на ошибках, спит между итерациями
рандом из `[20..40]` минут с jitter ±10%, до парсинга подтягивает
свежий `state.json` из Drive, после — заливает свежак обратно.

## GitHub Actions

Воркфлоу `.github/workflows/harvest.yml` запускается **по запросу**
(`workflow_dispatch`):

1. Скачивает свежие документы из выбранных источников в `all_pdfs/`
2. Парсит/чанкит/авторазмечает их через `ingest_v2.py` → `chunks_v2.jsonl`
3. Догружает чанки в **удалённый Qdrant** (Qdrant Cloud) через `embed_resume_v2.py`
4. Опционально заливает PDF + `state.json` в Google Drive (если задан
   секрет `RCLONE_CONFIG`) или S3 (если задан `S3_BUCKET`).

`state.json` **не коммитится** в репо — между прогонами чекпоинт живёт
в Drive (откуда автоматически подтягивается в начале следующего
прогона) или его можно скачать из `Upload run artifacts` в логах.

### Настройка GH Actions

См. инструкцию по rclone+Drive — [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md),
секция "GitHub Actions".

Минимум:
- Secret `RCLONE_CONFIG` — содержимое локального `rclone.conf`
- Secret `QDRANT_URL`, `QDRANT_API_KEY`, `HARVESTER_EMAIL`
- (Опц) Secret `CORE_API_KEY` — если нужен источник CORE
- (Опц) Vars `GDRIVE_REMOTE` / `GDRIVE_BASE` — если используешь не
  дефолтные имена `gdrive` / `big-data`.

## Источники

Воркфлоу по умолчанию использует `arxiv,openalex,europepmc,stackexchange,semanticscholar,core`.
Можно поменять на лету через `workflow_dispatch` → input `sources`.

## Бюджет / тайминг

Один прогон до 6 часов на GH Actions runner-е (ubuntu-latest, 2 vCPU,
без GPU):

| Шаг | Скорость | За 5 часов |
|---|---|---|
| Скачивание | ~5 PDF/сек | ~90k PDF (но рейт-лимиты урежут до 5–15k) |
| Ингест (pypdf + чанкинг) | ~2 PDF/сек | ~36k PDF |
| Эмбеддинг (e5-base CPU) | ~80 чанков/сек | ~1.4M чанков |

Реальное узкое место — рейт-лимиты источников. По умолчанию
`--budget 500` за один прогон.

## Локально (без Qdrant Cloud)

Тот же скрипт работает с локальной БД — просто не задавай `QDRANT_URL`:

```bash
python -m harvester.harvest_full --budget 50 --email you@example.com
```

Векторы попадут в `qdrant_db/`, а Streamlit-приложение возьмёт их
оттуда автоматически.

## Если что-то идёт не так

- **Все PDF фейлятся 403/429** — обычно это chemRxiv или КиберЛенинка
  с CI-IP. Убери их из `--sources`, оставь arxiv,openalex,europepmc,
  stackexchange (стабильные).
- **Qdrant out of disk** — переключись на платный тариф, либо
  периодически удаляй чанки старше N лет.
- **rclone в Actions не находит remote** — проверь, что секрет
  `RCLONE_CONFIG` содержит блок `[gdrive]` и `token = {…}`. См.
  troubleshooting в `GOOGLE_DRIVE.md`.
- **Прогон длится >6 часов** — actions упадёт по `timeout-minutes: 350`.
  Уменьши `--time-limit-min` в воркфлоу.
