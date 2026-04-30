"""Unpaywall — по DOI возвращает легальную OA-копию (если есть).

https://api.unpaywall.org/v2/<doi>?email=you@example.com

Бесплатно, без ключа, просто email. Rate limit — неформальный, ~100k req/день.

Используется как «апгрейд» для openalex/europepmc: если источник отдаёт
paywall-DOI, мы спрашиваем Unpaywall и часто получаем OA-copy на authors' site
или PMC. Отдельно как источник не запускается — это helper, дёргается из run.py
при FAIL-скачивании.
"""
from __future__ import annotations

import time
import httpx


БАЗА = "https://api.unpaywall.org/v2"


def найти_oa_pdf(
    doi: str,
    email: str,
    user_agent: str = "corpus-harvester/1.2",
    таймаут: float = 20.0,
) -> str | None:
    """Возвращает URL OA-PDF по DOI или None если не нашёлся."""
    doi = doi.strip().replace("https://doi.org/", "").replace("doi:", "")
    if not doi or not email:
        return None

    url = f"{БАЗА}/{doi}"
    try:
        r = httpx.get(url, params={"email": email}, timeout=таймаут,
                      headers={"User-Agent": user_agent, "Accept": "application/json"})
        if r.status_code == 404:
            return None
        if r.status_code == 429:
            time.sleep(5)
            return None
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None

    # best_oa_location — рекомендованная Unpaywall лучшая OA-копия
    best = data.get("best_oa_location") or {}
    for field in ("url_for_pdf", "url"):
        ссылка = best.get(field)
        if ссылка and (ссылка.endswith(".pdf") or "pdf" in ссылка.lower()):
            return ссылка
    # fallback — любая OA-копия с pdf
    for loc in data.get("oa_locations") or []:
        pdf = loc.get("url_for_pdf")
        if pdf:
            return pdf
    return None
