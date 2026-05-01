"""OpenAlex: REST API.

https://api.openalex.org/works

Concepts (см. https://docs.openalex.org/api-entities/concepts):
  C2780791683  Cheminformatics
  C119857082   Machine learning
  C185592680   Chemistry
  C192562407   Materials science
  C41008148    Computer science
  C71924100    Medicine

Используем `cursor` пагинацию для глубокой выборки.
"""
from __future__ import annotations

import time
from typing import Iterator

import httpx

from .arxiv import Документ


БАЗА = "https://api.openalex.org/works"

# Расширенный список концептов — чем больше тем, тем больше пул ссылок,
# и парсер не упирается в "кончились новые" даже после многих прогонов.
# ID берутся из https://api.openalex.org/concepts.
КОНЦЕПТЫ_ПО_УМОЛЧАНИЮ = {
    "C2780791683": "cheminformatics",
    "C119857082": "machine_learning",
    "C185592680": "chemistry",
    "C192562407": "materials_science",
    "C41008148": "computer_science",
    "C121332964": "physics",
    "C86803240": "biology",
    "C39432304": "environmental_science",
    "C71924100": "medicine",
    "C33923547": "mathematics",
    "C154945302": "artificial_intelligence",
    "C2522767166": "data_science",
    "C124101348": "data_mining",
    "C8010536": "natural_language_processing",
    "C153294291": "computational_chemistry",
    "C111919701": "bioinformatics",
    "C147597530": "computational_biology",
    "C161191863": "information_systems",
    "C42935608": "chemical_engineering",
    "C159985019": "biotechnology",
}


def собрать(
    концепт: str,
    cursor: str = "*",
    бюджет: int = 200,
    размер_страницы: int = 100,
    год_не_раньше: int | None = 2020,
    email: str = "",
    таймаут: float = 60.0,
) -> tuple[list[Документ], str | None]:
    """Возвращает (документы, новый_cursor). Если cursor=None — конец.

    OpenAlex требует только User-Agent с email (mailto-параметр) и
    щадящий rate-limit (≤10 req/s, рекомендуется ≤2).
    """
    клиент = httpx.Client(timeout=таймаут, headers={"User-Agent": f"corpus-harvester/1.0 ({email or 'unknown'})"})
    собрано: list[Документ] = []
    текущий = cursor or "*"
    фильтр = f"concepts.id:{концепт},has_oa_accepted_or_published_version:true"
    if год_не_раньше:
        фильтр += f",from_publication_date:{год_не_раньше}-01-01"
    try:
        while len(собрано) < бюджет and текущий:
            к_странице = min(размер_страницы, бюджет - len(собрано))
            params = {
                "filter": фильтр,
                "per-page": к_странице,
                "cursor": текущий,
                "select": "id,doi,title,publication_date,authorships,best_oa_location,abstract_inverted_index,concepts",
            }
            if email:
                params["mailto"] = email
            try:
                ответ = клиент.get(БАЗА, params=params)
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(2)
                break
            данные = ответ.json()
            результаты = данные.get("results", [])
            if not результаты:
                текущий = None
                break
            for w in результаты:
                pdf_url = ""
                loc = w.get("best_oa_location") or {}
                if loc.get("pdf_url"):
                    pdf_url = loc["pdf_url"]
                if not pdf_url:
                    continue
                doi = w.get("doi") or w.get("id")
                ид = doi.replace("https://doi.org/", "") if doi else w.get("id", "")
                дата = w.get("publication_date") or ""
                if год_не_раньше and дата[:4].isdigit() and int(дата[:4]) < год_не_раньше:
                    continue
                авторы = []
                for a in w.get("authorships", []):
                    автор = a.get("author") or {}
                    имя = автор.get("display_name", "")
                    if имя:
                        авторы.append(имя)
                концепты = [c.get("display_name", "") for c in w.get("concepts", []) if c.get("display_name")]
                # OpenAlex отдаёт abstract как inverted index, развернём
                abstract = ""
                inv = w.get("abstract_inverted_index") or {}
                if inv:
                    позиции: dict[int, str] = {}
                    for слово, поз_список in inv.items():
                        for п in поз_список:
                            позиции[п] = слово
                    abstract = " ".join(позиции[i] for i in sorted(позиции))
                собрано.append(Документ(
                    источник="openalex",
                    doc_id=f"openalex:{ид}",
                    название=(w.get("title") or "").strip(),
                    авторы=авторы,
                    дата=дата,
                    pdf_url=pdf_url,
                    abstract=abstract,
                    категории=концепты,
                ))
                if len(собрано) >= бюджет:
                    break
            мета = данные.get("meta", {})
            следующий = мета.get("next_cursor")
            if следующий and следующий != текущий:
                текущий = следующий
            else:
                текущий = None
                break
            time.sleep(0.5)
    finally:
        клиент.close()
    return собрано, текущий
