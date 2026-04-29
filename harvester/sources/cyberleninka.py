"""КиберЛенинка: OAI-PMH endpoint для русскоязычных статей.

https://cyberleninka.ru/oai

OAI отдаёт Dublin Core метаданные (без полного текста). Полный PDF тянем по
шаблону URL `<article_url>/pdf`. Резюме классификатор отфильтрует на этапе
ингеста по близости к нашим прототипам.

Замечание: с части IP (CDN/CF) PDF может возвращать 403. Метаданные
(OAI-endpoint) обычно проходят. В этом случае харвестер пропустит запись
и продолжит работу.
"""
from __future__ import annotations

import time
from typing import Iterator
from xml.etree import ElementTree as ET

import httpx

from .arxiv import Документ


БАЗА = "https://cyberleninka.ru/oai"
_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _текст(элемент, путь):
    нашли = элемент.findtext(путь, namespaces=_NS)
    return (нашли or "").strip()


def собрать(
    from_date: str,
    until_date: str | None = None,
    resumption_token: str | None = None,
    бюджет: int = 100,
    user_agent: str = "corpus-harvester/1.0",
    таймаут: float = 60.0,
) -> tuple[list[Документ], str | None]:
    """Возвращает (документы, новый_resumption_token)."""
    клиент = httpx.Client(timeout=таймаут, headers={"User-Agent": user_agent})
    собрано: list[Документ] = []
    токен = resumption_token
    try:
        while len(собрано) < бюджет:
            params: dict
            if токен:
                params = {"verb": "ListRecords", "resumptionToken": токен}
            else:
                params = {
                    "verb": "ListRecords",
                    "metadataPrefix": "oai_dc",
                    "from": from_date,
                }
                if until_date:
                    params["until"] = until_date
            try:
                ответ = клиент.get(БАЗА, params=params)
                ответ.raise_for_status()
            except httpx.HTTPError:
                time.sleep(2)
                break
            try:
                корень = ET.fromstring(ответ.text)
            except ET.ParseError:
                break
            записи = корень.findall("oai:ListRecords/oai:record", _NS)
            if not записи:
                токен = None
                break
            for запись in записи:
                заголовок = запись.find("oai:header", _NS)
                if заголовок is not None and заголовок.get("status") == "deleted":
                    continue
                метадата = запись.find("oai:metadata/oai_dc:dc", _NS)
                if метадата is None:
                    continue
                ид = _текст(заголовок, "oai:identifier") if заголовок is not None else ""
                название = _текст(метадата, "dc:title")
                if not ид or not название:
                    continue
                дата = _текст(заголовок, "oai:datestamp")[:10] if заголовок is not None else ""
                идентификаторы = метадата.findall("dc:identifier", _NS)
                url_статьи = ""
                for и in идентификаторы:
                    т = (и.text or "").strip()
                    if т.startswith("http"):
                        url_статьи = т
                        break
                if not url_статьи:
                    url_статьи = ид if ид.startswith("http") else f"https://cyberleninka.ru{ид}"
                pdf_url = url_статьи.rstrip("/") + "/pdf"
                авторы = [(а.text or "").strip() for а in метадата.findall("dc:creator", _NS) if (а.text or "").strip()]
                собрано.append(Документ(
                    источник="cyberleninka",
                    doc_id=f"cyberleninka:{ид}",
                    название=название,
                    авторы=авторы,
                    дата=дата,
                    pdf_url=pdf_url,
                    abstract=_текст(метадата, "dc:description"),
                    категории=[(п.text or "").strip() for п in метадата.findall("dc:subject", _NS) if (п.text or "").strip()],
                ))
                if len(собрано) >= бюджет:
                    break
            токен_элем = корень.find("oai:ListRecords/oai:resumptionToken", _NS)
            новый_токен = (токен_элем.text or "").strip() if токен_элем is not None and токен_элем.text else ""
            if новый_токен and новый_токен != токен:
                токен = новый_токен
            else:
                токен = None
                break
            time.sleep(0.5)
    finally:
        клиент.close()
    return собрано, токен
