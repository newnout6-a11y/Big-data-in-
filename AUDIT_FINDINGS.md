# Аудит кодовой базы «Навигатор цифровой химии»

Стек: Python 3.12 + Streamlit + Qdrant + RAG. Проект на Python, не TS, поэтому
вместо `tsc/vitest` использую `pytest` (он уже стоит, есть `conftest.py`).

Проверено: `core/`, `pipeline/`, `harvester/` (включая sources), `ui/`, `scripts/`,
все тесты, `.github/workflows/*`, deprecated-модули.

Baseline: **158 проходят** в `pytest tests/ --ignore=test_классификатор.py
--ignore=test_гибрид.py` (~34 сек). Двадцать один тест с реальной моделью
e5-base/BM25 пропущен из-за длительного скачивания (это не наш баг).

## Карта модулей

```
core/
  cases.py                 — 15 кейсов (keyword matching, Map[str -> List[str]])
  hybrid_search.py         — RRF-фьюжн + lazy BM25 (FastEmbed)
  reranker.py              — CrossEncoder lazy-load (BAAI/bge-reranker-v2-m3)
  taxonomy.py              — 3 домена + ~20 субдоменов с прототипами
  визуальная_обработка.py — Tier 0/1/2 OCR PDF-страниц + кэш + бюджет Groq Vision
  извлечение_картинок.py  — фильтры декоративных, привязка подписей, easyocr
  классификатор.py         — эмбеддинговый scope-guard + классификатор
  фильтр_качества.py      — 3 критерия отбраковки PDF до ingest
  notebooks.py             — пользовательские тетради (CRUD, поиск, OCR)
  study_tools.py           — конспекты/карточки/.docx-/.md-/.apkg-экспорты

pipeline/
  ingest_v2.py             — PDF/DOCX/TXT → chunks_v2.jsonl с metadata
  embed_resume_v2.py       — chunks_v2.jsonl → Qdrant (dense+sparse, idem по text_hash)
  миграция_в_v2.py         — knowledge → knowledge_hybrid (legacy)
  пересобрать_гибрид.py    — knowledge → knowledge_hybrid (named vectors)
  ingest.py / embed_resume.py / ingest_доп.py — DEPRECATED заглушки

harvester/
  run.py                   — оркестратор 8 источников + dedup + balance + Unpaywall fallback
  harvest_full.py          — end-to-end (harvest + ingest + embed) для CI
  loop.py                  — бесконечный цикл с jitter (для CI 5.5h timeout)
  state.py                 — курсоры + кросс-источниковый дедуп (O(1) сеты)
  домены.py                — балансировщик chem/it/other по ключевым словам
  gdrive_rclone.py         — sync в Google Drive (push/pull-state)
  s3_upload.py             — sync в S3 (опционально)
  sources/                 — 8 адаптеров (arxiv, openalex, europepmc, ...)

ui/
  app.py                   — главное Streamlit-приложение (5 вкладок, 3150 строк)
  дизайн.py                — CSS + HTML-рендереры

scripts/                   — запуск.py, snapshot tools, build_ui_db_*, инспектор, демо
.github/workflows/         — harvest, embed-now, vectorize-existing, verify-qdrant
```

---

## Находки

### C1. [FIXED] [HIGH] `notebooks.ingest_uploaded_files` — утечка файлов на диск при ошибке ingest

**Где:** `core/notebooks.py:ingest_uploaded_files` (~ строки 175-285).

**Суть:** Файл `target.write_bytes(data)` сохраняется на диск **до** запуска
обработки PDF и индексации. Если внутри `try` где-то падает (битый PDF,
OOM при OCR, ошибка Qdrant, обрыв сети) — `except: continue` записывает
ошибку в `summary["errors"]`, но **сам файл остаётся** в
`user_documents/<user>/<nb>/files/`. В `notebook["files"]` он не попадает,
поэтому нигде не отображается, не индексирован, не доступен — чистый мусор.

