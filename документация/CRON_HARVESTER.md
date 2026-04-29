# Бесконечный харвестер на GitHub Actions

Воркфлоу `.github/workflows/harvest.yml` запускается каждые 6 часов и за один прогон:

1. Скачивает свежие документы из выбранных источников в `all_pdfs/`
2. Парсит/чанкит/авторазмечает их через `ingest_v2.py` → `chunks_v2.jsonl`
3. Догружает чанки в **удалённый Qdrant** (Qdrant Cloud) через `embed_resume_v2.py`
4. Коммитит обновлённый `harvester/state.json` и JSON-отчёты обратно в репо

Это даёт инкрементальный, переживающий рестарты сбор корпуса без локального компьютера.

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

В `Actions → harvest` → `Enable workflow`. Дальше он будет запускаться по cron каждые 6 часов автоматически. Также можно запустить руками через `workflow_dispatch` с произвольным бюджетом и списком источников.

## Что и куда коммитится

Воркфлоу пушит **обратно в ту же ветку**:
- `harvester/state.json` — курсоры, список скачанных `doc_id`. Без этого следующий прогон не знает, что уже обработано.
- `harvester/logs/run_*.json` — короткий JSON-отчёт каждого прогона (длительность, return-codes по шагам).

Большие данные **не** коммитятся:
- `all_pdfs/` — игнорируется (растёт без предела)
- `harvested_meta/` — игнорируется
- `harvester/logs/harvest.log` — игнорируется (line-by-line, может пухнуть)
- `chunks_v2.jsonl` — игнорируется (40+ MB)
- `qdrant_db/` — игнорируется (embedded-БД больше не используется в cron — мы пушим в облако)

Сообщение коммитов: `harvest: incremental update [skip ci]` — не триггерит сам себя.

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
- **state.json конфликтует** — если ты руками что-то правил локально и пушил, GH Actions встретит конфликт при `git push`. Ничего страшного, на следующий прогон он подтянет main и продолжит.
- **Прогон длится >6 часов** — actions упадёт по `timeout-minutes: 350`. Уменьши `--time-limit-min` в воркфлоу, чтобы заранее завершаться.
