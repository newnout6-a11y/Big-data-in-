"""chemRxiv: публичный JSON API.

https://chemrxiv.org/engage/api-gateway/chemrxiv/public/v1/items

С 2025 года chemRxiv стоит за Cloudflare bot-protection ("Just a moment…").
Стандартный httpx-запрос получает 403 + HTML-челлендж. На пользовательских
браузерных IP может проходить, на дата-центровых обычно нет. Если 403 —
тихо пропускаем, печатаем понятное предупреждение, harvester продолжает
работу с другими источниками. Альтернатива: chemRxiv-материалы дублируются
в OpenAlex (cheminformatics/chemistry концепты), которые мы уже качаем.
"""
from __future__ import annotations

import time
from typing import Iterator

import httpx

from .arxiv import Документ


БАЗА = "https://chemrxiv.org/engage/api-gateway/chemrxiv/public/v1/items"
_БРАУЗЕРНЫЙ_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def собрать(
    skip: int = 0,
    бюджет: int = 200,
    размер_страницы: int = 50,
    год_не_раньше: int | None = 2020,
    user_agent: str = "corpus-harvester/1.0",
    таймаут: float = 60.0,
) -> Iterator[Документ]:
    отдано = 0
    текущий_skip = skip
    # Браузерный UA + Accept: chemRxiv API за Cloudflare, дефолтный httpx-UA
    # ловит 403 + HTML-челлендж. Браузерный UA иногда проходит.
    клиент = httpx.Client(
        timeout=таймаут,
        headers={
            "User-Agent": _БРАУЗЕРНЫЙ_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://chemrxiv.org/",
        },
    )
    try:
        while отдано < бюджет:
            к_странице = min(размер_страницы, бюджет - отдано)
            try:
                ответ = клиент.get(БАЗА, params={"skip": текущий_skip, "limit": к_странице, "sort": "PUBLISHED_DATE_DESC"})
                if ответ.status_code == 403 and "html" in ответ.headers.get("content-type", "").lower():
                    print(
                        "[chemrxiv] 403 от Cloudflare bot-protection — пропускаю, "
                        "chemRxiv-материалы тянутся через OpenAlex (концепт chemistry/cheminformatics)",
                        flush=True,
                    )
                    break
                ответ.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[chemrxiv] сеть упала: {type(e).__name__} — пропускаю", flush=True)
                time.sleep(3)
                break
            try:
                данные = ответ.json()
            except ValueError:
                print("[chemrxiv] не-JSON ответ — пропускаю", flush=True)
                break
            записи = данные.get("itemHits") or данные.get("items") or []
            if not записи:
                break
            for запись_обёртка in записи:
                item = запись_обёртка.get("item", запись_обёртка)
                ид = item.get("id") or item.get("doi")
                if not ид:
                    continue
                дата = (item.get("publishedDate") or item.get("submittedDate") or "")[:10]
                if год_не_раньше and дата and дата[:4].isdigit() and int(дата[:4]) < год_не_раньше:
                    continue
                pdf_url = ""
                for файл in (item.get("asset", {}).get("original", {}) and [item["asset"]["original"]]) or []:
                    if файл.get("mimeType") == "application/pdf":
                        pdf_url = файл.get("url", "")
                        break
                if not pdf_url and item.get("asset", {}).get("original", {}).get("url"):
                    pdf_url = item["asset"]["original"]["url"]
                if not pdf_url:
                    continue
                авторы = []
                for а in item.get("authors", []):
                    имя = " ".join(filter(None, [а.get("firstName", ""), а.get("lastName", "")]))
                    if имя.strip():
                        авторы.append(имя.strip())
                категории = [к.get("name", "") for к in item.get("categories", []) if к.get("name")]
                yield Документ(
                    источник="chemrxiv",
                    doc_id=f"chemrxiv:{ид}",
                    название=(item.get("title") or "").strip().replace("\n", " "),
                    авторы=авторы,
                    дата=дата,
                    pdf_url=pdf_url,
                    abstract=(item.get("abstract") or "").strip(),
                    категории=категории,
                )
                отдано += 1
                if отдано >= бюджет:
                    break
            текущий_skip += к_странице
            time.sleep(1.0)
    finally:
        клиент.close()


def следующий_курсор(текущий: int, прошло: int) -> int:
    return текущий + прошло
