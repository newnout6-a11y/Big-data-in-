"""Состояние харвестера: курсоры по источникам + список уже скачанных.

Кросс-источниковый дедуп: в поле `normalized_ids` хранятся нормализованные
ключи (DOI или arxiv-id без версии). Один и тот же документ, пришедший из
arxiv и openalex, получит одинаковый normalized_id и будет скачан один раз.
"""
import json
import os
import re
import threading


_БАЗА = os.path.dirname(os.path.abspath(__file__))
ФАЙЛ_СОСТОЯНИЯ = os.path.join(_БАЗА, "state.json")
ФАЙЛ_ЛОГА = os.path.join(_БАЗА, "logs", "harvest.log")


_замок = threading.Lock()


def _значения_по_умолчанию():
    return {
        "version": 4,
        "sources": {
            "arxiv": {"last_index": 0, "last_run": None},
            "chemrxiv": {"skip": 0, "last_run": None},
            "openalex": {"cursors": {}, "last_run": None},
            "europepmc": {"cursors": {}, "last_run": None},
            "cyberleninka": {"current_date": "2020-01-01", "last_run": None},
            "stackexchange": {"sites": {}, "last_run": None},
        },
        "downloaded_ids": [],
        "normalized_ids": [],
        # v4: учёт доменов для балансировки (chem/it/other)
        "domain_counts": {"chem": 0, "it": 0, "other": 0},
    }


# Регексы для нормализации doc_id → кросс-источниковый ключ.
_RE_DOI = re.compile(r"10\.\d{4,9}/[^\s]+", re.IGNORECASE)
_RE_ARXIV_OLD = re.compile(r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7})", re.IGNORECASE)
_RE_ARXIV_NEW = re.compile(r"(\d{4}\.\d{4,5})")


def нормализовать_doc_id(doc_id: str) -> str:
    """Возвращает канонический ключ для кросс-источникового дедупа.

    Приоритет:
      1. Если строка содержит DOI arxiv-алиаса (10.48550/arXiv.XXXX) → arxiv:XXXX.
      2. Если содержит обычный DOI → doi:<lower, без версии>.
      3. Если это arxiv:XXXX или openalex:10.48550/arxiv.XXXX → arxiv:XXXX (без vN).
      4. Иначе — исходный doc_id как есть (lowercased).

    Примеры:
      нормализовать_doc_id("arxiv:2304.12345v2")       -> "arxiv:2304.12345"
      нормализовать_doc_id("openalex:10.1038/s41586-023-12345") -> "doi:10.1038/s41586-023-12345"
      нормализовать_doc_id("europepmc:10.1038/s41586-023-12345") -> "doi:10.1038/s41586-023-12345"
      нормализовать_doc_id("europepmc:PMC1234567")     -> "europepmc:pmc1234567"
      нормализовать_doc_id("se:stackoverflow:12345")   -> "se:stackoverflow:12345"
    """
    if not doc_id:
        return ""

    s = doc_id.strip()

    # Отбросить префикс источника, если есть (мы узнаем источник из метадаты).
    тело = s
    if ":" in s:
        префикс, _, остаток = s.partition(":")
        if префикс.lower() in {"arxiv", "openalex", "europepmc", "chemrxiv", "cyberleninka", "doi"}:
            тело = остаток.strip()

    # 1. arxiv-алиас в виде DOI: 10.48550/arXiv.2304.12345 или 10.48550/arXiv.cs.CV/0601001
    # Важно: не исключаем '/' и 'v' из character class — они могут быть частью
    # старых arxiv-идентификаторов (cs.CV/0601001). Версию снимаем регексом в конце.
    m = re.search(r"10\.48550/arxiv\.([^\s]+)", тело, re.IGNORECASE)
    if m:
        base = re.sub(r"v\d+$", "", m.group(1), flags=re.IGNORECASE).rstrip(".")
        return f"arxiv:{base.lower()}"

    # 2. arxiv-id нового формата: 2304.12345(v2)
    m = _RE_ARXIV_NEW.search(тело)
    if m and "/" not in тело.split(m.group(1))[0][-10:]:
        # убираем хвост версии
        return f"arxiv:{m.group(1)}"

    # 3. arxiv-id старого формата: cs.AI/0504001
    m = _RE_ARXIV_OLD.match(тело)
    if m:
        return f"arxiv:{m.group(1).lower()}"

    # 4. Обычный DOI
    m = _RE_DOI.search(тело)
    if m:
        doi = m.group(0).lower().rstrip(".,;")
        return f"doi:{doi}"

    # 5. PMC-идентификатор
    m = re.search(r"pmc\d+", тело, re.IGNORECASE)
    if m:
        return f"pmc:{m.group(0).lower()}"

    # 6. Fallback — оригинальный doc_id в lowercase
    return s.lower()


