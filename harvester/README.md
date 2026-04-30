# Harvester — автосбор корпуса

Скачивает свежие PDF/тексты из открытых источников по теме «химия + IT + смежное».

## Источники

| Модуль | Что | Особенности |
|---|---|---|
| `sources/arxiv.py` | cs.LG, cs.AI, stat.ML, physics.chem-ph, cond-mat.mtrl-sci, q-bio.BM | Atom API, ≥3 сек между запросами |
| `sources/chemrxiv.py` | Все препринты с PDF | JSON API; CF может блокировать с CI-IP |
| `sources/openalex.py` | Cheminformatics, ML, Chemistry, Materials, CS | REST с курсором; нужен email в User-Agent |
| `sources/europepmc.py` | OA full-text по 8 ключевым запросам | REST, стабильный курсорный пейджинг |
| `sources/cyberleninka.py` | RU OAI-PMH (по дате) | Метаданные стабильны, PDF — CDN, может блокироваться |
| `sources/stackexchange.py` | Q+top answer (chemistry, ai, datascience, cs) | Без ключа: 10 000 запросов/день |
| `sources/semantic_scholar.py` | 200M+ публикаций, только с OA PDF | Без ключа 100 req/5min; можно указать `SEMANTIC_SCHOLAR_API_KEY` |
| `sources/core_api.py` | 130M+ OA-документов (CORE) | Требует `CORE_API_KEY` env; free tier 10 req/min, 1000/day |
| `sources/unpaywall.py` | Helper, не источник. По DOI ищет OA-копию | Fallback при paywall у openalex/europepmc |

## Запуск локально

```bash
pip install -r requirements.txt
python -m harvester.run --budget 300 --year-min 2020 --email you@example.com
```

Или сразу полный пайплайн (harvest → ingest → embed):

```bash
python -m harvester.harvest_full --budget 300 --email you@example.com
```

PDF/.txt попадают в `all_pdfs/`, метаданные — в `harvested_meta/`. Состояние
(курсоры, скачанные `doc_id`) — в `harvester/state.json`.

## Бесконечный режим — локально

Самый простой вариант: парсер крутится у тебя на машине, спарсенные
PDF/DOCX/TXT/метаданные и `state.json` уезжают прямо в Google Drive
через rclone. Никаких git push'ей с данными.

```bash
# 1) Установить rclone и авторизовать gdrive remote — гайд в
#    документация/GOOGLE_DRIVE.md
# 2) В .env (или env-переменными):
#      GDRIVE_REMOTE=gdrive
#      GDRIVE_BASE=big-data
#      HARVESTER_EMAIL=you@example.com

python -m harvester.loop --budget 500
```

`harvester.loop` бесконечно крутит `harvest_full`. До парсинга — pull
свежего state.json из Drive, после ingest+embed — push новых
PDF/DOCX/TXT/meta + state.json в Drive.

Полный гайд: [`документация/GOOGLE_DRIVE.md`](../документация/GOOGLE_DRIVE.md).

## Бесконечный режим — GitHub Actions

См. `.github/workflows/harvest.yml`. Запускается **по запросу**
(`workflow_dispatch`): раннер собирает свежие документы, ингестит,
векторизует и пушит чанки в Qdrant Cloud (по env `QDRANT_URL` +
`QDRANT_API_KEY`). `state.json` **не коммитится** обратно в репо —
если задан секрет `RCLONE_CONFIG`, чекпоинт и корпус уезжают в Drive.

Полный гайд: `документация/CRON_HARVESTER.md`.

## Этика

Используются ТОЛЬКО открытые легальные API. Никаких Sci-Hub / LibGen /
зеркал платных журналов. Все источники требуют только щадящий rate-limit и
User-Agent с email — никаких прокси/обходов.