При повторной попытке загрузки этого же файла ingest пройдёт нормально, но
старая копия останется навсегда. Накапливается со временем.

**Severity:** MEDIUM — функционально работает, утечка диска медленная (один
сбойный upload = один сиротский файл). Но за месяцы превращается в гигабайты
неиспользуемых PDF на хостинге.

**Фикс:** в `except` — удалить `target` (если есть). Картинки в
`extracted_images/<file_hash>/` и кэш `visual_index/pages/` оставляем —
они валидны и переиспользуются при повторном upload.

**Тест:** мокаем `upsert_chunks` чтобы бросал — проверяем `target.exists() == False`.

[FIXED] см. `tests/test_аудит_утечки.py::test_C1_target_удаляется_при_ошибке_ingest`

---

### C2. [FIXED] [MEDIUM] Мёртвая фича: фильтр «по кейсу» игнорируется в новой схеме (knowledge_hybrid)

**Где:** `ui/app.py:найти_похожие` (~ строка 491-498), вкладка «Поиск».

**Суть:** В UI пользователь может выбрать кейс из 16 в селекторе «Фильтр по
кейсу». Селектор активен в режимах `corpus` и `mixed`. Но в `найти_похожие`:

```python
if новая_схема:
    фильтр = _построить_фильтр(
        выбранный_кейс=None,  # case в новой схеме менее приоритетен
        домен=домен, субдомен=субдомен, ...
    )
else:
    фильтр = _построить_фильтр(выбранный_кейс=выбранный_кейс)
```

Под комментарием «менее приоритетен» — кейс просто **не передаётся** в
фильтр. При этом `pipeline/ingest_v2.py` пишет поле `case` в payload **каждого**
чанка новой схемы (строка `"case": кейс`), причём специально «для
backward-compat». Получается классический случай: UI-тумблер ничего не
делает, пользователь думает что фильтр работает, а выдача ровно та же.

Учитывая что кейсы в новой схеме залиты, проще всего — снова применять фильтр.
Если у документа `case` нет (старые), фильтр Match не пропустит — но это
проблема только при `case != "все"`, что и значит «выбран осознанно».

**Severity:** MEDIUM. Фича декларирована и видна в UI, факт молчаливо не работает.

**Фикс:** убрать `выбранный_кейс=None` для новой схемы. Поле `case` есть в
индексе (если не было — добавим payload-индекс при создании коллекции, но
проверка показала что в `embed_resume_v2.py` индекса на `case` действительно
нет — поэтому фильтрация будет full-scan). Поскольку коллекции маленькие,
full-scan за фильтр приемлем; при желании можно добавить индекс отдельно.

**Тест:** unit на `_построить_фильтр` — что при `выбор_кейса="оптимизация_реакции"`
он порождает `FieldCondition(key="case", match=MatchValue("оптимизация_реакции"))`.

[FIXED] см. `tests/test_аудит_утечки.py::test_C2_фильтр_по_кейсу_передаётся_в_новой_схеме`

---

### C3. [FIXED] [MEDIUM] `_загрузить_qdrant_cached` — утечка локальных Qdrant-клиентов при смене базы

**Где:** `ui/app.py:_загрузить_qdrant_cached` (`@st.cache_resource`).

**Суть:** Декоратор `st.cache_resource` кеширует по аргументам (url, api_key,
путь). При смене UI-выбора базы (50k → 100k → полная) каждый клиент
**остаётся** в кеше, держит файловый lock на `qdrant_db/` и память. Поскольку
Qdrant local mode не разрешает два клиента на одну папку — при смене обратно
получим RuntimeError "already accessed by another instance". Видно даже в
`scripts/inspect_page.py`, там специально написан workaround «копировать БД
во временную папку, если папка занята».

В UI же это проявляется как:
- пик памяти при переключениях баз (4 клиента 50k+100k+150k+200k)
- невозможность запустить второй процесс инспекции, пока UI открыт

