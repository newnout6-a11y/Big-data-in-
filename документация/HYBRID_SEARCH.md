# Гибридный поиск

## Принцип

Система использует два типа поиска одновременно и объединяет результаты через RRF (Reciprocal Rank Fusion):

```
Вопрос
  │
  ├──► Dense search (семантический)
  │    sentence-transformers → cosine similarity
  │
  ├──► Sparse search (лексический)
  │    BM25 токенизация → exact match
  │
  └──► RRF Fusion → единый ранжированный список
                      │
                      ▼
              Cross-encoder reranker
              (финальная переранжировка)
```

---

## Dense поиск

- **Модель**: `intfloat/multilingual-e5-base` (768 измерений, ~440 MB)
- **Метрика**: cosine similarity
- **Prefix**: `query: ` для вопросов, `passage: ` для документов (обязательно — e5 обучена с префиксами)
- **Нормализация**: `normalize_embeddings=True` → cosine = dot product
- **Хранение**: on-disk с binary quantization (32x экономия RAM)

**Как работает при запросе:**
1. Вопрос → `model.encode("query: " + вопрос, normalize_embeddings=True)` → вектор 768d
2. Qdrant ищет ближайших соседей в `dense` named vector
3. Возвращает top-N по cosine similarity

Плюсы: понимает семантику, синонимы, перефразировки, работает кросс-язычно (ru/en).
Минусы: может «промахнуться» по точным терминам, формулам, аббревиатурам.

## Sparse поиск (BM25)

- **Реализация**: FastEmbed `Qdrant/bm25` — это **не нейросеть**, а словарь токенизации (~25 KB)
- **TF**: вычисляется на клиенте (FastEmbed выдаёт `indices` и `values`)
- **IDF**: вычисляется на сервере Qdrant (параметр `Modifier.IDF` в коллекции)
- **Модуль**: `core/hybrid_search.py`
- **Lazy init**: double-checked locking через `threading.Lock()` — потокобезопасно в Streamlit

**Как работает при запросе:**
1. Вопрос → `получить_bm25().embed([вопрос])` → `SparseVector(indices=[...], values=[...])`
2. Qdrant ищет по `sparse` named vector с server-side IDF scoring
3. Возвращает top-N по BM25 score

```python
from hybrid_search import построить_sparse_один, построить_sparse_батч

# Один текст:
indices, values = построить_sparse_один("квантовая химия DFT")

# Батч (для ингеста):
sparse_list = построить_sparse_батч(["текст 1", "текст 2", ...])
# → [(indices, values), (indices, values), ...]
```

Плюсы: точное совпадение терминов, формул, аббревиатур (DFT, SMILES, QSAR).
Минусы: не понимает синонимы, не работает кросс-язычно.

---

## RRF Fusion

Reciprocal Rank Fusion объединяет два списка без нормализации скоров:

```python
def rrf_fuse(списки_id, k=60):
    """
    Для каждого документа:
      score(doc) = Σ 1/(k + rank_i + 1)   для каждого списка i, где doc присутствует

    k=60 — стандарт из Cormack et al. 2009
    """
    очки = {}
    for список in списки_id:
        for ранг, ид in enumerate(список):
            очки[ид] += 1.0 / (k + ранг + 1)
    return sorted(очки.keys(), key=lambda x: -очки[x])
```

**Почему k=60:**
- При k=60 топ-1 получает `1/61 ≈ 0.016`, топ-10 получает `1/71 ≈ 0.014` — разница невелика
- Это сглаживает шум в ранжировании: если dense и sparse дают разный порядок, RRF не паникует
- При k=1 (агрессивный) топ-1 доминирует; при k=1000 (плоский) все позиции почти равны

**Свойства:**
- Документ, найденный обоими методами → получает суммарный бонус (~2x score)
- Документ, найденный только одним — всё равно попадает в результат
- Не требует нормализации скоров между dense и sparse (они несопоставимы)

---

## Cross-encoder Reranker

После RRF fusion top-30 результатов переранжируются cross-encoder'ом:

| Параметр | Значение |
|----------|----------|
| Модель | `BAAI/bge-reranker-v2-m3` (env: `RERANKER_MODEL`) |
| Размер | ~600 MB (скачивается один раз в `~/.cache/huggingface/`) |
| max_length | 512 токенов на пару |
| Скорость | ~0.5 сек на 30 пар (CPU) |
| Модуль | `core/reranker.py` |
| Инициализация | Ленивая, double-checked locking |

**Алгоритм:**
```python
пары = [(вопрос, документ) for документ in top_30]
скоры = CrossEncoder.predict(пары, show_progress_bar=False)  # float[]
индексы = sorted(range(len(документы)), key=lambda i: -скоры[i])
return [(i, скоры[i]) for i in индексы[:top_k]]
```

