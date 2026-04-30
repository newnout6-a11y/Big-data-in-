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

## Бесконечный режим — GitHub Actions

См. `.github/workflows/harvest.yml`. Каждые 6 часов раннер собирает свежие
документы, ингестит, векторизует и пушит чанки в Qdrant Cloud (по env-var
`QDRANT_URL` + `QDRANT_API_KEY`). `state.json` коммитится обратно в репо.

Полный гайд по настройке — `документация/CRON_HARVESTER.md`.

## Этика

Используются ТОЛЬКО открытые легальные API. Никаких Sci-Hub / LibGen /
зеркал платных журналов. Все источники требуют только щадящий rate-limit и
User-Agent с email — никаких прокси/обходов.
