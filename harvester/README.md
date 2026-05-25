# Harvester

Автоматический сбор научных документов из открытых источников для базы знаний.

## Источники

| Источник | Формат | API |
|----------|--------|-----|
| arXiv | PDF | Atom API |
| OpenAlex | PDF | REST (concepts) |
| Europe PMC | PDF | REST search |
| Semantic Scholar | PDF | Graph API |
| ChemRxiv | PDF | JSON API |
| КиберЛенинка | PDF | OAI-PMH |
| Stack Exchange | TXT | REST API |
| CORE | PDF | REST v3 (нужен ключ) |

## Быстрый старт

```bash
# Собрать 100 документов:
python -m harvester.run --budget 100

# End-to-end (harvest + ingest + embed):
python -m harvester.harvest_full --budget 200

# Бесконечный цикл:
python -m harvester.loop --work-min 15 30 --sleep-min 20 40
```

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `run.py` | Оркестратор: обходит все источники, скачивает PDF/TXT |
| `harvest_full.py` | End-to-end: harvest → ingest_v2 → embed_resume_v2 |
| `loop.py` | Бесконечный цикл с рандомными паузами |
| `state.py` | Состояние: курсоры + дедуп (state.json) |
| `домены.py` | Классификация chem/it/other для балансировки |
| `gdrive_rclone.py` | Синхронизация в Google Drive |
| `s3_upload.py` | Синхронизация в S3 |
| `sources/` | Адаптеры для каждого источника |

## Переменные окружения

| Переменная | Обязательная | Описание |
|-----------|:---:|----------|
| `HARVESTER_EMAIL` | рекомендуется | Email для User-Agent (OpenAlex, Unpaywall) |
| `CORE_API_KEY` | нет | Ключ CORE API (без него CORE пропускается) |
| `SEMANTIC_SCHOLAR_API_KEY` | нет | Ключ S2 (повышает лимиты) |
| `GDRIVE_REMOTE` | нет | rclone remote для Drive |
| `S3_ENDPOINT_URL` | нет | URL S3-хранилища |

## Подробная документация

→ [`документация/HARVESTER.md`](../документация/HARVESTER.md)
