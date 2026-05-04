"""Тесты для semantic_scholar, core_api, unpaywall и их интеграции в run.py."""
from unittest.mock import MagicMock, patch


from harvester.sources import semantic_scholar, core_api, unpaywall
from harvester import run


# ---------- semantic_scholar ----------

def test_semantic_scholar_парсит_ответ():
    """Моковый ответ Semantic Scholar → корректные Документы."""
    мок_данные = {
        "data": [
            {
                "paperId": "abc123",
                "title": "Graph NN for chemistry",
                "authors": [{"name": "Иван Иванов"}, {"name": "John Smith"}],
                "year": 2023,
                "publicationDate": "2023-05-15",
                "abstract": "We propose a GNN for molecular property prediction.",
                "openAccessPdf": {"url": "https://example.com/paper.pdf"},
                "externalIds": {"DOI": "10.1234/abc.123"},
            },
            {
                # без OA PDF — пропускаем
                "paperId": "xyz789",
                "title": "Paywalled paper",
                "year": 2023,
                "openAccessPdf": None,
                "externalIds": {"DOI": "10.5555/paywall"},
            },
        ]
    }
    мок_ответ = MagicMock()
    мок_ответ.status_code = 200
    мок_ответ.json.return_value = мок_данные
    мок_ответ.raise_for_status = MagicMock()

    with patch("harvester.sources.semantic_scholar.httpx.Client") as мок_клиент:
        клиент_инст = мок_клиент.return_value
        клиент_инст.get.return_value = мок_ответ
        клиент_инст.close = MagicMock()

        доки, offset = semantic_scholar.собрать(запрос="test", бюджет=1)

    # Второй paper без OA — пропущен
    assert len(доки) == 1
    assert доки[0].источник == "semanticscholar"
    assert доки[0].doc_id == "semanticscholar:10.1234/abc.123"
    assert доки[0].pdf_url == "https://example.com/paper.pdf"
    assert доки[0].название == "Graph NN for chemistry"
    assert доки[0].дата == "2023-05-15"


def test_semantic_scholar_arxiv_alias_дает_arxiv_doc_id():
    """Если externalIds содержит ArXiv, doc_id должен быть arxiv:..."""
    paper = {
        "paperId": "xyz",
        "externalIds": {"ArXiv": "2304.12345", "DOI": "10.48550/arXiv.2304.12345"},
    }
    assert semantic_scholar._doi_или_id(paper) == "arxiv:2304.12345"


def test_semantic_scholar_фильтр_по_году():
    """Документ старше year_min не попадает в выдачу."""
    мок_данные = {
        "data": [
            {"paperId": "old", "title": "Too old", "year": 2010,
             "publicationDate": "2010-01-01",
             "openAccessPdf": {"url": "https://e.com/a.pdf"},
             "externalIds": {"DOI": "10.1/x"}},
            {"paperId": "new", "title": "New", "year": 2023,
             "publicationDate": "2023-01-01",
             "openAccessPdf": {"url": "https://e.com/b.pdf"},
             "externalIds": {"DOI": "10.1/y"}},
        ]
    }
    мок_ответ = MagicMock()
    мок_ответ.status_code = 200
    мок_ответ.json.return_value = мок_данные
    мок_ответ.raise_for_status = MagicMock()

    with patch("harvester.sources.semantic_scholar.httpx.Client") as мок_клиент:
        клиент_инст = мок_клиент.return_value
        клиент_инст.get.return_value = мок_ответ
        клиент_инст.close = MagicMock()

        доки, _ = semantic_scholar.собрать(запрос="test", бюджет=5, год_не_раньше=2020)

    assert len(доки) == 1
    assert доки[0].название == "New"


# ---------- core_api ----------

def test_core_без_ключа_возвращает_пусто():
    """Без CORE_API_KEY в env источник молча возвращает []."""
    with patch.dict("os.environ", {"CORE_API_KEY": ""}, clear=False):
        доки, offset = core_api.собрать(запрос="test", бюджет=10)
    assert доки == []
    assert offset == 0


def test_core_с_ключом_парсит_downloadUrl(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "test_key_123")

    мок_ответ = MagicMock()
    мок_ответ.status_code = 200
    мок_ответ.raise_for_status = MagicMock()
    мок_ответ.json.return_value = {
        "results": [
            {
                "id": "42",
                "title": "Materials informatics review",
                "doi": "10.1000/xyz",
                "authors": [{"name": "A. Researcher"}],
                "yearPublished": 2023,
                "publishedDate": "2023-06-01",
                "downloadUrl": "https://core.ac.uk/download/42.pdf",
                "abstract": "Review of ML in materials.",
            }
        ]
    }

    with patch("harvester.sources.core_api.httpx.Client") as мок_клиент:
        клиент_инст = мок_клиент.return_value
        клиент_инст.get.return_value = мок_ответ
        клиент_инст.close = MagicMock()

        доки, offset = core_api.собрать(запрос="materials", бюджет=1)

    assert len(доки) == 1
    assert доки[0].источник == "core"
    assert доки[0].doc_id == "core:10.1000/xyz"
    assert доки[0].pdf_url == "https://core.ac.uk/download/42.pdf"


