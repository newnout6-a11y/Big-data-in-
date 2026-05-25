# Harvester

Автоматический сбор научных документов из 8 открытых источников для базы знаний. Непрерывный цикл с балансировкой доменов, кросс-источниковым дедупом и синхронизацией в Google Drive / Qdrant Cloud.

## Источники

| Источник | Формат | API | Rate limit |
|----------|--------|-----|------------|
| arXiv | PDF | Atom XML | 3 сек/запрос |
| OpenAlex | PDF | REST (19 концептов) | 0.5 сек |
| Europe PMC | PDF | REST (~80 запросов) | 0.5 сек |
| Semantic Scholar | PDF | Graph API (40+ запросов) | 1 сек, backoff при 429 |
| ChemRxiv | PDF | JSON API | 1 сек, CF может блокировать |
| КиберЛенинка | PDF | OAI-PMH | 0.5 сек |
| Stack Exchange | TXT | REST (13 сайтов) | 0.5 сек + backoff |
| CORE | PDF | REST v3 (нужен ключ) | 6.5 сек (10 req/мин) |

Unpaywall — вспомогательный: ищет OA-копию по DOI при провале основного скачивания.

## Быстрый старт

```bash
# Собрать 100 документов:
python -m harvester.run --budget 100

# End-to-end (harvest + ingest + embed):
python -m harvester.harvest_full --budget 200

# Бесконечный цикл:
python -m harvester.loop --work-min-low 15 --work-min-high 30 --sleep-min-low 20 --sleep-min-high 40
```

## Как работает цикл

```
harvest_full (8-12 мин)  →  пауза (2-5 мин, jitter ±10%)  →  повтор
                              ↑                                    │
                              └── при ошибке: пауза 5 мин ────────┘
```

Тайминги рандомизированы. В GitHub Actions runner запускает `harvester.loop` на 5.5 часов (`timeout-minutes: 350`) — это решает проблему ненадёжного cron.

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `run.py` | Оркестратор: обходит все источники, скачивает PDF/TXT |
| `harvest_full.py` | End-to-end: harvest → ingest_v2 → embed_resume_v2 |
| `loop.py` | Бесконечный цикл с рандомными паузами |
| `state.py` | Состояние: курсоры + дедуп по normalized ID (state.json) |
| `домены.py` | Классификация chem/it/other + балансировка бюджетов |
| `gdrive_rclone.py` | Синхронизация в Google Drive |
| `s3_upload.py` | Синхронизация в S3 |
| `sources/` | Адаптеры для каждого источника |

## Rate limits и защита

- Каждый адаптер делает `time.sleep()` между запросами (от 0.5 до 6.5 сек)
- 429 → backoff 10 сек, макс 3 ретрая, потом источник пропускается
- PDF скачиваются с Chrome User-Agent + `Referer: google.com` для прохождения CDN
- ChemRxiv за Cloudflare: при 403 пропускается, материалы дублируются через OpenAlex

## Дедуп

Один документ из разных источников (arXiv + OpenAlex) не скачивается дважды. Нормализация: `arxiv:2304.12345v2` → `arxiv:2304.12345`, DOI → `doi:10.xxxx/yyyy`.

## Переменные окружения

| Переменная | Обязательная | Описание |
|-----------|:---:|----------|
| `HARVESTER_EMAIL` | рекомендуется | Email для User-Agent (OpenAlex, Unpaywall) |
| `CORE_API_KEY` | нет | Ключ CORE API (без него CORE пропускается) |
| `SEMANTIC_SCHOLAR_API_KEY` | нет | Ключ S2 (повышает лимиты) |
| `GDRIVE_REMOTE` | нет | rclone remote для Drive |
| `S3_ENDPOINT_URL` | нет | URL S3-хранилища |

## Подробная документация

→ [`документация/HARVESTER.md`](../документация/HARVESTER.md) — полное описание с диаграммами, state-форматом, балансировкой и GitHub Actions.