**Severity:** MEDIUM. Не падает фатально для типичного use case (один
человек использует одну базу), но при переключении баз накапливаются
лишние ресурсы.

**Фикс:** при изменении выбранной базы (через `st.session_state["qdrant_local_path"]`)
вызывать `_загрузить_qdrant_cached.clear()` — это освободит все кешированные
клиенты, новый создастся ленивно.

**Тест:** проверить, что после `clear()` повторный вызов с другим путём не
бросает «already accessed».

[FIXED] см. `tests/test_аудит_утечки.py::test_C3_qdrant_кэш_очищается_при_смене_базы`

---

### C4. [LOW] `_картинка_содержательная` — неограниченный кэш размеров картинок

**Где:** `ui/app.py:_КЭШ_РАЗМЕРОВ` (модуль-level dict).

**Суть:** При каждом запросе UI вызывает `_картинка_содержательная(путь)` для
всех картинок всех фрагментов. Размер картинки кешируется по абсолютному
пути в module-level dict без TTL/LRU. На корпусе с 10k+ извлечёнными
картинками за длительную сессию словарь распухнет на ~500 KB-2 MB
(сама запись — пара tuple). Не катастрофа, но утечка.

Также cache не invalidates по mtime — если PDF переиндексирован, картинки
перезаписаны, размер тот же — всё OK; если другой формат — кеш врёт. Но
такой кейс почти невозможен (extracted_images пишут идемпотентно).

**Severity:** LOW. Реально не мешает, фиксить только если будут проблемы.

**Defer.**

---

### C5. [LOW] `_highlighted_pdf` — накопление PDF с подсветкой

**Где:** `core/notebooks.py:_highlighted_pdf` пишет в `user_documents/highlights/`.

**Суть:** Каждая уникальная пара (документ, страница, цитата[:1200]) даёт новый
PDF в `highlights/`. После 100+ запросов в одну тетрадь там сотни мелких PDF
по 1-3 МБ. Никогда не очищаются.

**Severity:** LOW. Кэш переиспользуется (по digest), но за месяцы скапливается.

**Defer.** Можно добавить cron-чистку «старше 30 дней» отдельной задачей.

---

### C6. [LOW] `notebooks.переиндексировать_файл_с_ocr` — payload без visual_meta

**Где:** `core/notebooks.py:переиндексировать_файл_с_ocr`.

**Суть:** При переиндексации с OCR функция зовёт `_extract_pdf(target, use_ocr=True)`,
который возвращает `pages` без поля `visual_meta_by_page`. Затем `build_chunks`
с `visual_meta_by_page=None` (default) — и в payload каждого чанка
`tier_used=0`, `has_ocr=False`, `page_hash=""`, `image_path=""`.

При этом OCR реально применяется к встроенным картинкам (через
`extract_picture_caption` в `_extract_pdf` → `извк.извлечь_картинки_страницы(use_ocr=True)`).
Caption-текст попадает в payload через `images[].caption`, и поиск его видит.

То есть **функционально OK** — поиск работает, captions есть. Только
metadata-поля (tier_used и has_ocr) врут — UI «карточка файла» покажет «OCR не
применялся», хотя реально применялся. Минорная косметика.

**Severity:** LOW. **Defer.**

---

### C7. [LOW] `_split_text` отбрасывает чанки 50-80 символов

**Где:** `core/notebooks.py:_split_text` (`if len(piece) > 80`).

**Суть:** В `build_chunks` решение оставлять страницу принимается по
`len(text) >= 50 OR has_images`. Внутри `_split_text` — порог 80. То есть
страница с текстом 60 символов и без картинок не выкидывается на верхнем
уровне, но `_split_text` возвращает `[]`, и единственный fallback —
плейсхолдер «[Страница N: изображение]» (только если есть картинки).
В итоге короткие текстовые страницы (60-80 символов) без картинок
проигрывают. Окей, это редко. Defer.

**Severity:** LOW. **Defer.**

---

