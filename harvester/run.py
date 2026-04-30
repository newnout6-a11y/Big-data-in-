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
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx

from . import state
from . import домены
from .sources import (
    arxiv, chemrxiv, openalex, europepmc, cyberleninka, stackexchange,
    semantic_scholar, core_api, unpaywall,
)


_БАЗА = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ПАПКА_PDF = os.path.join(_БАЗА, "all_pdfs")
ПАПКА_МЕТА = os.path.join(_БАЗА, "harvested_meta")

ВСЕ_ИСТОЧНИКИ = [
    "arxiv", "chemrxiv", "openalex", "europepmc", "cyberleninka", "stackexchange",
    "semanticscholar", "core",
]


_ТРАНСЛИТ = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _слаг(текст: str, макс_длина: int = 80) -> str:
    """Транслитерирует кириллицу, чистит до [a-z0-9-], обрезает по слову."""
    if not текст:
        return ""
    т = текст.lower()
    т = "".join(_ТРАНСЛИТ.get(с, с) for с in т)
    т = unicodedata.normalize("NFKD", т)
    т = т.encode("ascii", "ignore").decode("ascii")
    т = re.sub(r"[^a-z0-9]+", "-", т).strip("-")
    if len(т) > макс_длина:
        обрез = т[:макс_длина]
        # Не разрываем слово
        if "-" in обрез:
            обрез = обрез.rsplit("-", 1)[0]
        т = обрез.strip("-")
    return т


def _безопасное_имя(
    doc_id: str,
    url: str = "",
    *,
    расширение: str | None = None,
    заголовок: str | None = None,
) -> str:
    """`<slug>__<short-doc-id>.pdf` — читаемо и уникально.
    Если заголовок пустой/нечитаемый — fallback на короткий хэш."""
    очищ = re.sub(r"[^A-Za-z0-9._-]+", "-", doc_id or "").strip("-")
    хэш12 = hashlib.sha1((doc_id or url).encode("utf-8")).hexdigest()[:12]
    if not очищ:
        короткий_doc = хэш12
    elif len(очищ) > 40:
        # url-style id: оставляем префикс источника + хэш для уникальности
        префикс = очищ[:25].strip("-") or "id"
        короткий_doc = f"{префикс}-{хэш12}"
    else:
        короткий_doc = очищ

    if расширение:
        суффикс = расширение
    else:
        суффикс = ".pdf"
        if url and "." in url.rsplit("/", 1)[-1]:
            кандидат = "." + url.rsplit(".", 1)[-1].split("?", 1)[0].lower()
            if кандидат in (".pdf", ".docx"):
                суффикс = кандидат

    слаг = _слаг(заголовок or "")
    if слаг:
        return f"{слаг}__{короткий_doc}{суффикс}"
    return f"{короткий_doc}{суффикс}"


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


def _печать(строка: str) -> None:
    """Печать в stdout с немедленным flush — чтобы видеть прогресс в .bat-окне."""
    print(строка, flush=True)


# Email, под которым Unpaywall/OpenAlex принимают запросы. Устанавливается
# в запустить() из args.email, читается в обработать_документ().
_ТЕКУЩИЙ_EMAIL = ""


def _извлечь_doi_из_doc_id(doc_id: str) -> str | None:
    """Если в doc_id зашит DOI (10.XXXX/...) — возвращает его без префикса.
    Используется только для Unpaywall-fallback'а."""
    if not doc_id:
        return None
    import re as _re
    m = _re.search(r"10\.\d{4,9}/[^\s]+", doc_id)
    if m:
        return m.group(0).rstrip(".,;")
    return None


