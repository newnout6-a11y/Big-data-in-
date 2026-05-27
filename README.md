# Навигатор цифровой химии

RAG-система (Retrieval-Augmented Generation) для семантического поиска и генерации ответов по корпусу научных документов на стыке **химии и информационных технологий**. Поддерживает гибридный поиск (dense + sparse), авторазметку по таксономии, пользовательские тетради, учебные инструменты и автоматический сбор документов из открытых источников.

---

## Возможности

- **RAG Q&A** — задаёшь вопрос на русском/английском, получаешь ответ с цитатами `[N]`, LaTeX-формулами и изображениями из PDF
- **Гибридный поиск** — dense-эмбеддинги (multilingual-e5-base, 768d) + sparse BM25 с RRF-фьюжном
- **Cross-encoder reranker** — `BAAI/bge-reranker-v2-m3` для финальной переранжировки top-K
- **Пользовательские тетради** — загрузка PDF/DOCX/PPTX/TXT, индексация с OCR, поиск внутри
- **Учебные инструменты** — конспекты, флеш-карточки (Anki APKG, TSV), квизы, графы связей
- **Автоматический харвестер** — сбор из arXiv, OpenAlex, Europe PMC, Semantic Scholar, ChemRxiv, КиберЛенинка, Stack Exchange, CORE
- **Авторазметка** — классификация чанков по таксономии (домен/субдомен) без LLM-вызовов
- **Фильтр качества** — автоотбраковка повреждённых/пустых PDF до ингеста
- **Визуальная обработка** — OCR тетрадей (RapidOCR + опционально Groq Vision)
- **Публичный доступ** — SSH-туннель через localhost.run (работает из РФ без VPN) + QR-код

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI (ui/app.py)                  │
│   Вкладки: Поиск │ Мои документы │ Учёба │ Кейсы │ Архит.  │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐
│  Groq LLM    │  │  Qdrant (hybrid) │  │ sentence-transf. │
│  llama-3.3   │  │  dense + sparse  │  │ multilingual-e5  │
│  70b / 8b    │  │  binary quant.   │  │ + bge-reranker   │
└──────────────┘  └─────────────────┘  └──────────────────┘
                            ▲
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐
│  ingest_v2   │  │ embed_resume_v2 │  │    harvester     │
│  PDF→chunks  │  │ chunks→Qdrant   │  │  8 источников    │
└──────────────┘  └─────────────────┘  └──────────────────┘
```

| Компонент | Технология |
|-----------|-----------|
| Интерфейс | Streamlit (wide layout, тёмная тема, кастомный CSS) |
| Эмбеддинги | `intfloat/multilingual-e5-base` — 768d, cosine |
| Sparse | BM25 с серверным IDF (FastEmbed `Qdrant/bm25`) |
| Reranker | `BAAI/bge-reranker-v2-m3` — cross-encoder, CPU |
| Векторная БД | Qdrant (локальный или Cloud), binary quantization |
| LLM | Groq API: `llama-3.3-70b-versatile` + fallback `llama-3.1-8b-instant` |
| OCR | RapidOCR (CPU, бесплатно) + EasyOCR + Groq Vision (опц.) |
| Публичный доступ | SSH-туннель `localhost.run` + QR-код |

---

## Структура проекта

```
.
├── core/                       # Бизнес-логика
│   ├── cases.py                # 15 тематических кейсов (keyword matching)
│   ├── hybrid_search.py        # Dense + BM25 с RRF-fusion (lazy init, thread-safe)
│   ├── notebooks.py            # Пользовательские тетради (загрузка, индексация, поиск)
│   ├── reranker.py             # Cross-encoder reranker (env RERANKER_MODEL)
│   ├── study_tools.py          # Конспекты, карточки, квизы, графы, экспорт
│   ├── taxonomy.py             # Таксономия: 3 домена, ~20 субдоменов
│   ├── визуальная_обработка.py # OCR страниц PDF (Tier 0/1/2)
│   ├── извлечение_картинок.py  # Извлечение и фильтрация изображений из PDF
│   ├── классификатор.py        # Эмбеддинговый классификатор + scope-guard
│   └── фильтр_качества.py     # Фильтр низкокачественных PDF (3 критерия)
│
├── pipeline/                   # Пайплайн данных
│   ├── ingest_v2.py            # PDF/DOCX/TXT → chunks_v2.jsonl (с метаданными)
│   ├── embed_resume_v2.py      # chunks_v2.jsonl → Qdrant (dense + sparse)
│   ├── миграция_в_v2.py        # Миграция старой коллекции → knowledge
│   └── пересобрать_гибрид.py   # knowledge → knowledge_hybrid (named vectors)
│
├── ui/                         # Интерфейс
│   ├── app.py                  # Главное Streamlit-приложение (RAG + все вкладки)
│   └── дизайн.py               # CSS-стили, HTML-шаблоны, рендереры
│
├── scripts/                    # Утилиты и скрипты запуска
│   ├── запуск.py               # Streamlit + SSH-туннель + QR
│   ├── download_snapshot.py    # Скачать snapshot из Qdrant Cloud
│   ├── import_snapshot.py      # Импорт JSONL в локальный Qdrant (--recreate, --limit N)
│   ├── optimize_collections.py # On_disk + binary quantization для экономии RAM
│   ├── inspect_page.py         # Диагностика: что Qdrant знает про страницу
│   ├── run_harvester.bat/.sh   # Однократный запуск харвестера
│   └── run_harvester_loop.bat/.sh  # Бесконечный цикл харвестера
│
├── harvester/                  # Автосбор научных документов
│   ├── run.py                  # Оркестратор (8 источников)
│   ├── harvest_full.py         # End-to-end: harvest → ingest → embed
│   ├── loop.py                 # Бесконечный цикл с рандомными паузами
│   ├── state.py                # Состояние + кросс-источниковый дедуп
│   ├── домены.py               # Классификатор домена для балансировки
│   ├── gdrive_rclone.py        # Синхронизация в Google Drive через rclone
│   ├── s3_upload.py            # Синхронизация в S3-совместимое хранилище
│   └── sources/                # Адаптеры источников
│       ├── arxiv.py, chemrxiv.py, openalex.py, europepmc.py,
│       ├── cyberleninka.py, stackexchange.py, semantic_scholar.py,
│       ├── core_api.py, unpaywall.py
│       └── ...
│
├── tests/                      # Pytest-тесты (~20 файлов)
├── .github/workflows/          # CI: harvest, embed-now, vectorize-existing, verify-qdrant
├── документация/               # Подробная документация по подсистемам
│
├── chunks_v2.jsonl               # Чанки с метаданными (основной файл данных)
├── knowledge_hybrid_export.jsonl # Готовые векторы из Qdrant Cloud (~6 GB)
├── all_pdfs/                     # Сырые документы (не в git)
├── harvested_meta/               # Метаданные собранных документов (JSON)
├── extracted_images/             # Извлечённые изображения из PDF
├── qdrant_db/                    # Локальное хранилище Qdrant (embedded mode)
├── requirements.txt              # Python-зависимости
├── conftest.py                   # Pytest: настройка sys.path + gасим TF
├── sitecustomize.py              # Автонастройка путей + gасим TF при старте Python
└── запуск.py                     # Шорткат → scripts/запуск.py
```

---

## Быстрый старт

### 1. Установка зависимостей

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Настройка `.env`

```bash
cp .env.example .env
```

Заполнить ключи:

```env
GROQ_API_KEY=gsk_ваш_ключ
GROQ_API_KEY_2=gsk_резервный_ключ          # опционально
```

Получить ключ: [console.groq.com](https://console.groq.com/) → API Keys → Create.

### 3. Подготовка данных

**Вариант A — с нуля (свои документы):**

```bash
# Положить PDF/DOCX/TXT в all_pdfs/
python pipeline/ingest_v2.py        # → chunks_v2.jsonl
python pipeline/embed_resume_v2.py  # → Qdrant (локальный)
```

**Вариант B — импорт готового snapshot из Qdrant Cloud:**

```bash
# В .env добавить QDRANT_URL и QDRANT_API_KEY
python scripts/download_snapshot.py --mode jsonl
python scripts/import_snapshot.py                    # все векторы
python scripts/import_snapshot.py --limit 40000      # только 40k (если RAM мало)
python scripts/import_snapshot.py --recreate --limit 40000  # снести и залить 40k
```

Векторы не пересчитываются — берутся готовые из JSONL. Идемпотентный: повторный запуск пропускает уже загруженные точки.

### 4. Запуск

```bash
# Только локально:
streamlit run ui/app.py --server.port 8501

