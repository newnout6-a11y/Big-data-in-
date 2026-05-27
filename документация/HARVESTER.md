# Харвестер — автосбор научных документов

## Обзор

Модуль `harvester/` автоматически собирает научные документы (PDF и тексты) из 8 открытых источников, сохраняет их в `all_pdfs/` с метаданными в `harvested_meta/`, и опционально синхронизирует в Google Drive или S3.

Цель — непрерывно наращивать корпус по тематике **химия + IT/ML**, не перекашивая баланс и не скачивая дубли.

---

## Источники

| Источник | Модуль | API | Формат | Rate limit | Примечания |
|----------|--------|-----|--------|------------|-----------|
| arXiv | `sources/arxiv.py` | Atom XML | PDF | 3 сек между запросами | cs.LG, physics.chem-ph, cond-mat.mtrl-sci, q-bio и ещё ~14 категорий |
| OpenAlex | `sources/openalex.py` | REST JSON | PDF | 0.5 сек; ~10 req/s с email, ~2 без | 19 концептов: cheminformatics, ML, chemistry, materials, biology и др. |
| Europe PMC | `sources/europepmc.py` | REST JSON | PDF | 0.5 сек между страницами | ~80 запросов по темам: от DFT до CRISPR. Фильтр `OPEN_ACCESS:Y` + `HAS_PDF:Y` |
| Semantic Scholar | `sources/semantic_scholar.py` | Graph API | PDF | 1 сек; 429 → backoff 10 сек, макс 3 ретрая | 40+ запросов, фильтр `openAccessPdf=true`. Опциональный API-ключ повышает лимиты |
| ChemRxiv | `sources/chemrxiv.py` | JSON API | PDF | 1 сек | За Cloudflare — может блокировать (см. ниже). Дубли тянутся через OpenAlex |
| КиберЛенинка | `sources/cyberleninka.py` | OAI-PMH XML | PDF | 0.5 сек | Русскоязычные статьи. Локальный стем-фильтр отсекает педагогику/филологию |
| Stack Exchange | `sources/stackexchange.py` | REST JSON | TXT | 0.5 сек; если `backoff` в ответе — ждём указанное время | Q+A как синтетические документы. 13 сайтов: chemistry, ai, stackoverflow, math и др. |
| CORE | `sources/core_api.py` | REST v3 JSON | PDF | 6.5 сек (free: 10 req/мин, 1000/день); 429 → backoff | Нужен `CORE_API_KEY` (бесплатный), без него источник молча пропускается |
| Unpaywall | `sources/unpaywall.py` | REST JSON | — | ~100K req/день | **Вспомогательный**: ищет легальную OA-копию по DOI, когда основной PDF-url недоступен |

---

## Как работает цикл

### Одна итерация (`harvester.run`)

```
1. Читаем state.json — курсоры каждого источника + список уже скачанных ID
2. Считаем коэффициенты балансировки (chem/it/other) → распределяем бюджет
3. По очереди обходим каждый источник:
   а) Запрашиваем API с текущего курсора
   б) Для каждого документа:
      - Проверяем кросс-источниковый дедуп (normalized_id)
      - Скачиваем PDF (или сохраняем текст для StackExchange)
      - При провале PDF → Unpaywall fallback по DOI
      - Классифицируем домен (chem/it/other)
      - Сохраняем метадату в harvested_meta/
   в) Обновляем курсор в state
4. Сохраняем state.json
```

### End-to-end (`harvester.harvest_full`)

Объединяет 3 шага в одной команде:
1. **harvest** — `harvester.run` (сбор PDF/текстов)
2. **ingest** — `ingest_v2.py` (обработка новых файлов → чанки)
3. **embed** — `embed_resume_v2.py` (догрузка чанков в Qdrant)

Пишет отчёт в `harvester/logs/run_<timestamp>.json`.

### Бесконечный цикл (`harvester.loop`)

