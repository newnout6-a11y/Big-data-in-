"""Оркестратор харвестера: собирает PDF из всех источников по бюджету.

Использование:
    python -m harvester.run --budget 500 --year-min 2020

Складывает PDF в all_pdfs/ (как и текущий ингест), записывает прогресс в
state.json. Не парсит и не эмбеддит — этим занимаются ingest.py / embed_resume.py.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

import httpx

from .sources import arxiv, chemrxiv, openalex
from . import state


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКА_PDF = os.path.join(_БАЗА, "all_pdfs")
ПАПКА_МЕТА = os.path.join(_БАЗА, "harvested_meta")


def _безопасное_имя(doc_id: str, url: str) -> str:
    хэш = hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:16]
    суффикс = ".pdf"
    if url and "." in url.rsplit("/", 1)[-1]:
        расш = "." + url.rsplit(".", 1)[-1].split("?", 1)[0].lower()
        if расш in (".pdf", ".docx"):
            суффикс = расш
    return хэш + суффикс


def _сохранить_метадату(doc_id, payload):
    os.makedirs(ПАПКА_МЕТА, exist_ok=True)
    хэш = hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:16]
    путь = os.path.join(ПАПКА_МЕТА, хэш + ".json")
    import json
    with open(путь, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _скачать(клиент, url):
    try:
        r = клиент.get(url, follow_redirects=True)
        if r.status_code != 200:
            return None
        ct = r.headers.get("content-type", "").lower()
        if "pdf" not in ct and not url.lower().endswith(".pdf"):
            return None
        return r.content
    except Exception:
        return None


def обработать_документ(док, состояние, клиент_pdf):
    if state.уже_скачан(состояние, док.doc_id):
        return False
    путь = os.path.join(ПАПКА_PDF, _безопасное_имя(док.doc_id, док.pdf_url))
    if os.path.exists(путь):
        state.пометить_скачанным(состояние, док.doc_id)
        return False
    данные = _скачать(клиент_pdf, док.pdf_url)
    if not данные:
        state.залогировать(f"FAIL {док.doc_id} {док.pdf_url}")
        return False
    os.makedirs(ПАПКА_PDF, exist_ok=True)
    with open(путь, "wb") as f:
        f.write(данные)
    _сохранить_метадату(док.doc_id, {
        "doc_id": док.doc_id,
        "источник": док.источник,
        "название": док.название,
        "авторы": док.авторы,
        "дата": док.дата,
        "категории": док.категории,
        "abstract": док.abstract,
        "pdf_url": док.pdf_url,
        "файл": os.path.basename(путь),
    })
    state.пометить_скачанным(состояние, док.doc_id)
    state.залогировать(f"OK {док.doc_id} -> {os.path.basename(путь)}")
    return True


def запустить(args):
    состояние = state.прочитать()
    клиент_pdf = httpx.Client(
        timeout=120,
        headers={"User-Agent": f"corpus-harvester/1.0 ({args.email or 'unknown'})"},
    )

    бюджет_на_источник = max(1, args.budget // 3)
    скачано_всего = 0

    # --- arXiv ---
    print(f"[arxiv] бюджет {бюджет_на_источник}, начало {состояние['sources']['arxiv']['last_index']}")
    с_arxiv = состояние["sources"]["arxiv"]["last_index"]
    собрано_arxiv = 0
    for док in arxiv.собрать(начало=с_arxiv, бюджет=бюджет_на_источник, год_не_раньше=args.year_min,
                              user_agent=f"corpus-harvester/1.0 ({args.email or 'unknown'})"):
        if обработать_документ(док, состояние, клиент_pdf):
            скачано_всего += 1
        собрано_arxiv += 1
    состояние["sources"]["arxiv"]["last_index"] = с_arxiv + собрано_arxiv
    состояние["sources"]["arxiv"]["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state.сохранить(состояние)

    # --- chemRxiv ---
    print(f"[chemrxiv] бюджет {бюджет_на_источник}, skip {состояние['sources']['chemrxiv']['skip']}")
    с_chem = состояние["sources"]["chemrxiv"]["skip"]
    собрано_chem = 0
    for док in chemrxiv.собрать(skip=с_chem, бюджет=бюджет_на_источник, год_не_раньше=args.year_min,
                                  user_agent=f"corpus-harvester/1.0 ({args.email or 'unknown'})"):
        if обработать_документ(док, состояние, клиент_pdf):
            скачано_всего += 1
        собрано_chem += 1
    состояние["sources"]["chemrxiv"]["skip"] = с_chem + собрано_chem
    состояние["sources"]["chemrxiv"]["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state.сохранить(состояние)

    # --- OpenAlex (по концептам) ---
    if args.email:
        for концепт_ид, имя in openalex.КОНЦЕПТЫ_ПО_УМОЛЧАНИЮ.items():
            cursor = состояние["sources"]["openalex"]["cursors"].get(концепт_ид, "*")
            print(f"[openalex/{имя}] бюджет {max(1, бюджет_на_источник // 5)}, cursor {cursor[:32]}…")
            доки, новый = openalex.собрать(
                концепт=концепт_ид,
                cursor=cursor,
                бюджет=max(1, бюджет_на_источник // 5),
                год_не_раньше=args.year_min,
                email=args.email,
            )
            for док in доки:
                if обработать_документ(док, состояние, клиент_pdf):
                    скачано_всего += 1
            состояние["sources"]["openalex"]["cursors"][концепт_ид] = новый or "*"
            state.сохранить(состояние)
        состояние["sources"]["openalex"]["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state.сохранить(состояние)
    else:
        print("[openalex] пропущено: для OpenAlex рекомендуется задать --email")

    клиент_pdf.close()
    print(f"\nИтого скачано в этом прогоне: {скачано_всего}")
    print(f"Папка: {ПАПКА_PDF}")
    print(f"Дальше: python ingest_доп.py && python embed_resume.py")
    return 0


def main(argv=None):
    парсер = argparse.ArgumentParser(description="Harvester — автосбор PDF под scope химия+IT.")
    парсер.add_argument("--budget", type=int, default=300, help="Сколько документов скачать в этом прогоне (≈/3 на источник)")
    парсер.add_argument("--year-min", type=int, default=2020, help="Минимальный год публикации")
    парсер.add_argument("--email", type=str, default=os.getenv("HARVESTER_EMAIL", ""), help="Email для User-Agent (требуется OpenAlex)")
    args = парсер.parse_args(argv)
    return запустить(args)


if __name__ == "__main__":
    sys.exit(main())
