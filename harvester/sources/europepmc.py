"""Europe PMC: REST search для OA full-text.

https://europepmc.org/RestfulWebService

Запрос вернёт PMCID и список ссылок (включая PDF). Фильтр на OA + год.
"""
from __future__ import annotations

import time

import httpx

from .arxiv import Документ


БАЗА = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

ЗАПРОСЫ_ПО_УМОЛЧАНИЮ = [
    "cheminformatics",
    "molecular property prediction",
    "drug discovery machine learning",
    "DFT density functional theory",
    "graph neural network molecule",
    "materials informatics",
    "high-throughput screening chemistry",
    "retrosynthesis machine learning",
    "transformer molecular generation",
    "protein structure prediction",
    "big data chemistry",
    "machine learning catalysis",
    "deep learning materials discovery",
    "quantum chemistry neural network",
    "crystal structure prediction",
    "molecular dynamics simulation",
    "reaction prediction machine learning",
    "de novo drug design",
    "QSAR machine learning",
    "docking deep learning",
    "chemical reaction networks",
    "biomarker discovery",
    "omics data integration",
    "single cell RNA-seq",
    "bioinformatics pipeline",
    "natural language processing biomedical",
    "AI radiology",
    "clinical decision support machine learning",
    "federated learning healthcare",
    "explainable AI medicine",
]


def _выбрать_pdf(результат: dict) -> str | None:
    список = (результат.get("fullTextUrlList") or {}).get("fullTextUrl", [])
    кандидаты = [
        х for х in список
        if х.get("documentStyle", "").lower() == "pdf"
    ]
    open_access = [х for х in кандидаты if х.get("availability", "").lower().startswith("open")]
    if open_access:
        return open_access[0].get("url")
    if кандидаты:
        return кандидаты[0].get("url")
    pmcid = результат.get("pmcid")
    if pmcid:
        return f"https://europepmc.org/articles/{pmcid}?pdf=render"
    return None


def собрать(
    запрос: str,
    cursor: str = "*",
    бюджет: int = 100,
    размер_страницы: int = 25,
    год_не_раньше: int | None = 2020,
    user_agent: str = "corpus-harvester/1.0",
    таймаут: float = 60.0,
) -> tuple[list[Документ], str | None]:
    """Возвращает (документы, новый_cursor). Если cursor=None — конец выдачи."""
    клиент = httpx.Client(timeout=таймаут, headers={"User-Agent": user_agent, "Accept": "application/json"})
    собрано: list[Документ] = []
    текущий = cursor or "*"
    полный_запрос = f"({запрос}) AND OPEN_ACCESS:Y AND HAS_PDF:Y"
    if год_не_раньше:
        полный_запрос += f" AND PUB_YEAR:[{год_не_раньше} TO 3000]"
    try:
        while len(собрано) < бюджет and текущий:
            params = {
                "query": полный_запрос,
                "format": "json",
                "resultType": "core",
                "pageSize": min(размер_страницы, бюджет - len(собрано)),
                "cursorMark": текущий,
            }
            try:
                ответ = клиент.get(БАЗА, params=params)
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(2)
                break
            данные = ответ.json()
            результаты = (данные.get("resultList") or {}).get("result", [])
            if not результаты:
                текущий = None
                break
            for r in результаты:
                pdf = _выбрать_pdf(r)
                if not pdf:
                    continue
                pmcid = r.get("pmcid") or r.get("id") or ""
                doi = r.get("doi") or pmcid
                ид = doi or pmcid
                дата = r.get("firstPublicationDate") or r.get("pubYear", "")
                if год_не_раньше and дата[:4].isdigit() and int(дата[:4]) < год_не_раньше:
                    continue
                авторы = []
                for a in (r.get("authorList") or {}).get("author", []):
                    имя = a.get("fullName") or " ".join(filter(None, [a.get("firstName", ""), a.get("lastName", "")]))
                    if имя.strip():
                        авторы.append(имя.strip())
                собрано.append(Документ(
                    источник="europepmc",
                    doc_id=f"europepmc:{ид}",
                    название=(r.get("title") or "").strip(),
                    авторы=авторы,
                    дата=дата[:10],
                    pdf_url=pdf,
                    abstract=(r.get("abstractText") or "").strip(),
                    категории=[],
                ))
                if len(собрано) >= бюджет:
                    break
            следующий = данные.get("nextCursorMark")
            if следующий and следующий != текущий:
                текущий = следующий
            else:
                текущий = None
                break
            time.sleep(0.5)
    finally:
        клиент.close()
    return собрано, текущий