```
┌────────────────────────────────────────────┐
│  Итерация: harvest_full (8-12 мин)         │
│    ↓                                        │
│  Пауза: 2-5 мин (+/-10% jitter)           │
│    ↓                                        │
│  Следующая итерация...                      │
│    ↓                                        │
│  При ошибке: пауза 5 мин и продолжаем     │
│    ↓                                        │
│  Ctrl+C / SIGTERM → корректный выход       │
└────────────────────────────────────────────┘
```

Тайминги рандомизированы, чтобы не создавать детерминистический паттерн запросов. Параметры:

| Env / CLI | Default | Описание |
|-----------|---------|----------|
| `HARVEST_WORK_MIN_LOW` | 100 | Нижняя граница работы (мин) |
| `HARVEST_WORK_MIN_HIGH` | 140 | Верхняя граница |
| `HARVEST_SLEEP_MIN_LOW` | 20 | Нижняя граница паузы (мин) |
| `HARVEST_SLEEP_MIN_HIGH` | 40 | Верхняя граница |
| `HARVEST_MAX_ITERATIONS` | 0 (бесконечно) | Лимит итераций |

---

## Работа с rate limits и защитой API

### Общие подходы

1. **Пауза между запросами** — каждый адаптер делает `time.sleep()` после каждой страницы. Интервал разный: arXiv строго требует ≥3 сек, OpenAlex хватает 0.5 сек.

2. **Backoff при 429** — Semantic Scholar и CORE делают до 3 ретраев с паузой 10 сек. Если лимит исчерпан — источник молча пропускается, цикл продолжается.

3. **User-Agent** — для API-запросов используется идентификатор `corpus-harvester/1.x (email)`. OpenAlex с email попадает в «polite pool» (~10 req/s вместо ~2).

4. **Браузерные заголовки для скачивания PDF** — HTTP-клиент для загрузки PDF использует Chrome User-Agent, `Accept: application/pdf`, `Referer: google.com` и `Accept-Language`. Это повышает шансы пройти CDN-проверки на сайтах издательств.

### ChemRxiv и Cloudflare

С 2025 года chemRxiv стоит за Cloudflare bot-protection. Стандартный запрос получает 403 + HTML-челлендж. Адаптер использует браузерный User-Agent и заголовки — иногда проходит с пользовательских IP, на дата-центровых (GitHub Actions) обычно нет. При 403 источник пропускается, а chemRxiv-материалы дублируются в OpenAlex (концепт chemistry/cheminformatics).

### КиберЛенинка

OAI-PMH endpoint для метаданных обычно доступен. PDF может возвращать 403 с некоторых IP (CDN/CF). В этом случае запись пропускается.

### Unpaywall fallback

Если основной PDF-url не скачивается (403, paywall и т.п.) и в doc_id есть DOI — делается запрос к Unpaywall. Часто находится OA-копия на PMC, authors' site или институтском репозитории.

---

## GitHub Actions

Workflow `.github/workflows/harvest.yml` — запуск вручную (workflow_dispatch) или по расписанию (cron отключён).

### Как зациклили на GitHub

Ключевая идея: вместо ненадёжного cron'а (GitHub Actions известен задержками до 30+ минут и пропусками при высокой нагрузке) **runner запускает `harvester.loop`** — бесконечный цикл внутри одного workflow run.

```yaml
timeout-minutes: 350   # ~5.5 часов — один workflow run
```

Внутри runner крутится цикл:
1. `harvest_full` (~8-12 минут с budget=200)
2. Синхронизация в Google Drive (через rclone)
3. Пауза 2-5 минут с jitter
4. Повтор...

Это гарантирует непрерывный поток данных в Drive, пока runner не упрётся в `timeout-minutes`. При ошибке — пауза 5 минут и продолжение.

### Concurrency

```yaml
concurrency:
  group: harvest
  cancel-in-progress: false
```

Одновременно может работать только один harvest run. Новый запуск не отменяет текущий — встаёт в очередь.

### Секреты и переменные

| Секрет | Обязательный | Описание |
|--------|:---:|----------|
| `QDRANT_URL` | да | URL Qdrant Cloud |
| `QDRANT_API_KEY` | да | Ключ Qdrant Cloud |
| `HARVESTER_EMAIL` | рекомендуется | Email для User-Agent OpenAlex/Unpaywall |
| `RCLONE_CONFIG` | рекомендуется | Содержимое rclone.conf для Google Drive |
| `CORE_API_KEY` | нет | Ключ CORE API |
| `SEMANTIC_SCHOLAR_API_KEY` | нет | Ключ S2 (повышает лимиты) |
| `S3_BUCKET` | нет | S3-совместимое хранилище |

