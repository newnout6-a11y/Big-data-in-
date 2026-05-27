# Настройка Qdrant Cloud

## Зачем

Локальный Qdrant (embedded mode) хорош для разработки, но для продакшн/демо нужен постоянно доступный сервер. Qdrant Cloud Free Tier даёт 1 GB RAM — этого хватает на ~100k+ точек с binary quantization.

---

## Создание кластера

1. Зарегистрироваться: [cloud.qdrant.io](https://cloud.qdrant.io/)
2. Create Cluster → Free Tier (1 GB RAM)
3. Записать:
   - **Cluster URL**: `https://your-cluster-id.region.aws.cloud.qdrant.io:6333`
   - **API Key**: сгенерировать в Dashboard → API Keys

---

## Конфигурация проекта

В `.env`:

```env
QDRANT_URL=https://your-cluster-id.region.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=your_api_key_here
```

После этого `embed_resume_v2.py` и приложение автоматически используют удалённый Qdrant вместо локального.

---

## Создание коллекции

Коллекция создаётся автоматически при первом запуске `embed_resume_v2.py`:

```bash
python pipeline/embed_resume_v2.py
```

Параметры коллекции `knowledge_hybrid`:
- Dense: 768d, cosine, on_disk
- Sparse: BM25, IDF modifier, on_disk
- Binary quantization: always_ram=True (32x экономия)

### Ручное создание (если нужно)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import *

client = QdrantClient(url="https://...", api_key="...")

client.create_collection(
    collection_name="knowledge_hybrid",
    vectors_config={
        "dense": VectorParams(size=768, distance=Distance.COSINE, on_disk=True)
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams(
            index=SparseIndexParams(on_disk=True),
            modifier=Modifier.IDF
        )
    },
    quantization_config=BinaryQuantization(
        binary=BinaryQuantizationConfig(always_ram=True)
    )
)
```

---

## Snapshot: скачивание и загрузка

### Скачать из Cloud на ПК

```bash
# Скачать snapshot (бинарный дамп):
python scripts/download_snapshot.py

# Или экспорт как JSONL (с векторами и payload):
python scripts/download_snapshot.py --mode jsonl
```

Результат:
- `knowledge_hybrid.snapshot` — бинарный дамп
- `knowledge_hybrid_export.jsonl` — JSONL (можно открыть/обработать)

### Импортировать JSONL в локальный Qdrant

```bash
# Все векторы:
python scripts/import_snapshot.py

# С ограничением (если RAM мало):
python scripts/import_snapshot.py --limit 40000

# Снести старую базу и залить заново:
python scripts/import_snapshot.py --recreate --limit 40000
```

Импортирует `knowledge_hybrid_export.jsonl` в локальный `qdrant_db/`. Векторы не пересчитываются — берутся готовые из JSONL. Идемпотентный (повторный запуск пропускает существующие точки по id).

---

## Проверка состояния

### Через CLI

```bash
python -c "
from qdrant_client import QdrantClient
import os
c = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
info = c.get_collection('knowledge_hybrid')
print(f'Points: {info.points_count}')
print(f'Vectors: {info.vectors_count}')
print(f'Status: {info.status}')
"
```

### Через GitHub Actions

Workflow `verify-qdrant.yml`:
```bash
# Запустить вручную через Actions → verify-qdrant → Run workflow
```

---

## Лимиты Free Tier

| Параметр | Лимит |
|----------|-------|
| RAM | 1 GB |
| Disk | 20 GB |
| Точки (с binary quant.) | ~100-150k |
| Точки (без квантования) | ~30-50k |
| API requests | без ограничений |

Binary quantization критична для Free Tier: без неё 768-мерные float32 векторы занимают 3 KB/точку, с ней — ~96 байт/точку в RAM.

---

## Переключение между локальным и Cloud

| Переменные | Режим |
|-----------|-------|
| `QDRANT_URL` не задан | Локальный (`qdrant_db/`) |
| `QDRANT_URL` задан | Удалённый (Cloud) |

Приложение автоматически выбирает режим при старте.