# С публичной ссылкой + QR (для демонстрации):
python запуск.py
```

---

## Пайплайн данных

```
all_pdfs/ ──► ingest_v2.py ──► chunks_v2.jsonl ──► embed_resume_v2.py ──► Qdrant
   │              │                                        │
   │         (классификация,                        (dense e5 768d +
   │          дедупликация,                          sparse BM25,
   │          извлечение картинок,                   binary quantization)
   │          фильтр качества)
   │
   └── harvester/run.py (автосбор из 8 источников)
```

### ingest_v2.py

Извлекает текст из PDF (PyMuPDF + fallback PyPDF), DOCX, TXT. Разбивает на чанки по 800 символов с перекрытием 100. Для каждого чанка:
- Вычисляет `text_hash` (SHA-1) для дедупликации
- Классифицирует домен/субдомен через эмбеддинговый классификатор
- Определяет язык (ru/en/other)
- Извлекает изображения со страницы + привязывает подписи
- Сохраняет метаданные из `harvested_meta/` (DOI, авторы, год, источник)

```bash
python pipeline/ingest_v2.py           # инкрементально (только новые файлы)
python pipeline/ingest_v2.py --full    # перезаписать chunks_v2.jsonl с нуля
```

### embed_resume_v2.py

Векторизует чанки в коллекцию `knowledge_hybrid`:
- **Dense**: `intfloat/multilingual-e5-base`, 768d, cosine, on_disk
- **Sparse**: BM25 с серверным IDF (`Qdrant/bm25`), on_disk
- **Binary quantization**: 32x экономия RAM (recall -2-5%, reranker компенсирует)
- **Идемпотентность**: UUIDv5 от text_hash — перезапуск безопасен

```bash
python pipeline/embed_resume_v2.py
```

Поддерживает как локальный Qdrant (`qdrant_db/`), так и удалённый (через `QDRANT_URL` + `QDRANT_API_KEY`).

---

## Харвестер

Автоматический сбор научных документов из 8 открытых источников (+ Unpaywall как fallback):

| Источник | API | Rate limit | Что берём |
|----------|-----|------------|-----------|
| arXiv | Atom XML | 3 сек/запрос | PDF, ~14 категорий (cs.LG, physics.chem-ph, cond-mat.mtrl-sci, q-bio) |
| OpenAlex | REST | 0.5 сек | PDF, 19 концептов (cheminformatics, ML, chemistry, materials...) |
| Europe PMC | REST | 0.5 сек | PDF, ~80 тематических запросов (DFT, CRISPR, MOF...) |
| Semantic Scholar | Graph API | 1 сек, backoff при 429 | PDF, 40+ запросов, фильтр `openAccessPdf` |
| ChemRxiv | JSON API | 1 сек, CF-protection | PDF, препринты по химии (при 403 — fallback через OpenAlex) |
| КиберЛенинка | OAI-PMH | 0.5 сек | PDF, русскоязычные статьи (стем-фильтр по scope) |
| Stack Exchange | REST | 0.5 сек + backoff | TXT (Q+A), 13 сайтов: chemistry, ai, stackoverflow, math... |
| CORE | REST v3 | 6.5 сек (free: 10 req/мин) | PDF, 130M+ OA (нужен бесплатный ключ) |
| Unpaywall | REST | ~100K/день | Вспомогательный: OA-копия по DOI при провале скачивания |

```bash
# Однократный запуск:
python -m harvester.run --budget 500