### Что делает workflow

```
1. Checkout репо
2. Python 3.11 + pip install -r requirements.txt
3. Установка rclone (если RCLONE_CONFIG задан)
4. Запуск harvester.loop:
   - harvest → ingest_v2 → embed_resume_v2 (цикл)
   - Результаты уезжают в Google Drive
   - Чанки пушатся в Qdrant Cloud
   - Никаких git push с данными
5. Артефакты: harvester/logs/ + state.json (30 дней)
```

---

## Кросс-источниковый дедуп

Один документ может прийти из нескольких источников (arXiv + OpenAlex + Semantic Scholar). `state.py` ведёт два списка:
- **downloaded_ids** — оригинальные doc_id (`arxiv:2304.12345`, `openalex:10.1234/...`)
- **normalized_ids** — канонические ключи для дедупа

Нормализация (`нормализовать_doc_id`):
1. arXiv DOI-алиас (`10.48550/arXiv.XXXX`) → `arxiv:XXXX`
2. arXiv id (`2304.12345v2`) → `arxiv:2304.12345` (без версии)
3. Обычный DOI → `doi:10.xxxx/yyyy` (lowercase)
4. PMC id → `pmc:pmc1234567`
5. Fallback → оригинал в lowercase

Пример: `arxiv:2304.12345v2` из arXiv и `openalex:10.48550/arXiv.2304.12345` из OpenAlex оба дадут `arxiv:2304.12345` — второй раз не скачается.

---

## Балансировка доменов

Чтобы корпус не перекосило (например, 80% IT), работает автоматическая балансировка:

1. Каждый скачанный документ классифицируется как **chem** / **it** / **other** на лету — по источнику + ключевым словам в title + abstract (без ML, чистые regex)
2. `domain_counts` в state.json отслеживает текущее распределение
3. Идеальная пропорция: 45% chem, 45% it, 10% other
4. Если домен отстаёт — его источники получают больший бюджет (мультипликатор через √ от отношения), ведущий — меньший

Каждый источник имеет ожидаемый домен для расчёта весов:

| Источник | Домен |
|----------|-------|
| arXiv, Stack Exchange, Semantic Scholar, CORE | it |
| ChemRxiv, OpenAlex, Europe PMC, КиберЛенинка | chem |

---

## Использование

### CLI-параметры `harvester.run`

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `--budget` | int | 300 | Сколько документов пытаться скачать (≈/N на источник) |
| `--year-min` | int | 2020 | Минимальный год публикации |
| `--email` | str | env `HARVESTER_EMAIL` | Email для User-Agent (нужен OpenAlex, Unpaywall) |
| `--sources` | str | все 8 | Список через запятую |
| `--time-limit-min` | int | 0 (без лимита) | Hard deadline в минутах |

### Однократный сбор

```bash
python -m harvester.run --budget 500
python -m harvester.run --budget 200 --sources arxiv,openalex
python -m harvester.run --budget 100 --year-min 2022 --time-limit-min 30
```

### End-to-end (harvest + ingest + embed)

```bash
python -m harvester.harvest_full --budget 200
```

### Бесконечный цикл

```bash
python -m harvester.loop --work-min-low 15 --work-min-high 30 --sleep-min-low 20 --sleep-min-high 40
```

### Скрипты-обёртки

```bash
# Windows:
scripts\run_harvester.bat          # однократный
scripts\run_harvester_loop.bat     # бесконечный цикл

# Linux/macOS:
scripts/run_harvester.sh
scripts/run_harvester_loop.sh
```

---

## Состояние (harvester/state.json)

Структура (v4):

