"""Stack Exchange API: вопросы + лучшие ответы по релевантным сайтам.

API: https://api.stackexchange.com/docs/questions
Без ключа лимит 10000 запросов в день, по 100 элементов на запрос.

Сайты под наш scope: chemistry, ai, datascience, cs, stackoverflow.
Возвращаем не PDF, а синтетический документ (Q+best answer как plain text).
Сохраняется в all_pdfs/ как .txt; ингест поддерживает .txt с PR #2.
"""
from __future__ import annotations

import html
import re
import time
from typing import Iterator

import httpx

from .arxiv import Документ


БАЗА = "https://api.stackexchange.com/2.3"

САЙТЫ_ПО_УМОЛЧАНИЮ = [
    # химия и около-химия
    "chemistry",
    "physics",
    "biology",
    # AI / ML / data
    "ai",
    "datascience",
    "stats",
    # general CS / math
    "cs",
    "math",
    "mathoverflow",
    "cstheory",
    "scicomp",
    # softdev
    "stackoverflow",
    "codereview",
]


_HTML_TAG = re.compile(r"<[^>]+>")
_PRE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL)


def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = _PRE.sub(lambda m: "\n```\n" + html.unescape(_HTML_TAG.sub("", m.group(1))) + "\n```\n", s)
    s = _HTML_TAG.sub("", s)
    return html.unescape(s).strip()


def собрать(
    site: str,
    page: int = 1,
    бюджет: int = 50,
    год_не_раньше: int | None = 2020,
    user_agent: str = "corpus-harvester/1.0",
    таймаут: float = 60.0,
) -> tuple[list[Документ], int | None]:
    """Возвращает (документы, следующая_страница).

    documents: каждый — синтетический «текстовый PDF», поле pdf_url пустое;
    оркестратор должен сохранять `abstract` (там Q+A) как .txt файл.
    """
    клиент = httpx.Client(timeout=таймаут, headers={"User-Agent": user_agent})
    собрано: list[Документ] = []
    тек_страница = page
    осталось = бюджет
    try:
        while осталось > 0:
            размер = min(100, осталось)
            params = {
                "site": site,
                "page": тек_страница,
                "pagesize": размер,
                "order": "desc",
                "sort": "votes",
                "filter": "withbody",
            }
            # fromdate работает только при sort=creation/activity, не при votes
            try:
                ответ = клиент.get(БАЗА + "/questions", params=params)
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(2)
                break
            данные = ответ.json()
            элементы = данные.get("items", [])
            if not элементы:
                return собрано, None
            ids_for_answers = [str(q.get("accepted_answer_id")) for q in элементы if q.get("accepted_answer_id")]
            ответы_map: dict[int, str] = {}
            if ids_for_answers:
                try:
                    о = клиент.get(
                        БАЗА + "/answers/" + ";".join(ids_for_answers),
                        params={"site": site, "filter": "withbody", "pagesize": 100},
                    )
                    о.raise_for_status()
                    for a in о.json().get("items", []):
                        ответы_map[a.get("question_id")] = _strip_html(a.get("body", ""))
                except httpx.HTTPError:
                    pass
            for q in элементы:
                qid = q.get("question_id")
                заголовок = q.get("title", "")
                тело = _strip_html(q.get("body", ""))
                ответ_текст = ответы_map.get(qid, "")
                полный_текст = (
                    f"# {заголовок}\n\n"
                    f"## Question\n\n{тело}\n\n"
                    + (f"## Top Answer\n\n{ответ_текст}\n" if ответ_текст else "")
                )
                from datetime import datetime, timezone
                ts = q.get("creation_date", 0)
                дата = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""
                собрано.append(Документ(
                    источник=f"stackexchange:{site}",
                    doc_id=f"se:{site}:{qid}",
                    название=заголовок,
                    авторы=[(q.get("owner") or {}).get("display_name", "")],
                    дата=дата,
                    pdf_url="",  # синтетический контент, не файл
                    abstract=полный_текст,
                    категории=q.get("tags", []),
                ))
                осталось -= 1
                if осталось <= 0:
                    break
            if not данные.get("has_more", False):
                return собрано, None
            тек_страница += 1
            if данные.get("backoff"):
                time.sleep(int(данные["backoff"]) + 1)
            time.sleep(0.5)
    finally:
        клиент.close()
    return собрано, тек_страница