### C8. [LOW] `pipeline/ingest_v2.извлечь_pdf` — отбрасывает страницы с текстом < 50

**Где:** `pipeline/ingest_v2.py:_извлечь_pdf_pymupdf` — `if текст and len(текст.strip()) > 50`.

**Суть:** Для harvester pipeline страницы с пустым/коротким текстом
выкидываются ДО фильтра качества. Это значит фильтр качества видит
только содержательные страницы. Критерий «мало непустых страниц
(figures-only)» в результате почти не срабатывает — все страницы и так
непустые. Но критерий «мало слов» работает, и он спасает.

**Severity:** LOW (баг почти беззубый, тесты на figures-only фильтр пройдут
если страницы с пустым текстом эмулировать). **Defer.**

---

## Что попало в [Defer]

C4-C8 не критичны, не мешают пользователю, либо требуют существенной
переработки policy decisions. Зафиксированы для будущих PR.

---

### C9. [FIXED] [HIGH] `harvest_full.py` запускает несуществующие скрипты — весь CI-pipeline молча не работает

**Где:** `harvester/harvest_full.py:main` — шаги `ingest` и `embed`.

**Суть:** После реструктуризации файлов `ingest_v2.py` и `embed_resume_v2.py`
переехали из корня в `pipeline/`. В корне их физически нет (deprecated-стабы
с тем же именем убраны). Но `harvest_full.py` всё ещё зовёт:

```python
команда_ingest = [sys.executable, "ingest_v2.py"]
команда_embed = [sys.executable, "embed_resume_v2.py"]
```

Запускается subprocess'ом с `cwd=_БАЗА` (корень репо). Python не находит
файл, бросает `FileNotFoundError: [Errno 2] No such file or directory:
'ingest_v2.py'`. **Но**: `_запустить` ловит исключение, пишет в лог и
возвращает rc=1. `harvest_full.main` запоминает return_code в отчёте, **но
сам всегда возвращает 0**. `harvester.loop` смотрит на rc subprocess'а
`harvest_full` (всегда 0) — считает итерацию успешной и идёт спать.

Итог: **в CI пайплайн harvest_full.harvest_full**
(`.github/workflows/harvest.yml`, шаг «Run harvester.loop»):
- harvest качает PDF — работает (через `python -m harvester.run`, корректный путь);
- ingest **молча падает** — на каждой итерации;
- embed **молча падает** — на каждой итерации;
- Drive push в конце пушит сами PDF, но `chunks_v2.jsonl` в Drive не пополняется.

То есть workflow `harvest.yml` (бесконечный цикл harvest+ingest+embed) уже
несколько коммитов как полностью сломан в части ingest/embed, и никто этого
не заметил, потому что CI не валится. Только `vectorize-existing.yml` и
`embed-now.yml` правильно зовут `pipeline/ingest_v2.py` и работают.

**Severity:** HIGH. Главный CI-workflow проекта молча не делает половину
своей работы. Ингест и эмбеддинг в Qdrant Cloud из cron'а не идут, и видимо
давно. Это «фича есть, но код который её применяет никогда не вызывается»
ровно того класса, про который ты предупреждал.

**Фикс:** заменить `"ingest_v2.py"` → `os.path.join("pipeline", "ingest_v2.py")`.
И аналогично для embed. Cwd=`_БАЗА` (корень репо), pipeline/ относится
от него — стабильно работает на Windows и Linux runner'е GitHub Actions.

**Тест:** `tests/test_harvest_full_paths.py` мокает `_запустить` и проверяет
что в команды передан именно `pipeline/<скрипт>`. Verified: тест ловит баг
если откатить фикс.

[FIXED]

---

## Что починим в этом аудите

- **C1** — утечка файлов при ошибке ingest_uploaded_files
- **C2** — мёртвая фича: фильтр по кейсу в новой схеме
- **C3** — утечка Qdrant-клиентов при смене UI-базы
- **C9** — CI-pipeline harvest_full молча не работает (ingest+embed скрипты не находятся)
