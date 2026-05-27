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

- **Модель**: `intfloat/multilingual-e5-base` (768 измерений)
- **Метрика**: cosine similarity
- **Prefix**: `query: ` для вопросов, `passage: ` для документов
- **Хранение**: on-disk с binary quantization (32x экономия RAM)

Плюсы: понимает семантику, синонимы, перефразировки, работает кросс-язычно (ru/en).
Минусы: может «промахнуться» по точным терминам, формулам, аббревиатурам.

## Sparse поиск (BM25)

- **Реализация**: FastEmbed `Qdrant/bm25` с серверным IDF (Modifier.IDF)
- **Токенизация**: на стороне Qdrant, без дополнительных моделей
- **Модуль**: `core/hybrid_search.py`
- **Lazy init**: модель BM25 (~25 КБ — это не нейросеть, просто словарь) загружается один раз при первом вызове, через double-checked locking (потокобезопасно)
- **Потокобезопасность**: все модели (BM25, reranker) используют `threading.Lock` + кэш-словарь для ленивой инициализации — безопасно в Streamlit с `@st.cache_resource`

Плюсы: точное совпадение терминов, формул, аббревиатур.
Минусы: не понимает синонимы, не работает кросс-язычно.

### Построение sparse-вектора

```python
from hybrid_search import построить_sparse_один, построить_sparse_батч

# Один текст:
sparse = построить_sparse_один("квантовая химия DFT")
# → SparseVector(indices=[...], values=[...])

# Батч:
sparse_list = построить_sparse_батч(["текст 1", "текст 2", ...])
```

---

## RRF Fusion

Reciprocal Rank Fusion объединяет два списка без необходимости нормализации скоров:

```python
def rrf_fuse(dense_ids, sparse_ids, k=60):
    """
    score(doc) = 1/(k + rank_dense) + 1/(k + rank_sparse)
    """
```

- `k=60` — стандартный параметр RRF (сглаживание)
- Документ, найденный обоими методами, получает бонус
- Документ, найденный только одним — всё равно попадает в результат

---

## Cross-encoder Reranker

После RRF fusion top-30 результатов переранжируются cross-encoder'ом:

- **Модель**: `BAAI/bge-reranker-v2-m3` (можно переопределить через env `RERANKER_MODEL`)
- **Размер**: ~600 MB (скачивается один раз)
- **max_length**: 512 токенов на пару
- **Скорость**: ~0.5 сек на 30 пар (CPU)
- **Модуль**: `core/reranker.py`
- **Lazy init**: модель загружается один раз при первом вызове, через double-checked locking (потокобезопасно)

```python
from reranker import переранжировать

# переранжировать(вопрос, список_текстов) → отсортированные индексы
```

Cross-encoder видит пару (вопрос, документ) целиком и даёт более точный скор, чем bi-encoder. Компенсирует потерю recall от binary quantization.

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
        modifier=Modifier.IDF  # серверный IDF
    )
}
quantization_config = BinaryQuantization(
    binary=BinaryQuantizationConfig(always_ram=True)
)
```

### Payload-индексы

| Поле | Тип | Назначение |
|------|-----|-----------|
| `domain` | KEYWORD | Фильтр по домену |
| `subdomain` | KEYWORD | Фильтр по субдомену |
| `source` | KEYWORD | Фильтр по источнику |
| `language` | KEYWORD | Фильтр по языку |
| `doc_id` | KEYWORD | Идентификатор документа |
| `year` | INTEGER | Фильтр/сортировка по году |
| `text_hash` | KEYWORD | Дедупликация |

---

## Фильтрация в UI

Пользователь может настроить фильтры:
- **Домен**: один из доменов таксономии или «все»
- **Субдомен**: конкретный субдомен
- **Язык**: ru / en / все
- **Год**: Range-фильтр

Фильтры передаются в Qdrant как `Filter` с `FieldCondition`.

---

## Recency boost

Свежие документы получают бонус к скору:

```python
def _recency_boost(year, current_year=2024):
    # Документы последних 2 лет: +10-15% к скору
    # Документы старше 5 лет: без бонуса
```

---

## Миграция со старых коллекций

Проект прошёл через несколько версий коллекций:

1. `химия` — оригинальная (только dense, 46k точек)
2. `knowledge` — с payload-индексами и авторазметкой
3. `knowledge_hybrid` — текущая (dense + sparse, named vectors)

Скрипты миграции:
- `pipeline/миграция_в_v2.py`: `химия` → `knowledge` (копирует векторы, добавляет payload)
- `pipeline/пересобрать_гибрид.py`: `knowledge` → `knowledge_hybrid` (добавляет sparse)

Приложение умеет работать с любой из трёх коллекций (авто-детект в `выбрать_коллекцию()`).
