# Бесконечный харвестер

Есть два режима — **локальный** (рекомендуется, без коммитов в репо) и
GitHub Actions (как было раньше, но без push'ей в main).

## Локальный режим — `harvester.loop` + Google Drive

Парсер крутится у тебя на машине бесконечно, спарсенные PDF/метаданные
и `state.json` уезжают прямо в твою папку на Google Drive. Никаких
git push'ей — только парсинг и отправка.

См. подробный гайд по настройке: [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md).

После настройки:

```bash
python -m harvester.loop --budget 500
```

`harvester.loop` перезапускается на ошибках, спит между итерациями
рандом из `[20..40]` минут с jitter ±10%, после каждой итерации
автоматически заливает свежак в Drive.

## GitHub Actions

Воркфлоу `.github/workflows/harvest.yml` запускается **по запросу**
(`workflow_dispatch`) и за один прогон:

1. Скачивает свежие документы из выбранных источников в `all_pdfs/`
2. Парсит/чанкит/авторазмечает их через `ingest_v2.py` → `chunks_v2.jsonl`
3. Догружает чанки в **удалённый Qdrant** (Qdrant Cloud) через `embed_resume_v2.py`
4. Опционально заливает PDF + `state.json` в Google Drive (если задан
   `GDRIVE_FOLDER_ID`) или S3 (если задан `S3_BUCKET`).

`state.json` **не коммитится** в репо — между прогонами чекпоинт живёт
на Drive (или его можно скачать из `Upload run artifacts` в логах
прогона). Если хочется автоматического переноса state.json между
прогонами — задай `GDRIVE_FOLDER_ID` + `GDRIVE_CREDENTIALS_JSON` как
секреты репо, и каждый прогон сначала будет читать локальный
state.json (пустой на свежем раннере) — для длинной истории сбора
лучше использовать локальный режим.

## Источники

Воркфлоу по умолчанию использует `arxiv,openalex,europepmc,stackexchange`.
Полный список модулей в `harvester/sources/`:

| Источник | Что есть | Заметки |
|---|---|---|
| `arxiv` | 500k+ свежих PDF (cs.LG, physics.chem-ph, cond-mat, q-bio.BM, …) | Требует ≥3 сек между запросами |
| `chemrxiv` | ~30k препринтов | Часто 403 с CI-IP (Cloudflare). Лучше с обычной машины |
| `openalex` | Сотни тысяч OA-статей по 5 концептам | Требует email в User-Agent |
| `europepmc` | Миллионы полных текстов медбио + смежная химия | Стабильный REST с курсором |
| `cyberleninka` | RU OAI-PMH | Метаданные стабильны, PDF может блокироваться CDN |
| `stackexchange` | Q+top answer как `.txt` (chemistry, ai, datascience, cs) | API без ключа (10k req/день) |

## Настройка

### 1. Поднять Qdrant Cloud

Бесплатный тариф Qdrant Cloud даёт ~1 GB кластера = около 1.5M векторов 768d. Это хватит на 100–300k чанков, т. е. примерно 5–15k документов.

1. Регистрируешься на https://cloud.qdrant.io
2. Создаёшь Free кластер (любой регион поближе к GitHub Actions — например, eu-central)
3. Берёшь `URL` (вроде `https://abcdef-...eu-central.aws.cloud.qdrant.io`) и API-ключ

Если не хочешь Qdrant Cloud — поднимешь сам Qdrant в Docker на VPS:

```bash
docker run -d --restart unless-stopped \
  -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

И проброс наружу через nginx + HTTPS. URL будет `https://qdrant.твой-домен/`.

### 2. Добавить секреты в репо

`Settings → Secrets and variables → Actions → New repository secret`:

| Имя | Значение |
|---|---|
| `QDRANT_URL` | URL Qdrant Cloud |
| `QDRANT_API_KEY` | API-ключ Qdrant Cloud |
| `HARVESTER_EMAIL` | Твой email для User-Agent OpenAlex |

`GROQ_API_KEY` уже должен быть в репо (используется приложением).

### 3. Включить воркфлоу

В `Actions → harvest` → `Enable workflow`. Дальше его можно запускать руками
через `workflow_dispatch` с произвольным бюджетом и списком источников.

## Что и куда сохраняется

Воркфлоу **не** коммитит ничего обратно в репо. После прогона:
- `harvester/state.json` и `harvester/logs/` сохраняются как **artifact**
  прогона (`Upload run artifacts`, retention 30 дней).
- Если задан `GDRIVE_FOLDER_ID` + `GDRIVE_CREDENTIALS_JSON` — `state.json`
  и спарсенные PDF/метаданные уходят в Google Drive (см.
  [`GOOGLE_DRIVE.md`](GOOGLE_DRIVE.md)).
- Если задан `S3_BUCKET` + `S3_*` — то же самое уходит в S3.

Большие данные не сохраняются ни в репо, ни как artifact:
- `all_pdfs/` — игнорируется (растёт без предела, заливается в Drive/S3)
- `harvested_meta/` — игнорируется (заливается в Drive/S3)
- `harvester/logs/harvest.log` — игнорируется (line-by-line, может пухнуть)
- `chunks_v2.jsonl` — игнорируется (40+ MB)
- `qdrant_db/` — игнорируется (embedded-БД больше не используется в cron — мы пушим в облако)

## Бюджет / тайминг

Один прогон 6 часов на GH Actions runner-е (ubuntu-latest, 2 vCPU, без GPU):

| Шаг | Скорость | За 5 часов |
|---|---|---|
| Скачивание | ~5 PDF/сек | ~90k PDF (но рейт-лимиты урежут до 5–15k) |
| Ингест (pypdf + чанкинг) | ~2 PDF/сек | ~36k PDF |
| Эмбеддинг (e5-base CPU) | ~80 чанков/сек | ~1.4M чанков |

Реальное узкое место — рейт-лимиты источников. По умолчанию `--budget 300` за один прогон, итого 4 прогона/сутки ≈ **1200 документов в день**, до 10k за неделю.

Хочешь быстрее — увеличь `--budget` через `workflow_dispatch` или измени дефолт в `harvest.yml`. Или поставь cron чаще (но не чаще, чем раз в час, чтобы не накладывались прогоны — стоит `concurrency: cancel-in-progress: false`).

## Локально

Тот же скрипт работает с локальной БД (без Qdrant Cloud) — просто не задавай `QDRANT_URL`:

```bash
python -m harvester.harvest_full --budget 50 --email you@example.com
```

Векторы попадут в `qdrant_db/`, а Streamlit-приложение возьмёт их оттуда автоматически.

## Если что-то идёт не так

- **Все PDF фейлятся 403/429** — обычно это chemRxiv или КиберЛенинка с CI-IP. Убери их из `--sources`, оставь arxiv,openalex,europepmc,stackexchange (стабильные).
- **Qdrant out of disk** — переключись на платный тариф, либо периодически удаляй чанки старше N лет (отдельный скрипт-cleanup).
- **state.json не сохраняется между прогонами в Actions** — workflow
  больше не пушит state.json в репо (это была причина задачи «без
  постоянных пушов»). Используй локальный режим (`harvester.loop` +
  Drive) или подключи `GDRIVE_FOLDER_ID` к workflow и **руками**
  скачивай актуальный `state.json` из Drive перед запуском.
- **Прогон длится >6 часов** — actions упадёт по `timeout-minutes: 350`. Уменьши `--time-limit-min` в воркфлоу, чтобы заранее завершаться.
