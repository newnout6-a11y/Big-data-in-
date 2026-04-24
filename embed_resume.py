import os
import json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

файл_чанков = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunks.jsonl")
папка_базы = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db")
название_коллекции = "химия"
размер_батча = 64

клиент = QdrantClient(path=папка_базы)

уже_в_базе = клиент.count(название_коллекции).count
print(f"В базе уже: {уже_в_базе} точек")

все_чанки = []
with open(файл_чанков, "r", encoding="utf-8") as файл:
    for строка in файл:
        строка = строка.strip()
        if строка:
            все_чанки.append(json.loads(строка))

print(f"Всего чанков в файле: {len(все_чанки)}")

осталось = все_чанки[уже_в_базе:]
print(f"Осталось загрузить: {len(осталось)}")

if not осталось:
    print("Нечего загружать, база уже заполнена")
    import sys
    sys.exit(0)

модель = SentenceTransformer("intfloat/multilingual-e5-base")
print("Модель загружена")

текущий_ид = уже_в_базе

for старт in range(0, len(осталось), размер_батча):
    батч = осталось[старт:старт + размер_батча]

    тексты = ["passage: " + ч["text"] for ч in батч]
    векторы = модель.encode(тексты, show_progress_bar=False, normalize_embeddings=True)

    точки = []
    for i, чанк in enumerate(батч):
        точки.append(PointStruct(
            id=текущий_ид,
            vector=векторы[i].tolist(),
            payload={
                "text": чанк["text"],
                "document": чанк["document"],
                "page": чанк["page"],
                "case": чанк["case"]
            }
        ))
        текущий_ид += 1

    клиент.upsert(collection_name=название_коллекции, points=точки)

    if (старт // размер_батча + 1) % 10 == 0 or старт + размер_батча >= len(осталось):
        всего_готово = уже_в_базе + min(старт + размер_батча, len(осталось))
        print(f"  Загружено в Qdrant: {всего_готово}/{len(все_чанки)}")

print(f"\nГотово! В базе теперь {клиент.count(название_коллекции).count} векторов")