def обработать_документ(док, состояние, клиент_pdf):
    if state.уже_скачан(состояние, док.doc_id):
        # Отдельно отметим если дубль пришёл из другого источника через
        # нормализованный ключ — это самый частый случай экономии трафика.
        норм = state.нормализовать_doc_id(док.doc_id)
        if док.doc_id not in состояние.get("downloaded_ids", []) and норм in состояние.get("normalized_ids", []):
            _печать(f"[{док.источник}] SKIP {док.doc_id} (кросс-источник дубль: {норм})")
        else:
            _печать(f"[{док.источник}] SKIP {док.doc_id} (уже скачан)")
        return False

    # Stack Exchange и подобные синтетические — без pdf_url, текст в abstract
    if not док.pdf_url and док.abstract:
        имя = _безопасное_имя(док.doc_id, "", расширение=".txt", заголовок=док.название)
        путь = os.path.join(ПАПКА_PDF, имя)
        os.makedirs(ПАПКА_PDF, exist_ok=True)
        with open(путь, "w", encoding="utf-8") as f:
            f.write(док.abstract)
        # Классификация домена — тот же путь что для PDF-документов.
        # Без неё stackexchange (IT-источник) не засчитывается в domain_counts
        # и балансировщик бюджетов думает что IT отстаёт → даёт IT лишний буст.
        домен = домены.классифицировать(
            источник=док.источник, название=док.название,
            abstract=док.abstract, doc_id=док.doc_id,
        )
        _сохранить_метадату(имя, {
            "doc_id": док.doc_id,
            "источник": док.источник,
            "название": док.название,
            "авторы": док.авторы,
            "дата": док.дата,
            "категории": док.категории,
            "домен": домен,
            "abstract": док.abstract[:500],
            "pdf_url": "",
            "файл": имя,
        })
        state.пометить_скачанным(состояние, док.doc_id)
        dc = состояние.setdefault("domain_counts", {"chem": 0, "it": 0, "other": 0})
        dc[домен] = dc.get(домен, 0) + 1
        state.залогировать(f"OK_TXT {док.doc_id} -> {имя}")
        _печать(f"[{док.источник}] OK   {имя} (домен: {домен})")
        return True

    if not док.pdf_url:
        _печать(f"[{док.источник}] SKIP {док.doc_id} (нет pdf_url)")
        return False

    имя = _безопасное_имя(док.doc_id, док.pdf_url, заголовок=док.название)
    путь = os.path.join(ПАПКА_PDF, имя)
    if os.path.exists(путь):
        state.пометить_скачанным(состояние, док.doc_id)
        _печать(f"[{док.источник}] SKIP {имя} (файл уже на диске)")
        return False
    _печать(f"[{док.источник}] GET  {имя} ← {док.pdf_url[:80]}")
    данные = _скачать_pdf(клиент_pdf, док.pdf_url)
    if not данные:
        # Unpaywall fallback: если в doc_id зашит DOI и есть email — просим
        # Unpaywall легальную OA-копию. Часто NEJM/Cell/Science paywall PDF
        # при этом доступны как authors' preprint на PMC или институте.
        email = _ТЕКУЩИЙ_EMAIL or os.environ.get("HARVESTER_EMAIL", "").strip()
        doi_для_unpaywall = _извлечь_doi_из_doc_id(док.doc_id)
        if doi_для_unpaywall and email:
            альт = unpaywall.найти_oa_pdf(doi_для_unpaywall, email=email)
            if альт and альт != док.pdf_url:
                _печать(f"[{док.источник}] UNPAYWALL {альт[:80]}")
                данные = _скачать_pdf(клиент_pdf, альт)
                if данные:
                    # Документ — dataclass, не NamedTuple: присваиваем напрямую,
                    # чтобы в метаданных pdf_url был рабочей ссылкой, а не упавшей
                    док.pdf_url = альт
        if not данные:
            state.залогировать(f"FAIL {док.doc_id} {док.pdf_url}")
            _печать(f"[{док.источник}] FAIL {док.doc_id}")
            return False
    os.makedirs(ПАПКА_PDF, exist_ok=True)
    with open(путь, "wb") as f:
        f.write(данные)
    # Классификация домена — для балансировки и для ingest-фильтров
    домен = домены.классифицировать(
        источник=док.источник, название=док.название,
        abstract=док.abstract, doc_id=док.doc_id,
    )
    _сохранить_метадату(имя, {
        "doc_id": док.doc_id,
        "источник": док.источник,
        "название": док.название,
        "авторы": док.авторы,
        "дата": док.дата,
        "категории": док.категории,
        "домен": домен,
        "abstract": док.abstract[:500],
        "pdf_url": док.pdf_url,
        "файл": имя,
    })
    state.пометить_скачанным(состояние, док.doc_id)
    # Инкремент счётчика домена — для последующих балансировочных коэффициентов
    dc = состояние.setdefault("domain_counts", {"chem": 0, "it": 0, "other": 0})
    dc[домен] = dc.get(домен, 0) + 1
    state.залогировать(f"OK {док.doc_id} -> {имя}")
    _печать(f"[{док.источник}] OK   {имя} ({len(данные)//1024} КБ, домен: {домен})")
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


