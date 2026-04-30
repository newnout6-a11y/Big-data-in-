"""Semantic Scholar Graph API — свободный доступ к 200M+ публикациям с OA PDF.

https://api.semanticscholar.org/graph/v1/paper/search

Лимиты (без ключа): ~100 req/5min, rate limited через 429. С ключом
(SEMANTIC_SCHOLAR_API_KEY) — выше. Ключ опциональный, работает и без него.

Формат `openAccessPdf` в ответе:
  {"url": "https://....", "status": "green"}  — когда Semantic Scholar знает верифицированный OA PDF
  null                                         — когда его нет, пропускаем.
"""
from __future__ import annotations

import os
import time
from typing import Iterator

import httpx

from .arxiv import Документ


БАЗА = "https://api.semanticscholar.org/graph/v1/paper/search"

ПОЛЯ = "title,authors,year,openAccessPdf,abstract,externalIds,publicationDate"

ЗАПРОСЫ_ПО_УМОЛЧАНИЮ = [
    "machine learning chemistry",
    "graph neural network molecule",
    "cheminformatics property prediction",
    "density functional theory DFT",
    "retrosynthesis",
    "materials informatics",
    "drug discovery deep learning",
    "reinforcement learning robotics",
    "transformer language model efficient",
    "diffusion model image generation",
]


def _doi_или_id(paper: dict) -> str:
    """doc_id с приоритетом ArXiv → DOI → остальное.

    ArXiv раньше DOI потому что для arxiv-статей dedup идёт по arxiv-id,
    а DOI-алиас (10.48550/arXiv.XXXX) нормализатор всё равно сведёт к нему же,
    но быстрее выдавать сразу канонический вид.
    """
    ext = paper.get("externalIds") or {}
    for ключ in ("ArXiv", "DOI", "CorpusId", "MAG"):
        if ключ in ext and ext[ключ]:
            if ключ == "ArXiv":
                return f"arxiv:{ext[ключ]}"
            if ключ == "DOI":
                return f"semanticscholar:{ext[ключ]}"
            return f"semanticscholar:{ключ.lower()}:{ext[ключ]}"
    return f"semanticscholar:{paper.get('paperId', '')}"


def собрать(
    запрос: str,
    offset: int = 0,
    бюджет: int = 50,
    год_не_раньше: int | None = 2020,
    user_agent: str = "corpus-harvester/1.2",
    таймаут: float = 60.0,
    api_key: str | None = None,
) -> tuple[list[Документ], int]:
    """Возвращает (документы, новый_offset). Новый offset = старый + кол-во запрошенных."""
    заголовки = {"User-Agent": user_agent, "Accept": "application/json"}
    key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if key:
        заголовки["x-api-key"] = key

    клиент = httpx.Client(timeout=таймаут, headers=заголовки)
    собрано: list[Документ] = []
    текущий_offset = offset
    размер_страницы = min(100, бюджет)

    try:
        while len(собрано) < бюджет:
            осталось = бюджет - len(собрано)
            params = {
                "query": запрос,
                "offset": текущий_offset,
                "limit": min(размер_страницы, осталось, 100),
                "fields": ПОЛЯ,
                "openAccessPdf": "true",  # только с доступным PDF
            }
            if год_не_раньше:
                params["year"] = f"{год_не_раньше}-"

            try:
                ответ = клиент.get(БАЗА, params=params)
                if ответ.status_code == 429:
                    # Rate limit — ждём и пробуем ещё раз
                    time.sleep(10)
                    continue
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(2)
                break

            данные = ответ.json()
            результаты = данные.get("data") or []
            if not результаты:
                break

            for paper in результаты:
                oa = paper.get("openAccessPdf") or {}
                pdf_url = oa.get("url") if isinstance(oa, dict) else None
                if not pdf_url:
                    continue

                дата = paper.get("publicationDate") or str(paper.get("year") or "")
                if год_не_раньше and len(дата) >= 4 and дата[:4].isdigit():
                    if int(дата[:4]) < год_не_раньше:
                        continue

                авторы = [a.get("name", "").strip() for a in (paper.get("authors") or []) if a.get("name")]

                собрано.append(Документ(
                    источник="semanticscholar",
                    doc_id=_doi_или_id(paper),
                    название=(paper.get("title") or "").strip(),
                    авторы=авторы,
                    дата=дата[:10] if дата else "",
                    pdf_url=pdf_url,
                    abstract=(paper.get("abstract") or "").strip(),
                    категории=[],
                ))
                if len(собрано) >= бюджет:
                    break

            страница = len(результаты)
            текущий_offset += страница
            if страница < params["limit"]:
                break
            time.sleep(1.0)
    finally:
        клиент.close()

    return собрано, текущий_offset
