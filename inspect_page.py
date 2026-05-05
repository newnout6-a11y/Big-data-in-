"""Диагностика того, что Qdrant реально знает про одну страницу PDF
и как она ранжируется при поиске.

Запускается из корня проекта:

    python inspect_page.py --notebook "хтп" --document "Лекция 5" --page 24 \
        --query "схема массообменных процессов"

Все параметры — подстроки, регистронезависимые. Можно указывать частично
(`--notebook хтп` совпадёт и с "ХТП Лекции"). Если параметр не задан —
скрипт предложит выбрать интерактивно.

Что выводит:
    1. Все чанки (text / chunk_index / список картинок с caption) для
       указанной страницы указанного документа указанной тетради.
    2. Если задан --query — для каждого чанка: dense-score, keyword-буст,
       итоговый score (как в notebooks.search_notebook).
    3. Топ-5 по search_notebook: какие фрагменты реально попадают в контекст
       LLM и на каком месте стоит искомая страница (или пометка «не попала
       в топ-20 кандидатов»).

Этот скрипт НЕ трогает индекс, только читает.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# Не тянем Streamlit и TF — это обычный CLI.
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qdrant_client import QdrantClient  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

import notebooks  # noqa: E402


def _qdrant_client() -> QdrantClient:
    """Тот же путь, что в app.загрузить_qdrant — удалённый если QDRANT_URL,
    иначе локальный qdrant_db/ рядом со скриптом.

    Если локальная БД занята другим процессом (обычно — запущенный Streamlit),
    делаем быструю копию во временную папку и работаем с ней: только читаем,
    оригинал не трогаем. Копия удаляется при выходе через atexit.
    """
    import atexit
    import shutil
    import tempfile

    url = (os.getenv("QDRANT_URL") or "").strip()
    if url:
        return QdrantClient(
            url=url,
            api_key=os.getenv("QDRANT_API_KEY") or None,
            prefer_grpc=False,
            timeout=60,
        )
    db_path = Path(__file__).resolve().parent / "qdrant_db"
    try:
        return QdrantClient(path=str(db_path))
    except RuntimeError as exc:
        if "already accessed" not in str(exc):
            raise
        print(
            f"  ⚠  qdrant_db занят другим процессом (Streamlit запущен?).\n"
            f"  Копирую во временную папку для чтения…"
        )
        tmp_dir = tempfile.mkdtemp(prefix="qdrant_inspect_")
        tmp_db = os.path.join(tmp_dir, "qdrant_db")
        shutil.copytree(str(db_path), tmp_db)
        print(f"  Готово. Временная копия: {tmp_db}\n")
        atexit.register(shutil.rmtree, tmp_dir, True)
        return QdrantClient(path=tmp_db)


def _найти_тетрадь(подстрока: str, user_id: str) -> dict[str, Any]:
    тетради = notebooks.list_notebooks(user_id)
    if not тетради:
        sys.exit(f"У пользователя {user_id!r} нет тетрадей.")
    if not подстрока:
        print("Доступные тетради:")
        for i, t in enumerate(тетради, 1):
            print(f"  [{i}] {t['title']}  ({len(t.get('files') or [])} файл(ов))")
        выбор = input("Номер тетради: ").strip()
        try:
            return тетради[int(выбор) - 1]
        except (ValueError, IndexError):
            sys.exit("Некорректный выбор.")
    подходят = [t for t in тетради if подстрока.lower() in t["title"].lower()]
    if not подходят:
        print(f"Тетради с подстрокой {подстрока!r} не найдено. Есть:")
        for t in тетради:
            print(f"  - {t['title']}")
        sys.exit(1)
    if len(подходят) > 1:
        print(f"Несколько тетрадей подходят под {подстрока!r}:")
        for i, t in enumerate(подходят, 1):
            print(f"  [{i}] {t['title']}")
        выбор = input("Номер: ").strip()
        try:
            return подходят[int(выбор) - 1]
        except (ValueError, IndexError):
            sys.exit("Некорректный выбор.")
    return подходят[0]


def _найти_документ(подстрока: str, тетрадь: dict[str, Any]) -> str:
    файлы = [f.get("name") for f in (тетрадь.get("files") or []) if f.get("name")]
    if not файлы:
        sys.exit(f"В тетради «{тетрадь['title']}» нет файлов.")
    if not подстрока:
        print("Файлы тетради:")
        for i, n in enumerate(файлы, 1):
            print(f"  [{i}] {n}")
        выбор = input("Номер файла: ").strip()
        try:
            return файлы[int(выбор) - 1]
        except (ValueError, IndexError):
            sys.exit("Некорректный выбор.")
    подходят = [n for n in файлы if подстрока.lower() in n.lower()]
    if not подходят:
        print(f"Файлов с подстрокой {подстрока!r} нет. Есть:")
        for n in файлы:
            print(f"  - {n}")
        sys.exit(1)
    if len(подходят) > 1:
        print(f"Несколько файлов подходят под {подстрока!r}:")
        for i, n in enumerate(подходят, 1):
            print(f"  [{i}] {n}")
        выбор = input("Номер: ").strip()
        try:
            return подходят[int(выбор) - 1]
        except (ValueError, IndexError):
            sys.exit("Некорректный выбор.")
    return подходят[0]


def _чанки_страницы(
    client: QdrantClient,
    тетрадь: dict[str, Any],
    документ: str,
    страница: int,
    user_id: str,
) -> list[dict[str, Any]]:
    """Прямой scroll по фильтру (тетрадь + документ + страница).
    Возвращает payloads, отсортированные по chunk_index."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    notebooks.ensure_collection(client, тетрадь)
    query_filter = Filter(must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="notebook_id", match=MatchValue(value=тетрадь["id"])),
        FieldCondition(key="document", match=MatchValue(value=документ)),
        FieldCondition(key="page", match=MatchValue(value=страница)),
    ])
    найдено: list[dict[str, Any]] = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=тетрадь["collection"],
            scroll_filter=query_filter,
            limit=32,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        найдено.extend(dict(p.payload or {}) for p in batch)
        if offset is None:
            break
    найдено.sort(key=lambda p: int(p.get("chunk_index") or 0))
    return найдено