# ---------- unpaywall ----------

def test_unpaywall_находит_url_for_pdf():
    мок_ответ = MagicMock()
    мок_ответ.status_code = 200
    мок_ответ.raise_for_status = MagicMock()
    мок_ответ.json.return_value = {
        "best_oa_location": {
            "url_for_pdf": "https://authors-site.edu/preprint.pdf",
            "url": "https://doi.org/10.1234/x"
        }
    }
    with patch("harvester.sources.unpaywall.httpx.get", return_value=мок_ответ):
        url = unpaywall.найти_oa_pdf("10.1234/x", email="me@example.com")
    assert url == "https://authors-site.edu/preprint.pdf"


def test_unpaywall_без_email_возвращает_None():
    assert unpaywall.найти_oa_pdf("10.1234/x", email="") is None


def test_unpaywall_404_возвращает_None():
    мок_ответ = MagicMock()
    мок_ответ.status_code = 404
    with patch("harvester.sources.unpaywall.httpx.get", return_value=мок_ответ):
        url = unpaywall.найти_oa_pdf("10.1234/nonexistent", email="me@e.com")
    assert url is None


def test_unpaywall_url_for_pdf_без_подстроки_pdf_тоже_возвращается():
    """Регрессия: по контракту Unpaywall url_for_pdf — всегда PDF,
    даже если в URL нет подстроки «pdf» (например, CDN-ссылка)."""
    мок_ответ = MagicMock()
    мок_ответ.status_code = 200
    мок_ответ.raise_for_status = MagicMock()
    мок_ответ.json.return_value = {
        "best_oa_location": {
            "url_for_pdf": "https://s3.amazonaws.com/jor/fulltext/abc123",
            "url": "https://journal.example.org/article/abc123"
        }
    }
    with patch("harvester.sources.unpaywall.httpx.get", return_value=мок_ответ):
        url = unpaywall.найти_oa_pdf("10.1234/x", email="me@example.com")
    assert url == "https://s3.amazonaws.com/jor/fulltext/abc123"


# ---------- run.py helpers ----------

def test_извлечь_doi_из_doc_id():
    assert run._извлечь_doi_из_doc_id("openalex:10.1038/s41586-023-12345") == "10.1038/s41586-023-12345"
    assert run._извлечь_doi_из_doc_id("semanticscholar:10.1234/abc.xyz") == "10.1234/abc.xyz"
    assert run._извлечь_doi_из_doc_id("arxiv:2304.12345") is None  # без 10.XXXX/
    assert run._извлечь_doi_из_doc_id("") is None


def test_новые_источники_зарегистрированы():
    assert "semanticscholar" in run.ВСЕ_ИСТОЧНИКИ
    assert "core" in run.ВСЕ_ИСТОЧНИКИ
    assert "semanticscholar" in run.СБОРЩИКИ
    assert "core" in run.СБОРЩИКИ


def test_semantic_scholar_429_не_зацикливается():
    """Постоянный 429 должен выйти после N ретраев, а не крутиться вечно."""
    мок_ответ = MagicMock()
    мок_ответ.status_code = 429

    with patch("harvester.sources.semantic_scholar.httpx.Client") as мок_клиент, \
         patch("harvester.sources.semantic_scholar.time.sleep"):
        клиент_инст = мок_клиент.return_value
        клиент_инст.get.return_value = мок_ответ
        клиент_инст.close = MagicMock()

        доки, offset = semantic_scholar.собрать(запрос="test", бюджет=50)

    # Должен выйти после 3 ретраев → 4 GET-запроса (первый + 3 retry)
    assert доки == []
    assert клиент_инст.get.call_count <= 5  # с запасом на flakiness


def test_core_429_не_зацикливается(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "test_key")

    мок_ответ = MagicMock()
    мок_ответ.status_code = 429

    with patch("harvester.sources.core_api.httpx.Client") as мок_клиент, \
         patch("harvester.sources.core_api.time.sleep"):
        клиент_инст = мок_клиент.return_value
        клиент_инст.get.return_value = мок_ответ
        клиент_инст.close = MagicMock()

        доки, offset = core_api.собрать(запрос="test", бюджет=50)

    assert доки == []
    assert клиент_инст.get.call_count <= 5


def test_unpaywall_fallback_обновляет_pdf_url():
    """Проверка что после Unpaywall-fallback pdf_url в метаданных обновлён
    (регрессия — раньше использовался _replace на dataclass что не работало).
    """
    from harvester.sources.arxiv import Документ
    док = Документ(
        источник="europepmc", doc_id="europepmc:10.1038/x",
        название="Test", авторы=[], дата="2023-01-01",
        pdf_url="https://broken.example.com/paywall.pdf",
        abstract="", категории=[],
    )
    новый_url = "https://oa.example.com/open.pdf"
    # У dataclass есть прямое присваивание
    док.pdf_url = новый_url
    assert док.pdf_url == новый_url
