"""arXiv: Atom API.

https://export.arxiv.org/api/query

Категории под наш scope (химия + IT + пересечение):
  cs.LG, cs.AI, cs.CL, cs.CV, cs.IR, stat.ML  — IT/ML
  physics.chem-ph                             — химия
  cond-mat.mtrl-sci                           — материалы
  q-bio.BM, q-bio.QM                          — биохимия/мед
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import httpx


КАТЕГОРИИ_ПО_УМОЛЧАНИЮ = [
    "cs.LG",
    "cs.AI",
    "cs.CL",
    "stat.ML",
    "physics.chem-ph",
    "cond-mat.mtrl-sci",
    "q-bio.BM",
    "q-bio.QM",
]

_NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


@dataclass
class Документ:
    источник: str
    doc_id: str
    название: str
    авторы: list[str]
    дата: str  # YYYY-MM-DD
    pdf_url: str
    abstract: str
    категории: list[str]


def _построить_запрос(категории, начало, размер):
    cats = " OR ".join(f"cat:{c}" for c in категории)
    params = {
        "search_query": cats,
        "start": начало,
        "max_results": размер,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return "https://export.arxiv.org/api/query?" + urlencode(params)


def собрать(
    категории: list[str] | None = None,
    начало: int = 0,
    бюджет: int = 200,
    размер_страницы: int = 100,
    год_не_раньше: int | None = 2020,
    user_agent: str = "corpus-harvester/1.0",
    таймаут: float = 60.0,
) -> Iterator[Документ]:
    """Итератор по свежим записям arXiv.

    `начало` — смещение от верхушки выдачи (будет мутироваться вызывающим, чтобы
    инкрементально сдвигаться).
    """
    if категории is None:
        категории = КАТЕГОРИИ_ПО_УМОЛЧАНИЮ
    отдано = 0
    смещение = начало
    клиент = httpx.Client(timeout=таймаут, headers={"User-Agent": user_agent})
    try:
        while отдано < бюджет:
            к_странице = min(размер_страницы, бюджет - отдано)
            url = _построить_запрос(категории, смещение, к_странице)
            try:
                ответ = клиент.get(url)
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(3)
                break
            корень = ET.fromstring(ответ.text)
            записи = корень.findall("a:entry", _NS)
            if not записи:
                break
            for з in записи:
                arxiv_id_el = з.find("a:id", _NS)
                назв_el = з.find("a:title", _NS)
                опубл_el = з.find("a:published", _NS)
                summ_el = з.find("a:summary", _NS)
                if arxiv_id_el is None or назв_el is None:
                    continue
                arxiv_id = arxiv_id_el.text.strip().rsplit("/", 1)[-1]
                дата = (опубл_el.text[:10] if опубл_el is not None and опубл_el.text else "")
                if год_не_раньше and дата and int(дата[:4]) < год_не_раньше:
                    continue
                pdf_url = ""
                for ссылка in з.findall("a:link", _NS):
                    if ссылка.get("type") == "application/pdf":
                        pdf_url = ссылка.get("href", "")
                        break
                if not pdf_url:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                авторы = [a.findtext("a:name", default="", namespaces=_NS).strip()
                          for a in з.findall("a:author", _NS)]
                категории_стат = [
                    к.get("term", "")
                    for к in з.findall("a:category", _NS)
                ]
                yield Документ(
                    источник="arxiv",
                    doc_id=f"arxiv:{arxiv_id}",
                    название=(назв_el.text or "").strip().replace("\n", " "),
                    авторы=авторы,
                    дата=дата,
                    pdf_url=pdf_url,
                    abstract=(summ_el.text or "").strip() if summ_el is not None else "",
                    категории=категории_стат,
                )
                отдано += 1
                if отдано >= бюджет:
                    break
            смещение += к_странице
            time.sleep(3.0)  # arXiv требует ≥3 сек между запросами
    finally:
        клиент.close()


def следующий_курсор(текущий: int, прошло: int) -> int:
    return текущий + прошло