def _форматировать_картинку(i: int, картинка: dict[str, Any]) -> str:
    путь = картинка.get("path") or "(без path)"
    caption = (картинка.get("caption") or "").strip()
    if caption:
        caption_repr = caption if len(caption) <= 200 else caption[:200] + "…"
    else:
        caption_repr = "(caption пустой)"
    return f"    [img {i}] {путь}\n            caption: {caption_repr}"


def _печать_чанка(idx: int, payload: dict[str, Any]) -> None:
    text = (payload.get("text") or "").strip()
    images = payload.get("images") or []
    print(f"\n  ┌─ чанк #{idx} (chunk_index={payload.get('chunk_index')})")
    print(f"  │  file_hash: {payload.get('file_hash', '')[:12]}…")
    print(f"  │  text ({len(text)} симв.):")
    for line in text.splitlines() or [""]:
        print(f"  │    {line}")
    if images:
        print(f"  │  картинки ({len(images)}):")
        for i, im in enumerate(images, 1):
            for line in _форматировать_картинку(i, im).splitlines():
                print(f"  │{line}")
    else:
        print("  │  картинки: нет")
    print("  └──────")


def _ранжирование_чанков(
    payloads: list[dict[str, Any]],
    query_vector: list[float],
    question: str,
    client: QdrantClient,
    тетрадь: dict[str, Any],
) -> list[tuple[dict[str, Any], float, float, float]]:
    """Для каждого из переданных payloads получает его dense-score к запросу.

    Делается через query_points с фильтром по document+page и большим
    лимитом (чтобы все чанки этой страницы попали в ответ).
    Возвращает [(payload, dense, keyword, итоговый), ...].
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    if not payloads:
        return []
    document = payloads[0].get("document")
    page = payloads[0].get("page")
    user_id = payloads[0].get("user_id") or notebooks.get_user_id()
    query_filter = Filter(must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="notebook_id", match=MatchValue(value=тетрадь["id"])),
        FieldCondition(key="document", match=MatchValue(value=document)),
        FieldCondition(key="page", match=MatchValue(value=page)),
    ])
    response = client.query_points(
        collection_name=тетрадь["collection"],
        query=query_vector,
        limit=64,
        query_filter=query_filter,
        with_payload=True,
    )
    оценки: dict[int, float] = {}
    for point in response.points:
        chunk_index = int((point.payload or {}).get("chunk_index") or 0)
        оценки[chunk_index] = float(point.score)

    токены = notebooks._токены_запроса(question)
    результат: list[tuple[dict[str, Any], float, float, float]] = []
    for payload in payloads:
        chunk_index = int(payload.get("chunk_index") or 0)
        dense = оценки.get(chunk_index, 0.0)
        буст = notebooks._keyword_буст(payload, токены)
        результат.append((payload, dense, буст, dense + буст))
    return результат


def _топ_по_тетради(
    model: SentenceTransformer,
    client: QdrantClient,
    тетрадь: dict[str, Any],
    question: str,
    *,
    искомая_стр: int,
    искомый_документ: str,
    limit: int = 5,
) -> None:
    """Прогон реального search_notebook. Видно что LLM реально получит.
    Показываем и dense-score, и keyword-буст, и итоговый — чтобы сортировка
    была понятна (search_notebook сортирует по dense+буст, не по dense)."""
    токены = notebooks._токены_запроса(question)
    точки = notebooks.search_notebook(
        client, model, тетрадь, question, limit=limit,
    )
    print(f"\n── Топ-{limit} по search_notebook для запроса {question!r} ──")
    print(f"   (сортировка по dense+keyword; .score у qdrant-point = dense only)\n")
    if not точки:
        print("  (ничего не вернулось)")
        return
    искомая_в_топе = False
    for i, point in enumerate(точки, 1):
        payload = point.payload or {}
        doc = str(payload.get("document") or "")
        page = payload.get("page")
        kw = notebooks._keyword_буст(payload, токены)
        mark = ""
        if искомый_документ.lower() in doc.lower() and page == искомая_стр:
            mark = "  ← ИСКОМАЯ СТРАНИЦА"
            искомая_в_топе = True
        print(
            f"  [{i}] dense={point.score:.3f}  kw={kw:+.3f}  итог={point.score + kw:.3f}  "
            f"стр.{page} chunk={payload.get('chunk_index')}{mark}"
        )
    print()
    if not искомая_в_топе:
        print(
            f"  ⚠ Искомая страница {искомая_стр} из {искомый_документ!r} "
            f"в топ-{limit} НЕ попала."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", "-n", default="", help="Подстрока названия тетради")
    parser.add_argument("--document", "-d", default="", help="Подстрока имени файла")
    parser.add_argument("--page", "-p", type=int, required=True, help="Номер страницы")
    parser.add_argument("--query", "-q", default="", help="Запрос для подсчёта score")
    parser.add_argument("--user-id", default="", help="Переопределить NAVIGATOR_USER_ID")
    args = parser.parse_args()

    user_id = (args.user_id or notebooks.get_user_id()).strip() or "local"
    print(f"user_id: {user_id}")

    тетрадь = _найти_тетрадь(args.notebook, user_id)
    print(f"Тетрадь: {тетрадь['title']}  (id={тетрадь['id']}, collection={тетрадь['collection']})")

    документ = _найти_документ(args.document, тетрадь)
    print(f"Документ: {документ}")
    print(f"Страница: {args.page}")

    client = _qdrant_client()

    payloads = _чанки_страницы(client, тетрадь, документ, args.page, user_id)
    if not payloads:
        print(f"\n⚠ В Qdrant нет чанков для стр.{args.page} документа {документ!r}.")
        print("  Это означает одно из:")
        print("  - страница не попала в индексацию (чистый PDF без текста?);")
        print("  - номер страницы в PDF-просмотрщике и в индексе отличается;")
        print("  - документ индексировался под другим именем.")
        return

    print(f"\n── Чанков стр.{args.page}: {len(payloads)} ──")
    for i, p in enumerate(payloads, 1):
        _печать_чанка(i, p)

    if args.query:
        print(f"\n── Оценка чанков стр.{args.page} к запросу {args.query!r} ──")
        model = SentenceTransformer("intfloat/multilingual-e5-base")
        qv = model.encode("query: " + args.query, normalize_embeddings=True).tolist()
        оценки = _ранжирование_чанков(payloads, qv, args.query, client, тетрадь)
        for i, (p, dense, kw, total) in enumerate(оценки, 1):
            print(
                f"  чанк #{i} (chunk_index={p.get('chunk_index')}): "
                f"dense={dense:.3f}  keyword={kw:+.3f}  итог={total:.3f}  "
                f"{'✓ проходит min_score' if dense >= notebooks.NOTEBOOK_MIN_SCORE or kw >= 0.15 else '✗ отсеивается'}"
            )
        _топ_по_тетради(
            model, client, тетрадь, args.query,
            искомая_стр=args.page,
            искомый_документ=документ,
            limit=5,
        )


if __name__ == "__main__":
    main()