```json
{
  "version": 4,
  "sources": {
    "arxiv":        { "last_index": 4200, "last_run": "2026-05-20T..." },
    "chemrxiv":     { "skip": 800, "last_run": "..." },
    "openalex":     { "cursors": { "C2780791683": "IlsxNTAw...", ... }, "last_run": "..." },
    "europepmc":    { "cursors": { "cheminformatics": "AoE/EBp...", ... }, "last_run": "..." },
    "cyberleninka": { "current_date": "2024-06-01", "last_run": "..." },
    "stackexchange": { "sites": { "chemistry": 5, "ai": 3, ... }, "last_run": "..." }
  },
  "downloaded_ids": ["arxiv:2304.12345", "openalex:10.1234/...", ...],
  "normalized_ids": ["arxiv:2304.12345", "doi:10.1234/...", ...],
  "domain_counts": { "chem": 1234, "it": 1180, "other": 86 }
}
```

Курсоры инкрементальны — каждый запуск продолжает с того места, где остановился предыдущий. При миграции со старых версий нормализованные ID строятся автоматически.

---

## Синхронизация

### Google Drive (рекомендуемый способ)

Через rclone — данные НЕ коммитятся в git. См. [GOOGLE_DRIVE.md](GOOGLE_DRIVE.md).

```bash
python -m harvester.gdrive_rclone upload
```

Структура в Drive:
```
<remote>:<base>/
├── pdf/              ← all_pdfs/*.pdf
├── docx/             ← all_pdfs/*.docx
├── txt/              ← all_pdfs/*.txt
├── meta/             ← harvested_meta/*.json
└── state.json        ← harvester/state.json
```

### S3 (альтернативный бэкап)

```bash
python -m harvester.s3_upload
```

Требует env: `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`.

---

## Формат метаданных

Файл `harvested_meta/<basename>.json`:

```json
{
  "doc_id": "arxiv:2301.12345",
  "источник": "arxiv",
  "название": "Graph Neural Networks for Molecular Property Prediction",
  "авторы": ["Smith J.", "Lee K."],
  "дата": "2023-01-15",
  "категории": ["cs.LG", "physics.chem-ph"],
  "домен": "chem",
  "abstract": "We propose a novel GNN architecture...",
  "pdf_url": "https://arxiv.org/pdf/2301.12345.pdf",
  "файл": "graph-neural-networks__arxiv-2301-12345.pdf"
}
```

---

## Расширение: добавление нового источника

1. Создать файл `harvester/sources/my_source.py`
2. Реализовать функцию `собрать(...)` → `Iterator[Документ]` или `tuple[list[Документ], cursor]`
3. Использовать dataclass `Документ` из `sources/arxiv.py`
4. Добавить в `harvester/run.py`:
   - Импорт: `from .sources import my_source`
   - Функцию `_собрать_my_source(args, состояние, клиент_pdf, бюджет)`
   - Запись в `СБОРЩИКИ`
5. Добавить имя в `ВСЕ_ИСТОЧНИКИ`
6. (Опционально) Добавить ожидаемый домен в `домены.ИСТОЧНИК_ОЖИДАЕМЫЙ_ДОМЕН`

---

## Именование файлов

Скачанные файлы получают читаемое и уникальное имя:

```
<slug-из-заголовка>__<short-doc-id>.pdf
```

Примеры:
- `graph-neural-networks-for-molecular__arxiv-2301-12345.pdf`
- `bayesian-optimization-of-chemical__doi-10-1038-s41586.pdf`

Правила:
- Кириллица → транслит (`молекул` → `molekul`)
- Спецсимволы → `-`
- Максимум 80 символов slug
- Если заголовок пустой → fallback на short-hash doc_id (12 символов SHA-1)

---

## Атомарность state.json

Запись state — через atomic rename:
```python
# 1. Пишем во временный файл
with open("state.json.tmp", "w") as f:
    json.dump(данные, f)
# 2. Атомарная замена
os.replace("state.json.tmp", "state.json")
```

Это предотвращает повреждение state при kill процесса mid-write (частая ситуация в GitHub Actions при `timeout-minutes`).

Runtime-индексы (`_downloaded_set`, `_normalized_set`) — O(1) lookup, не сериализуются в JSON. Восстанавливаются из списков при каждом `прочитать()`.
