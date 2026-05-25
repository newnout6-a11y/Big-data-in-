# Харвестер — автосбор научных документов

## Обзор

Модуль `harvester/` автоматически собирает научные документы (PDF и тексты) из 8 открытых источников, сохраняет их в `all_pdfs/` с метаданными в `harvested_meta/`, и опционально синхронизирует в Google Drive или S3.

---

## Источники

| Источник | Модуль | API | Формат | Примечания |
|----------|--------|-----|--------|-----------|
| arXiv | `sources/arxiv.py` | Atom API | PDF | cs.LG, physics.chem-ph, cond-mat.mtrl-sci, q-bio |
| OpenAlex | `sources/openalex.py` | REST | PDF | Concepts: cheminformatics, ML, chemistry, materials, CS |
| Europe PMC | `sources/europepmc.py` | REST | PDF | Полные тексты медбио + химия, фильтр OA + год |
| Semantic Scholar | `sources/semantic_scholar.py` | Graph API | PDF | 200M+ публикаций, OA PDF status |
| ChemRxiv | `sources/chemrxiv.py` | JSON API | PDF | За Cloudflare, может блокировать с CI-IP |
| КиберЛенинка | `sources/cyberleninka.py` | OAI-PMH | PDF | Русскоязычные статьи, фильтр по предметам |
| Stack Exchange | `sources/stackexchange.py` | REST | TXT | Q+A как синтетические документы |
| CORE | `sources/core_api.py` | REST v3 | PDF | 130M+ OA, нужен CORE_API_KEY |
| Unpaywall | `sources/unpaywall.py` | REST | — | Вспомогательный: ищет OA-копию по DOI |

---

## Использование

### Однократный сбор документов

```bash
python -m harvester.run --budget 500
python -m harvester.run --budget 200 --sources arxiv,openalex
python -m harvester.run --budget 100 --year-min 2022
```

Параметры:
- `--budget N` — сколько документов попытаться скачать (суммарно)
- `--sources` — через запятую; по умолчанию все 8
- `--year-min` — минимальный год публикации (default: 2020)
- `--email` — для User-Agent OpenAlex/Unpaywall (или env `HARVESTER_EMAIL`)

### End-to-end: harvest + ingest + embed

```bash
python -m harvester.harvest_full --budget 200
```

Делает в одной команде:
1. `harvester.run` — собирает PDF/тексты
2. `ingest_v2` — обрабатывает только новые файлы
3. `embed_resume_v2` — догружает чанки в Qdrant

Пишет отчёт в `harvester/logs/run_<timestamp>.json`.

### Бесконечный цикл

```bash
python -m harvester.loop --work-min 15 30 --sleep-min 20 40
```

Параметры:
- `--work-min MIN MAX` — длительность одной итерации (минуты)
- `--sleep-min MIN MAX` — пауза между итерациями (с jitter ±10%)
- `--s3` — синхронизировать в S3 после каждой итерации

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

## Состояние (harvester/state.py)

Файл `harvester/state.json` хранит:
- **Курсоры** по каждому источнику (offset, page, cursor-token, date)
- **downloaded_ids** — список doc_id уже скачанных документов
- **normalized_ids** — нормализованные ключи для кросс-источникового дедупа
- **domain_counts** — счётчик документов по доменам (chem/it/other)

### Кросс-источниковый дедуп

Один документ может быть найден несколькими источниками (arXiv + OpenAlex + Semantic Scholar). Дедуп по нормализованному ID:
- DOI: `10.xxxx/yyyy` → lower, без trailing punctuation
- arXiv: `arxiv:2301.12345v2` → `arxiv:2301.12345` (без версии)

---

## Балансировка доменов (harvester/домены.py)

Чтобы корпус не перекосило в сторону IT или химии:
1. Каждый документ классифицируется как `chem` / `it` / `other` (по источнику + заголовку + abstract)
2. `domain_counts` в state.json отслеживает баланс
3. Харвестер может регулировать бюджет: давать больше квоты отстающему домену

---

## Синхронизация

### Google Drive (рекомендуемый способ)

Через rclone — без коммитов данных в git. См. [GOOGLE_DRIVE.md](GOOGLE_DRIVE.md).

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

## GitHub Actions (CI)

Workflow `harvest.yml` (запуск вручную через workflow_dispatch):

1. Устанавливает Python + зависимости
2. Восстанавливает state.json из Google Drive (если есть)
3. Запускает `harvest_full` с заданным бюджетом
4. Синхронизирует результат обратно в Drive
5. Загружает чанки в Qdrant Cloud

Секреты:
- `QDRANT_URL`, `QDRANT_API_KEY` — обязательные
- `HARVESTER_EMAIL` — для OpenAlex/Unpaywall
- `RCLONE_CONFIG` — содержимое rclone.conf (для Drive)
- `GDRIVE_BASE` — корневая папка в Drive
- `CORE_API_KEY` — для источника CORE (опционально)

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
2. Реализовать функцию `собрать(...)` → `Iterator[Документ]`
3. Использовать dataclass `Документ` из `sources/arxiv.py`
4. Добавить в `harvester/run.py`:
   - Импорт: `from .sources import my_source`
   - Функцию `_собрать_my_source(args, состояние, клиент_pdf, бюджет)`
   - Запись в `СБОРЩИКИ`
5. Добавить имя в `ВСЕ_ИСТОЧНИКИ`