# End-to-end (harvest + ingest + embed):
python -m harvester.harvest_full --budget 200

# Бесконечный цикл (с рандомными паузами):
python -m harvester.loop --work-min-low 15 --work-min-high 30 --sleep-min-low 20 --sleep-min-high 40
```

Особенности:
- **Бесконечный цикл** — `harvester.loop` крутит harvest→ingest→embed с рандомными паузами (jitter ±10%); при ошибке — пауза 5 мин и продолжение
- **Кросс-источниковый дедуп** — нормализация DOI/arxiv-id, один документ из разных источников скачивается один раз
- **Балансировка доменов** — автоклассификация chem/it/other по ключевым словам, идеальная пропорция 45/45/10, отстающий домен получает больший бюджет
- **Rate limit handling** — индивидуальные паузы на источник; 429 → exponential backoff; браузерные заголовки для скачивания PDF
- **Unpaywall fallback** — если основной PDF-url недоступен (paywall, 403), ищет OA-копию через Unpaywall по DOI
- **Google Drive sync** — через rclone, данные НЕ коммитятся в git
- **S3 backup** — опциональная синхронизация в S3-совместимое хранилище

Подробнее: [`документация/HARVESTER.md`](документация/HARVESTER.md)

---

## CI/CD (GitHub Actions)

| Workflow | Назначение |
|----------|-----------|
| `harvest.yml` | Сбор + ingest + embed в бесконечном цикле (до 5.5 часов) |
| `embed-now.yml` | Одноразовый эмбед chunks_v2.jsonl → Qdrant Cloud |
| `vectorize-existing.yml` | Массовая векторизация существующих чанков |
| `verify-qdrant.yml` | Проверка состояния коллекции в Qdrant Cloud |

**harvest.yml** — ключевой workflow. Вместо ненадёжного cron (задержки до 30+ мин у GitHub Actions) runner запускает `harvester.loop` — бесконечный цикл внутри одного run (`timeout-minutes: 350`). Каждая итерация: harvest → ingest_v2 → embed_resume_v2 → sync в Google Drive. Concurrency: один run, без cancel-in-progress.

Секреты: `QDRANT_URL`, `QDRANT_API_KEY`, `HARVESTER_EMAIL`, `RCLONE_CONFIG`, `GDRIVE_BASE`.

---

## Переменные окружения

| Переменная | Обязательная | Описание |
|-----------|:---:|----------|
| `GROQ_API_KEY` | да | Основной ключ Groq для LLM |
| `GROQ_API_KEY_2` | нет | Резервный ключ (авто-fallback при 429) |
| `QDRANT_URL` | нет | URL Qdrant Cloud (без него — локальная БД) |
| `QDRANT_API_KEY` | нет | API-ключ Qdrant Cloud |
| `HARVESTER_EMAIL` | нет | Email для User-Agent (OpenAlex, Unpaywall) |
| `GDRIVE_REMOTE` | нет | Имя rclone remote для Google Drive |
| `GDRIVE_BASE` | нет | Корневая папка в Drive (default: `big-data`) |
| `CORE_API_KEY` | нет | Ключ CORE API |
| `S3_ENDPOINT_URL` | нет | URL S3-совместимого хранилища |
| `S3_BUCKET` | нет | Бакет S3 |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | нет | Креды S3 |

---

## Устойчивость к лимитам

- **Несколько ключей Groq** — автоматический fallback при 429 Rate Limit
- **Откат модели** — с `llama-3.3-70b` на `llama-3.1-8b-instant` при исчерпании квоты
- **Идемпотентный embed** — перезапуск после сбоя продолжает с того же места
- **Инкрементальный ingest** — обрабатывает только новые файлы в `all_pdfs/`

---

## Тестирование

```bash
# Все тесты:
pytest tests/ -v