def прочитать():
    if not os.path.exists(ФАЙЛ_СОСТОЯНИЯ):
        return _добавить_индексы(_значения_по_умолчанию())
    try:
        with open(ФАЙЛ_СОСТОЯНИЯ, "r", encoding="utf-8") as f:
            данные = json.load(f)
    except Exception:
        return _добавить_индексы(_значения_по_умолчанию())

    # Миграция со схемы v2 → v3: бэкфилл normalized_ids из downloaded_ids.
    if "normalized_ids" not in данные:
        данные["normalized_ids"] = []
        for did in данные.get("downloaded_ids", []):
            норм = нормализовать_doc_id(did)
            if норм and норм not in данные["normalized_ids"]:
                данные["normalized_ids"].append(норм)
        данные["version"] = 3
    # Миграция v3 → v4: добавить пустые domain_counts (без ретро-классификации,
    # она требует title/abstract которых нет в state.json — стартуем с нуля).
    if "domain_counts" not in данные:
        данные["domain_counts"] = {"chem": 0, "it": 0, "other": 0}
        данные["version"] = 4
    return _добавить_индексы(данные)


def _добавить_индексы(данные: dict) -> dict:
    """Кладёт в state множества для O(1) lookup'а уже скачанных id.

    Поля начинаются с подчёркивания и удаляются перед сохранением, чтобы
    не попасть в JSON. Без них `уже_скачан`/`пометить_скачанным` строили
    бы set(...) из списка на каждый вызов — O(n²) на полный harvest.
    """
    данные["_downloaded_set"] = set(данные.get("downloaded_ids") or ())
    данные["_normalized_set"] = set(данные.get("normalized_ids") or ())
    return данные


def сохранить(данные):
    parent = os.path.dirname(ФАЙЛ_СОСТОЯНИЯ)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # Внутренние индексы (set'ы) не сериализуем — они восстанавливаются на read.
    для_записи = {k: v for k, v in данные.items() if not k.startswith("_")}
    with _замок:
        # Атомарная запись
        врем = ФАЙЛ_СОСТОЯНИЯ + ".tmp"
        with open(врем, "w", encoding="utf-8") as f:
            json.dump(для_записи, f, ensure_ascii=False, indent=2)
        os.replace(врем, ФАЙЛ_СОСТОЯНИЯ)


def _получить_сет(состояние: dict, ключ_сета: str, ключ_списка: str) -> set:
    """Достаёт set из state, лениво подкачивая его из списка для старого state."""
    сет = состояние.get(ключ_сета)
    if isinstance(сет, set):
        return сет
    сет = set(состояние.get(ключ_списка) or ())
    состояние[ключ_сета] = сет
    return сет


def уже_скачан(состояние, doc_id):
    """True если документ уже скачан — проверяет и raw doc_id, и нормализованный ключ.

    Это даёт кросс-источниковый дедуп: arxiv:2304.12345 и openalex:10.48550/arxiv.2304.12345
    оба дадут normalized = arxiv:2304.12345, второй раз не скачается.
    """
    downloaded = _получить_сет(состояние, "_downloaded_set", "downloaded_ids")
    if doc_id in downloaded:
        return True
    норм = нормализовать_doc_id(doc_id)
    if not норм:
        return False
    normalized = _получить_сет(состояние, "_normalized_set", "normalized_ids")
    return норм in normalized


def пометить_скачанным(состояние, doc_id):
    if "downloaded_ids" not in состояние:
        состояние["downloaded_ids"] = []
    if "normalized_ids" not in состояние:
        состояние["normalized_ids"] = []
    downloaded = _получить_сет(состояние, "_downloaded_set", "downloaded_ids")
    normalized = _получить_сет(состояние, "_normalized_set", "normalized_ids")
    if doc_id not in downloaded:
        состояние["downloaded_ids"].append(doc_id)
        downloaded.add(doc_id)
    норм = нормализовать_doc_id(doc_id)
    if норм and норм not in normalized:
        состояние["normalized_ids"].append(норм)
        normalized.add(норм)


def залогировать(сообщение):
    os.makedirs(os.path.dirname(ФАЙЛ_ЛОГА), exist_ok=True)
    with _замок, open(ФАЙЛ_ЛОГА, "a", encoding="utf-8") as f:
        f.write(сообщение.rstrip() + "\n")