def _собрать_semanticscholar(args, состояние, клиент_pdf, бюджет):
    """Semantic Scholar API по списку запросов с per-query offset."""
    конф = состояние["sources"].setdefault("semanticscholar", {"offsets": {}, "last_run": None})
    скачано = 0
    запросы = semantic_scholar.ЗАПРОСЫ_ПО_УМОЛЧАНИЮ
    на_запрос = max(1, бюджет // len(запросы))
    for q in запросы:
        offset = конф["offsets"].get(q, 0)
        print(f"[semanticscholar] '{q[:30]}' бюджет {на_запрос}, offset {offset}")
        доки, новый = semantic_scholar.собрать(
            запрос=q, offset=offset, бюджет=на_запрос,
            год_не_раньше=args.year_min, user_agent=_ua(args),
        )
        for док in доки:
            if обработать_документ(док, состояние, клиент_pdf):
                скачано += 1
        конф["offsets"][q] = новый
    конф["last_run"] = _сейчас()
    return скачано


def _собрать_core(args, состояние, клиент_pdf, бюджет):
    """CORE API — требует CORE_API_KEY в env. Без ключа бесшумно пропускает."""
    if not os.getenv("CORE_API_KEY", "").strip():
        print("[core] пропущено: задай ENV CORE_API_KEY (https://core.ac.uk/services/api#what-is-included)")
        return 0
    конф = состояние["sources"].setdefault("core", {"offsets": {}, "last_run": None})
    скачано = 0
    запросы = core_api.ЗАПРОСЫ_ПО_УМОЛЧАНИЮ
    на_запрос = max(1, бюджет // len(запросы))
    for q in запросы:
        offset = конф["offsets"].get(q, 0)
        print(f"[core] '{q[:30]}' бюджет {на_запрос}, offset {offset}")
        доки, новый = core_api.собрать(
            запрос=q, offset=offset, бюджет=на_запрос,
            год_не_раньше=args.year_min, user_agent=_ua(args),
        )
        for док in доки:
            if обработать_документ(док, состояние, клиент_pdf):
                скачано += 1
        конф["offsets"][q] = новый
    конф["last_run"] = _сейчас()
    return скачано


СБОРЩИКИ = {
    "arxiv": _собрать_arxiv,
    "chemrxiv": _собрать_chemrxiv,
    "openalex": _собрать_openalex,
    "europepmc": _собрать_europepmc,
    "cyberleninka": _собрать_cyberleninka,
    "stackexchange": _собрать_stackexchange,
    "semanticscholar": _собрать_semanticscholar,
    "core": _собрать_core,
}


def запустить(args):
    global _ТЕКУЩИЙ_EMAIL
    _ТЕКУЩИЙ_EMAIL = (args.email or "").strip()

    источники = [s.strip() for s in args.sources.split(",") if s.strip()]
    неизвестные = [s for s in источники if s not in СБОРЩИКИ]
    if неизвестные:
        print(f"Неизвестные источники: {неизвестные}. Доступны: {list(СБОРЩИКИ)}")
        return 2

    состояние = state.прочитать()
    # Браузерные заголовки повышают шансы пройти Cloudflare/CF-капчи
    # (КиберЛенинка, NEJM, Cell и т.п.). На честных научных эндпоинтах не мешает.
    клиент_pdf = httpx.Client(
        timeout=120,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "Referer": "https://www.google.com/",
            "X-Harvester-Email": args.email or "unknown",
        },
    )

    # Топик-балансировка: считаем мультипликаторы бюджета исходя из текущего
    # распределения доменов в state. Если chem отстаёт — chem-источники получают
    # бюджет больше, it-источники меньше. При пустом state все по 1.0.
    counts = состояние.get("domain_counts", {})
    коэф_домен = домены.рассчитать_коэффициенты(counts)
    print(f"[balance] счётчики {counts} → коэф {коэф_домен}")

    базовый = max(1, args.budget // len(источники))
    весы: list[float] = []
    for и in источники:
        ожидаемый = домены.ИСТОЧНИК_ОЖИДАЕМЫЙ_ДОМЕН.get(и, "other")
        весы.append(коэф_домен.get(ожидаемый, 1.0))
    сумма_весов = sum(весы) or 1.0
    бюджеты_per: dict[str, int] = {}
    общий = args.budget
    for и, в in zip(источники, весы):
        бюджеты_per[и] = max(1, int(общий * в / сумма_весов))

    итог = 0
    дедлайн = time.time() + args.time_limit_min * 60 if args.time_limit_min else None

    for и in источники:
        if дедлайн and time.time() > дедлайн:
            print(f"Достигнут лимит времени, остановка перед {и}")
            break
        try:
            n = СБОРЩИКИ[и](args, состояние, клиент_pdf, бюджеты_per[и])
            итог += n
            print(f"  → {и}: скачано {n} (бюджет {бюджеты_per[и]})")
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
