"""CORE v3 — крупнейший OA-агрегатор (130M+ документов).

https://api.core.ac.uk/v3/search/works

Требует API-ключ (бесплатный): https://core.ac.uk/services/api#what-is-included
Ставить в env CORE_API_KEY. Без ключа источник не активен (возвращает []).

Лимит free tier: 10 req/min, 1000/day. Этого хватает на пару десятков пакетов
в сутки — запускаем реже остальных источников.
"""
from __future__ import annotations

import os
import time

import httpx

from .arxiv import Документ


БАЗА = "https://api.core.ac.uk/v3/search/works"

ЗАПРОСЫ_ПО_УМОЛЧАНИЮ = [
    "cheminformatics",
    "molecular property prediction",
    "graph neural network chemistry",
    "materials informatics",
    "machine learning drug discovery",
    "high-performance computing",
    "natural language processing transformer",
    "computer vision neural network",
]


def _doc_id(work: dict) -> str:
    doi = (work.get("doi") or "").strip()
    if doi:
        return f"core:{doi.replace('https://doi.org/', '')}"
    arxiv_id = work.get("arxivId") or ""
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    id_num = work.get("id") or ""
    return f"core:{id_num}"


def собрать(
    запрос: str,
    offset: int = 0,
    бюджет: int = 50,
    год_не_раньше: int | None = 2020,
    user_agent: str = "corpus-harvester/1.2",
    таймаут: float = 60.0,
    api_key: str | None = None,
) -> tuple[list[Документ], int]:
    """Возвращает (документы, новый_offset)."""
    key = api_key or os.getenv("CORE_API_KEY", "").strip()
    if not key:
        # Нет ключа → молча выходим с 0 документами. В логах на уровне run.py
        # будет написано «core: бюджет 0» (если активировано) — пользователь
        # увидит что нечего качать и разберётся.
        return [], offset

    заголовки = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Authorization": f"Bearer {key}",
    }
    клиент = httpx.Client(timeout=таймаут, headers=заголовки)
    собрано: list[Документ] = []
    текущий_offset = offset
    страница = 0
    max_429_retries = 3
    retries_429 = 0

    # CORE позволяет уточнить выборку: fullText=true → есть PDF.
    q_parts = [запрос, "_exists_:fullText"]
    if год_не_раньше:
        q_parts.append(f"yearPublished>={год_не_раньше}")
    полный_запрос = " AND ".join(q_parts)

    try:
        while len(собрано) < бюджет:
            осталось = бюджет - len(собрано)
            params = {
                "q": полный_запрос,
                "offset": текущий_offset,
                "limit": min(100, осталось),
            }
            try:
                ответ = клиент.get(БАЗА, params=params)
                if ответ.status_code == 429:
                    # Дневная квота CORE = 1000 req/day, так что выходим после
                    # N ретраев, чтобы не крутиться бесконечно.
                    if retries_429 >= max_429_retries:
                        break
                    retries_429 += 1
                    time.sleep(10)
                    continue
                retries_429 = 0
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(2)
                break

            данные = ответ.json()
            работы = данные.get("results") or []
            if not работы:
                break

            for work in работы:
                # downloadUrl — прямая ссылка на OA PDF (если CORE его сохранил)
                pdf_url = (work.get("downloadUrl") or "").strip()
                if not pdf_url:
                    # fallback: ссылки в outputs
                    for out in work.get("outputs") or []:
                        if out.get("format", "").lower() == "pdf" and out.get("url"):
                            pdf_url = out["url"]
                            break
                if not pdf_url:
                    continue

                год = work.get("yearPublished") or 0
                if год_не_раньше and isinstance(год, int) and год > 0 and год < год_не_раньше:
                    continue
                дата = work.get("publishedDate") or (str(год) if год else "")

                авторы = [a.get("name", "").strip() for a in (work.get("authors") or []) if a.get("name")]

                собрано.append(Документ(
                    источник="core",
                    doc_id=_doc_id(work),
                    название=(work.get("title") or "").strip(),
                    авторы=авторы,
                    дата=дата[:10] if дата else "",
                    pdf_url=pdf_url,
                    abstract=(work.get("abstract") or "").strip(),
                    категории=[],
                ))
                if len(собрано) >= бюджет:
                    break

            размер_страницы = len(работы)
            текущий_offset += размер_страницы
            if размер_страницы < params["limit"]:
                break
            страница += 1
            time.sleep(6.5)  # free tier: 10 req/min → ~6 сек между запросами
    finally:
        клиент.close()

    return собрано, текущий_offset
