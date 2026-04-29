"""Оркестратор харвестера: собирает PDF/тексты из всех источников.

Использование:
    python -m harvester.run --budget 500 [--sources arxiv,openalex,europepmc,...]

Источники:
  - arxiv         (cs.LG, physics.chem-ph, ...)
  - chemrxiv      (PDF JSON API; CF может блокировать с CI-IP)
  - openalex      (concepts: cheminformatics, ML, chemistry, materials, CS)
  - europepmc     (полные тексты медбио + смежная химия)
  - cyberleninka  (RU OAI-PMH; PDF могут блокироваться CDN)
  - stackexchange (Q+top answer как .txt)

Складывает PDF/.txt в all_pdfs/, метаданные — в harvested_meta/. State в
harvester/state.json. Все источники инкрементальны.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import state
from .sources import arxiv, chemrxiv, openalex, europepmc, cyberleninka, stackexchange


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКА_PDF = os.path.join(_БАЗА, "all_pdfs")
ПАПКА_МЕТА = os.path.join(_БАЗА, "harvested_meta")

ВСЕ_ИСТОЧНИКИ = ["arxiv", "chemrxiv", "openalex", "europepmc", "cyberleninka", "stackexchange"]


def _безопасное_имя(doc_id: str, url: str, *, расширение: str | None = None) -> str:
    хэш = hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:16]
    if расширение:
        return хэш + расширение
    суффикс = ".pdf"
    if url and "." in url.rsplit("/", 1)[-1]:
        кандидат = "." + url.rsplit(".", 1)[-1].split("?", 1)[0].lower()
        if кандидат in (".pdf", ".docx"):
            суффикс = кандидат
    return хэш + суффикс


def _сохранить_метадату(имя_файла, payload):
    os.makedirs(ПАПКА_МЕТА, exist_ok=True)
    основание, _ = os.path.splitext(имя_файла)
    путь = os.path.join(ПАПКА_МЕТА, основание + ".json")
    with open(путь, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _скачать_pdf(клиент, url):
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

    # Stack Exchange и подобные синтетические — без pdf_url, текст в abstract
    if not док.pdf_url and док.abstract:
        имя = _безопасное_имя(док.doc_id, "", расширение=".txt")
        путь = os.path.join(ПАПКА_PDF, имя)
        os.makedirs(ПАПКА_PDF, exist_ok=True)
        with open(путь, "w", encoding="utf-8") as f:
            f.write(док.abstract)
        _сохранить_метадату(имя, {
            "doc_id": док.doc_id,
            "источник": док.источник,
            "название": док.название,
            "авторы": док.авторы,
            "дата": док.дата,
            "категории": док.категории,
            "abstract": док.abstract[:500],
            "pdf_url": "",
            "файл": имя,
        })
        state.пометить_скачанным(состояние, док.doc_id)
        state.залогировать(f"OK_TXT {док.doc_id} -> {имя}")
        return True

    if not док.pdf_url:
        return False

    имя = _безопасное_имя(док.doc_id, док.pdf_url)
    путь = os.path.join(ПАПКА_PDF, имя)
    if os.path.exists(путь):
        state.пометить_скачанным(состояние, док.doc_id)
        return False
    данные = _скачать_pdf(клиент_pdf, док.pdf_url)
    if not данные:
        state.залогировать(f"FAIL {док.doc_id} {док.pdf_url}")
        return False
    os.makedirs(ПАПКА_PDF, exist_ok=True)
    with open(путь, "wb") as f:
        f.write(данные)
    _сохранить_метадату(имя, {
        "doc_id": док.doc_id,
        "источник": док.источник,
        "название": док.название,
        "авторы": док.авторы,
        "дата": док.дата,
        "категории": док.категории,
        "abstract": док.abstract[:500],
        "pdf_url": док.pdf_url,
        "файл": имя,
    })
    state.пометить_скачанным(состояние, док.doc_id)
    state.залогировать(f"OK {док.doc_id} -> {имя}")
    return True


def _ua(args):
    return f"corpus-harvester/1.1 ({args.email or 'unknown'})"


def _распределить_бюджет(всего, источники):
    """Поровну, но не меньше 1 на источник."""
    if not источники:
        return {}
    доля = max(1, всего // len(источники))
    return {и: доля for и in источники}


def _собрать_arxiv(args, состояние, клиент_pdf, бюджет):
    print(f"[arxiv] бюджет {бюджет}, начало {состояние['sources']['arxiv']['last_index']}")
    с = состояние["sources"]["arxiv"]["last_index"]
    собрано = 0
    скачано = 0
    for док in arxiv.собрать(начало=с, бюджет=бюджет, год_не_раньше=args.year_min, user_agent=_ua(args)):
        if обработать_документ(док, состояние, клиент_pdf):
            скачано += 1
        собрано += 1
    состояние["sources"]["arxiv"]["last_index"] = с + собрано
    состояние["sources"]["arxiv"]["last_run"] = _сейчас()
    return скачано


def _собрать_chemrxiv(args, состояние, клиент_pdf, бюджет):
    print(f"[chemrxiv] бюджет {бюджет}, skip {состояние['sources']['chemrxiv']['skip']}")
    с = состояние["sources"]["chemrxiv"]["skip"]
    собрано = 0
    скачано = 0
    for док in chemrxiv.собрать(skip=с, бюджет=бюджет, год_не_раньше=args.year_min, user_agent=_ua(args)):
        if обработать_документ(док, состояние, клиент_pdf):
            скачано += 1
        собрано += 1
    состояние["sources"]["chemrxiv"]["skip"] = с + собрано
    состояние["sources"]["chemrxiv"]["last_run"] = _сейчас()
    return скачано


def _собрать_openalex(args, состояние, клиент_pdf, бюджет):
    if not args.email:
        print("[openalex] пропущено: задай --email или ENV HARVESTER_EMAIL")
        return 0
    скачано = 0
    на_концепт = max(1, бюджет // len(openalex.КОНЦЕПТЫ_ПО_УМОЛЧАНИЮ))
    for концепт_ид, имя in openalex.КОНЦЕПТЫ_ПО_УМОЛЧАНИЮ.items():
        cursor = состояние["sources"]["openalex"]["cursors"].get(концепт_ид, "*")
        print(f"[openalex/{имя}] бюджет {на_концепт}, cursor {cursor[:24]}…")
        доки, новый = openalex.собрать(
            концепт=концепт_ид, cursor=cursor, бюджет=на_концепт,
            год_не_раньше=args.year_min, email=args.email,
        )
        for док in доки:
            if обработать_документ(док, состояние, клиент_pdf):
                скачано += 1
        состояние["sources"]["openalex"]["cursors"][концепт_ид] = новый or "*"
    состояние["sources"]["openalex"]["last_run"] = _сейчас()
    return скачано


def _собрать_europepmc(args, состояние, клиент_pdf, бюджет):
    """Идём по списку запросов с per-query cursor."""
    если_кэш = состояние["sources"].setdefault("europepmc", {"cursors": {}, "last_run": None})
    скачано = 0
    запросы = europepmc.ЗАПРОСЫ_ПО_УМОЛЧАНИЮ
    на_запрос = max(1, бюджет // len(запросы))
    for q in запросы:
        cursor = если_кэш["cursors"].get(q, "*")
        print(f"[europepmc] '{q[:30]}' бюджет {на_запрос}")
        доки, новый = europepmc.собрать(
            запрос=q, cursor=cursor, бюджет=на_запрос,
            год_не_раньше=args.year_min, user_agent=_ua(args),
        )
        for док in доки:
            if обработать_документ(док, состояние, клиент_pdf):
                скачано += 1
        если_кэш["cursors"][q] = новый or "*"
    если_кэш["last_run"] = _сейчас()
    return скачано


def _собрать_cyberleninka(args, состояние, клиент_pdf, бюджет):
    """Сдвигается по дням от args.year_min до сегодня, по 1 дню за прогон."""
    конф = состояние["sources"].setdefault(
        "cyberleninka",
        {"current_date": f"{args.year_min}-01-01", "last_run": None},
    )
    тек = конф["current_date"]
    if not тек or len(тек) < 10:
        тек = f"{args.year_min}-01-01"
    дата = datetime.fromisoformat(тек).replace(tzinfo=timezone.utc)
    конец = datetime.now(timezone.utc) - timedelta(days=1)
    скачано = 0
    окно_дней = max(1, min(7, бюджет // 50))  # 50 записей/день примерно
    while скачано < бюджет and дата < конец:
        from_ = дата.strftime("%Y-%m-%d")
        until = (дата + timedelta(days=окно_дней)).strftime("%Y-%m-%d")
        print(f"[cyberleninka] {from_} → {until}")
        доки, _ = cyberleninka.собрать(
            from_date=from_, until_date=until,
            бюджет=min(100, бюджет - скачано), user_agent=_ua(args),
        )
        for док in доки:
            if обработать_документ(док, состояние, клиент_pdf):
                скачано += 1
        дата = дата + timedelta(days=окно_дней)
    конф["current_date"] = дата.strftime("%Y-%m-%d")
    конф["last_run"] = _сейчас()
    return скачано


def _собрать_stackexchange(args, состояние, клиент_pdf, бюджет):
    конф = состояние["sources"].setdefault("stackexchange", {"sites": {}, "last_run": None})
    скачано = 0
    сайты = stackexchange.САЙТЫ_ПО_УМОЛЧАНИЮ
    на_сайт = max(1, бюджет // len(сайты))
    for сайт in сайты:
        стр = конф["sites"].get(сайт, 1)
        print(f"[stackexchange/{сайт}] бюджет {на_сайт}, страница {стр}")
        доки, новая = stackexchange.собрать(
            site=сайт, page=стр, бюджет=на_сайт, год_не_раньше=args.year_min, user_agent=_ua(args),
        )
        for док in доки:
            if обработать_документ(док, состояние, клиент_pdf):
                скачано += 1
        конф["sites"][сайт] = новая or стр
    конф["last_run"] = _сейчас()
    return скачано


def _сейчас():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


СБОРЩИКИ = {
    "arxiv": _собрать_arxiv,
    "chemrxiv": _собрать_chemrxiv,
    "openalex": _собрать_openalex,
    "europepmc": _собрать_europepmc,
    "cyberleninka": _собрать_cyberleninka,
    "stackexchange": _собрать_stackexchange,
}


def запустить(args):
    источники = [s.strip() for s in args.sources.split(",") if s.strip()]
    неизвестные = [s for s in источники if s not in СБОРЩИКИ]
    if неизвестные:
        print(f"Неизвестные источники: {неизвестные}. Доступны: {list(СБОРЩИКИ)}")
        return 2

    состояние = state.прочитать()
    клиент_pdf = httpx.Client(
        timeout=120,
        headers={"User-Agent": _ua(args)},
    )

    бюджет_per = max(1, args.budget // len(источники))
    итог = 0
    дедлайн = time.time() + args.time_limit_min * 60 if args.time_limit_min else None

    for и in источники:
        if дедлайн and time.time() > дедлайн:
            print(f"Достигнут лимит времени, остановка перед {и}")
            break
        try:
            n = СБОРЩИКИ[и](args, состояние, клиент_pdf, бюджет_per)
            итог += n
            print(f"  → {и}: скачано {n}")
        except Exception as e:
            print(f"  → {и}: ОШИБКА {type(e).__name__}: {e}")
            state.залогировать(f"ERR {и} {type(e).__name__}: {e}")
        state.сохранить(состояние)

    клиент_pdf.close()
    print(f"\nИтого скачано: {итог}")
    print(f"Папка: {ПАПКА_PDF}")
    print(f"Дальше: python ingest_v2.py && python embed_resume_v2.py")
    return 0


def main(argv=None):
    парсер = argparse.ArgumentParser(description="Harvester — автосбор PDF/текстов под scope химия+IT.")
    парсер.add_argument("--budget", type=int, default=300, help="Сколько документов в этом прогоне (≈/N на источник)")
    парсер.add_argument("--year-min", type=int, default=2020, help="Минимальный год публикации")
    парсер.add_argument("--email", type=str, default=os.getenv("HARVESTER_EMAIL", ""), help="Email для User-Agent (требуется OpenAlex)")
    парсер.add_argument("--sources", type=str, default=",".join(ВСЕ_ИСТОЧНИКИ), help="Список источников через запятую")
    парсер.add_argument("--time-limit-min", type=int, default=0, help="Лимит времени в минутах (0 — без лимита)")
    args = парсер.parse_args(argv)
    return запустить(args)


if __name__ == "__main__":
    sys.exit(main())
