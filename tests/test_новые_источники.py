"""Smoke-тесты на новых парсеров источников.

Проверяют структуру возврата без сети — мокаем httpx.Client.get.
Реальные сетевые тесты прогоняются в локальной разработке (не в CI).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from harvester.sources import europepmc, cyberleninka, stackexchange


def _ответ(json_data=None, text=None, status=200):
    м = MagicMock()
    м.status_code = status
    м.json.return_value = json_data or {}
    м.text = text or ""
    м.raise_for_status = MagicMock()
    return м


def test_europepmc_parses_result():
    ответ_pmc = _ответ(json_data={
        "resultList": {"result": [{
            "id": "12345", "pmcid": "PMC12345", "doi": "10.1/foo",
            "title": "ML for chemistry",
            "firstPublicationDate": "2024-05-01",
            "abstractText": "Test abstract",
            "authorList": {"author": [{"fullName": "Doe, John"}]},
            "fullTextUrlList": {"fullTextUrl": [
                {"documentStyle": "pdf", "availability": "Open access", "url": "https://x/pdf"},
            ]},
        }]},
        "nextCursorMark": "*",
    })
    with patch("harvester.sources.europepmc.httpx.Client") as M:
        M.return_value.get.return_value = ответ_pmc
        доки, cur = europepmc.собрать("ml", бюджет=1, размер_страницы=1, год_не_раньше=2020)
    assert len(доки) == 1
    d = доки[0]
    assert d.источник == "europepmc"
    assert d.дата.startswith("2024")
    assert d.pdf_url == "https://x/pdf"
    assert "Doe, John" in d.авторы


def test_cyberleninka_parses_oai():
    xml = """<?xml version="1.0"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header><identifier>https://cyberleninka.ru/article/n/test</identifier><datestamp>2024-03-15T10:00:00Z</datestamp></header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Тестовая статья по химии</dc:title>
          <dc:creator>Иванов И.И.</dc:creator>
          <dc:identifier>https://cyberleninka.ru/article/n/test</dc:identifier>
          <dc:description>Аннотация</dc:description>
        </oai_dc:dc>
      </metadata>
    </record>
    <resumptionToken>tok123</resumptionToken>
  </ListRecords>
</OAI-PMH>"""
    with patch("harvester.sources.cyberleninka.httpx.Client") as M:
        M.return_value.get.return_value = _ответ(text=xml)
        доки, tok = cyberleninka.собрать(from_date="2024-01-01", бюджет=1)
    assert len(доки) == 1
    d = доки[0]
    assert d.источник == "cyberleninka"
    assert d.название == "Тестовая статья по химии"
    assert d.pdf_url.endswith("/pdf")
    assert tok == "tok123"


def test_stackexchange_combines_q_and_answer():
    вопросы = _ответ(json_data={
        "items": [{
            "question_id": 100, "title": "Why is gold golden?",
            "body": "<p>A question about gold.</p>",
            "tags": ["chem"], "owner": {"display_name": "u1"},
            "creation_date": 1700000000, "accepted_answer_id": 200,
        }],
        "has_more": False,
    })
    ответы = _ответ(json_data={
        "items": [{"question_id": 100, "body": "<p>It's relativistic.</p>"}],
    })
    with patch("harvester.sources.stackexchange.httpx.Client") as M:
        client = MagicMock()
        client.get.side_effect = [вопросы, ответы]
        M.return_value = client
        доки, _ = stackexchange.собрать("chemistry", page=1, бюджет=1)
    assert len(доки) == 1
    d = доки[0]
    assert d.источник == "stackexchange:chemistry"
    assert d.pdf_url == ""
    assert "Why is gold golden?" in d.abstract
    assert "Top Answer" in d.abstract
    assert "relativistic" in d.abstract


def test_stackexchange_strip_html():
    очищено = stackexchange._strip_html("<p>Hello <b>world</b></p>")
    assert "Hello" in очищено
    assert "<" not in очищено
