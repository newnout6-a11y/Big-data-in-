# Qdrant Cloud Free + GitHub Actions: автономная векторизация

Этот гайд — как настроить полностью бесплатный, полностью автономный пайплайн:
твой ноутбук не нужен, всё крутится в GitHub Actions, вектора живут в Qdrant Cloud Free.

## Что мы получаем

```
Google Drive (твой PDF-корпус)
        ↓ rclone (через секрет RCLONE_CONFIG)
GitHub Actions (4 vCPU, 16 GB RAM, бесплатно для public-репо)
   - подтягивает свежий state.json из Drive
   - качает свежие PDF из arXiv / OpenAlex / Europe PMC / ...
   - парсит и чанкит (ingest_v2.py)
   - эмбеддит (embed_resume_v2.py)
   - пушит результат в Qdrant Cloud
        ↓ HTTP
Qdrant Cloud Free (1 GB RAM, 4 GB диск, 0.5 vCPU)
   - принимает векторы по API
   - хранит ~3-5M точек 768d с binary quantization
```

Запуск — каждые 10 минут по cron'у. Никакого участия со стороны.

## 1. Зарегаться на Qdrant Cloud (2 минуты)

1. Открыть https://cloud.qdrant.io → Sign up (через email или GitHub).
2. Подтвердить email.
3. На дашборде нажать **Create Free Cluster**:
   - Cloud provider: любой (AWS / Azure / GCP)
   - Region: ближайший к тебе
   - Name: `big-data-free`
4. Дождаться статуса **Running** (~1 минута).
5. В деталях кластера нажать **Get API key** → создать → **скопировать ключ сразу**, второй раз не покажет.
6. Скопировать **Endpoint URL** (вида `https://xxx.aws.cloud.qdrant.io:6333`).

## 2. Положить секреты в GitHub

В репозитории: Settings → Secrets and variables → Actions → **New repository secret**.

Минимум:

| Имя | Значение | Зачем |
|---|---|---|
| `QDRANT_URL` | Endpoint URL из шага 1 | Куда пушить векторы |
| `QDRANT_API_KEY` | API key из шага 1 | Авторизация в Qdrant Cloud |
| `HARVESTER_EMAIL` | твоя почта | User-Agent для OpenAlex / Unpaywall |

Опционально, если хочешь чтобы PDF/чанки уезжали в твой Google Drive:

| Имя | Значение | Зачем |
|---|---|---|
| `RCLONE_CONFIG` | содержимое `~/.config/rclone/rclone.conf` | Доступ к Drive из CI |
| `CORE_API_KEY` | https://core.ac.uk/services/api | Источник CORE (OA-документы) |

Гайд по настройке rclone и Drive — `документация/GOOGLE_DRIVE.md`.

## 3. Запуск

Само начнёт работать по cron'у (`*/10 * * * *`). Чтобы проверить руками — Actions → harvest → **Run workflow**. Дефолтные параметры уже включают `run_ingest=true` и `run_embed=true`.

После первого прогона в дашборде Qdrant Cloud увидишь коллекцию `knowledge_hybrid` с ненулевым числом точек.

## 4. Емкость и квантование

Free tier: 1 GB RAM + 4 GB диск + 0.5 vCPU.

`embed_resume_v2.py` создаёт коллекцию с **binary quantization** + **on_disk dense vectors**:
- Полные float32-вектора лежат на диске (4 GB → ~1.3M точек 768d).
- В RAM держим только бинарную копию (32× меньше) → 1 GB RAM = ~13M бинарных кодов 768d.
- Поиск идёт по бинарным, потом топ-100 пересчитывается на оригинальных float32 (rescoring) → recall практически как у full-precision.

Реальный практический потолок Free tier с этими настройками — **3-5M чанков**. Дальше упрёшься либо в 4 GB диска, либо начнёт деградировать индексация на 0.5 vCPU.

## 5. Когда перерастёшь Free tier

См. `документация/ORACLE_CLOUD.md` — как поднять self-hosted Qdrant на бесплатной виртуалке Oracle Cloud (4 vCPU + 24 GB RAM + 200 GB SSD, навсегда бесплатно).

## 6. Скачать вектора себе на ПК

Скриптом `download_snapshot.py` в корне репо:

```bash
# .env должен содержать QDRANT_URL и QDRANT_API_KEY
python download_snapshot.py                         # snapshot (бинарный дамп)
python download_snapshot.py --mode jsonl            # JSONL-экспорт (для других тулов)
python download_snapshot.py --cleanup               # удалить snapshot с сервера после скачки
```

Snapshot восстанавливается локально:

```python
from qdrant_client import QdrantClient
c = QdrantClient(path="./qdrant_db")
c.recover_snapshot("knowledge_hybrid", "./knowledge_hybrid.snapshot")
```

После этого можно гонять Streamlit-приложение локально без Qdrant Cloud — оно само возьмёт `qdrant_db/`.

## 7. Если что-то идёт не так

- **Workflow падает с `QDRANT_URL not set`** — проверь, что секрет в Settings → Secrets, **именно** `QDRANT_URL` (без опечаток).
- **`disk quota exceeded`** в Qdrant Cloud — ты упёрся в 4 GB free tier. Качай снапшот, пересаживайся на Oracle Cloud (см. п.5) или удаляй старые точки.
- **Кластер «приостановлен»** — Free tier авто-suspend'ится после 1 недели простоя. Войди в дашборд и нажми Resume. Если cron-trigger workflow'а активен — кластер не будет успевать заснуть.
- **Кластер удалён** через 4 недели простоя — поднимай новый, секреты в репо обнови, CI догрузит данные с нуля (idempotent).