**Зачем нужен:**
- Bi-encoder (e5) кодирует вопрос и документ **отдельно** → сравнение только по dot product
- Cross-encoder видит **пару целиком** → attention между всеми токенами вопроса и документа
- Это даёт существенно лучшее понимание релевантности (особенно для сложных запросов)
- Компенсирует -2-5% recall от binary quantization

**Почему только top-30, а не все:**
- Cross-encoder O(n) по числу пар, каждая пара проходит через полный transformer
- 30 пар × 512 токенов ≈ 0.5 сек на CPU — приемлемо для UX
- 1000 пар заняло бы ~15 сек — неприемлемо

---

## Коллекция Qdrant

Коллекция `knowledge_hybrid` с named-vectors:

```python
vectors_config = {
    "dense": VectorParams(size=768, distance=Distance.COSINE, on_disk=True)
}
sparse_vectors_config = {
    "sparse": SparseVectorParams(
        index=SparseIndexParams(on_disk=True),
        modifier=Modifier.IDF  # серверный IDF — вычисляется из всей коллекции
    )
}
quantization_config = BinaryQuantization(
    binary=BinaryQuantizationConfig(always_ram=True)
)
```

**Как работает binary quantization:**
1. Оригинальный float32 вектор (768 × 4 = 3072 байт) хранится **на диске**
2. Бинарный код (768 бит = 96 байт) хранится **в RAM**
3. При поиске: грубый кандидат-список по Hamming distance бинарных кодов
4. Затем rescore кандидатов по оригинальным float32 с диска
5. Итог: 32x меньше RAM, потеря recall 2-5%

### Payload-индексы

Создаются автоматически при инициализации коллекции:

| Поле | Тип | Назначение |
|------|-----|-----------|
| `domain` | KEYWORD | Фильтр по домену (chemistry/it_chem/it_ml) |
| `subdomain` | KEYWORD | Фильтр по субдомену (21 варианта) |
| `source` | KEYWORD | Фильтр по источнику (arxiv/openalex/...) |
| `language` | KEYWORD | Фильтр по языку (ru/en/mixed) |
| `doc_id` | KEYWORD | Идентификатор документа (для группировки) |
| `year` | INTEGER | Range-фильтрация по году публикации |
| `text_hash` | KEYWORD | Дедупликация при resume-загрузке |

---

## Фильтрация в UI

Пользователь может настроить фильтры в sidebar:
- **Домен**: один из доменов таксономии или «все»
- **Субдомен**: конкретный субдомен внутри домена
- **Язык**: ru / en / все
- **Год**: Range-фильтр (от — до)

Фильтры передаются в Qdrant как `Filter` с `FieldCondition(key, MatchValue/Range)`.

Пример:
```python
Filter(must=[
    FieldCondition(key="domain", match=MatchValue(value="it_chem")),
    FieldCondition(key="year", range=Range(gte=2022)),
])
```

---

## Recency boost

Свежие документы получают бонус к скору после reranker'а:

```python
def _recency_boost(year, current_year=2026):
    # Документы последних 2 лет: +10-15% к скору
    # Документы 2-5 лет: линейный спад бонуса
    # Документы старше 5 лет: без бонуса (score × 1.0)
```

Бонус применяется **после** reranker'а, чтобы не искажать семантическую релевантность. Только мягкая коррекция для разрешения ничьих между одинаково релевантными фрагментами.

---

## Полный pipeline запроса (шаг за шагом)

```
1. Пользователь вводит вопрос
2. Scope-guard: cos(вопрос, прототипы) → in-scope?
   НЕТ → "Не моя тема" + примеры
3. Dense: "query: " + вопрос → e5 → 768d → Qdrant cosine search (top-50)
4. Sparse: BM25 tokenize вопрос → Qdrant BM25 search (top-50)
5. RRF: объединить dense_ids + sparse_ids (k=60) → единый список
6. Payload-фильтры (domain/language/year) — если выставлены в UI
7. Reranker: top-30 → CrossEncoder.predict → пересортировка
8. Recency boost: score × (1 + bonus) для свежих
9. Финальный top-K → в промпт LLM
```

---

## Миграция со старых коллекций

Проект прошёл через несколько версий коллекций:

1. `химия` — оригинальная (только dense, 46k точек, без named vectors)
2. `knowledge` — с payload-индексами и авторазметкой (flat vector)
3. `knowledge_hybrid` — текущая (dense + sparse, named vectors, binary quant)

Скрипты миграции:
- `pipeline/миграция_в_v2.py`: `химия` → `knowledge` (копирует векторы, добавляет payload)
- `pipeline/пересобрать_гибрид.py`: `knowledge` → `knowledge_hybrid` (добавляет sparse)

Приложение умеет работать с любой из трёх коллекций (авто-детект в `выбрать_коллекцию()`).