# Конкретный модуль:
pytest tests/test_гибрид.py -v
pytest tests/test_классификатор.py -v
```

Тесты покрывают: гибридный поиск, классификатор, визуальную обработку, экспорт карточек, OCR, балансировку доменов, кросс-источниковый дедуп, harvester loop, Google Drive sync и др.

---

## Документация

Подробная документация по подсистемам — в папке [`документация/`](документация/):

| Файл | Тема |
|------|------|
| [АРХИТЕКТУРА.md](документация/АРХИТЕКТУРА.md) | Обзор архитектуры и потоков данных |
| [ЛОКАЛЬНЫЙ_ЗАПУСК.md](документация/ЛОКАЛЬНЫЙ_ЗАПУСК.md) | Полная инструкция локального запуска |
| [HYBRID_SEARCH.md](документация/HYBRID_SEARCH.md) | Гибридный поиск: dense + sparse + RRF |
| [HARVESTER.md](документация/HARVESTER.md) | Харвестер: источники, настройка, CI |
| [GOOGLE_DRIVE.md](документация/GOOGLE_DRIVE.md) | Синхронизация через rclone |
| [QDRANT_CLOUD_SETUP.md](документация/QDRANT_CLOUD_SETUP.md) | Настройка Qdrant Cloud |
| [ВИЗУАЛЬНАЯ_ОБРАБОТКА.md](документация/ВИЗУАЛЬНАЯ_ОБРАБОТКА.md) | OCR и обработка изображений |
| [УЧЕБНЫЕ_ИНСТРУМЕНТЫ.md](документация/УЧЕБНЫЕ_ИНСТРУМЕНТЫ.md) | Конспекты, карточки, квизы, графы |

---

## Лицензия

Проект создан в рамках учебной/исследовательской работы.
