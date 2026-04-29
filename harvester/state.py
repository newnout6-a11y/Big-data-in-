"""Состояние харвестера: курсоры по источникам + список уже скачанных."""
import json
import os
import threading


_БАЗА = os.path.dirname(os.path.abspath(__file__))
ФАЙЛ_СОСТОЯНИЯ = os.path.join(_БАЗА, "state.json")
ФАЙЛ_ЛОГА = os.path.join(_БАЗА, "logs", "harvest.log")


_замок = threading.Lock()


def _значения_по_умолчанию():
    return {
        "version": 1,
        "sources": {
            "arxiv": {"last_index": 0, "last_run": None},
            "chemrxiv": {"skip": 0, "last_run": None},
            "openalex": {"cursors": {}, "last_run": None},
        },
        "downloaded_ids": [],
    }


def прочитать():
    if not os.path.exists(ФАЙЛ_СОСТОЯНИЯ):
        return _значения_по_умолчанию()
    try:
        with open(ФАЙЛ_СОСТОЯНИЯ, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _значения_по_умолчанию()


def сохранить(данные):
    os.makedirs(os.path.dirname(ФАЙЛ_СОСТОЯНИЯ), exist_ok=True) if os.path.dirname(ФАЙЛ_СОСТОЯНИЯ) else None
    with _замок:
        # Атомарная запись
        врем = ФАЙЛ_СОСТОЯНИЯ + ".tmp"
        with open(врем, "w", encoding="utf-8") as f:
            json.dump(данные, f, ensure_ascii=False, indent=2)
        os.replace(врем, ФАЙЛ_СОСТОЯНИЯ)


def уже_скачан(состояние, doc_id):
    return doc_id in set(состояние.get("downloaded_ids", []))


def пометить_скачанным(состояние, doc_id):
    if "downloaded_ids" not in состояние:
        состояние["downloaded_ids"] = []
    if doc_id not in состояние["downloaded_ids"]:
        состояние["downloaded_ids"].append(doc_id)


def залогировать(сообщение):
    os.makedirs(os.path.dirname(ФАЙЛ_ЛОГА), exist_ok=True)
    with _замок, open(ФАЙЛ_ЛОГА, "a", encoding="utf-8") as f:
        f.write(сообщение.rstrip() + "\n")
