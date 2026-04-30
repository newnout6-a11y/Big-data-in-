"""Тесты кросс-источникового дедупа (harvester/state.py)."""
import pytest

from harvester import state


# ---------- нормализовать_doc_id ----------

@pytest.mark.parametrize("вход,ожидание", [
    # arxiv с версией и без
    ("arxiv:2304.12345",       "arxiv:2304.12345"),
    ("arxiv:2304.12345v1",     "arxiv:2304.12345"),
    ("arxiv:2304.12345v7",     "arxiv:2304.12345"),
    # arxiv старого формата
    ("arxiv:cs.AI/0504001",    "arxiv:cs.ai/0504001"),
    # arxiv-алиас в виде DOI (openalex его часто отдаёт)
    ("openalex:10.48550/arXiv.2304.12345",  "arxiv:2304.12345"),
    ("europepmc:10.48550/arxiv.2304.12345", "arxiv:2304.12345"),
    # arxiv-алиас DOI с версией
    ("openalex:10.48550/arXiv.2304.12345v2",  "arxiv:2304.12345"),
    # arxiv-алиас DOI для старых ID со слэшем и заглавной V (регрессия:
    # раньше [^\s/v] с IGNORECASE резал на cs.C и hep-ph)
    ("openalex:10.48550/arXiv.cs.CV/0601001", "arxiv:cs.cv/0601001"),
    ("openalex:10.48550/arXiv.hep-ph/0401001", "arxiv:hep-ph/0401001"),
    # обычный DOI в openalex/europepmc
    ("openalex:10.1038/s41586-023-12345",   "doi:10.1038/s41586-023-12345"),
    ("europepmc:10.1038/s41586-023-12345",  "doi:10.1038/s41586-023-12345"),
    # DOI в chemrxiv
    ("chemrxiv:10.26434/chemrxiv-2024-ab12c", "doi:10.26434/chemrxiv-2024-ab12c"),
    # europepmc с PMC id
    ("europepmc:PMC1234567",   "pmc:pmc1234567"),
    # stackexchange оставляем как есть
    ("se:stackoverflow:12345", "se:stackoverflow:12345"),
    # cyberleninka (URL-based) — fallback, префикс оставляем (иначе slug
    # случайно совпадёт с чем-то из SE и словим ложный дубль)
    ("cyberleninka:chto-takoe-ximia", "cyberleninka:chto-takoe-ximia"),
    # пустая строка
    ("",                       ""),
])
def test_нормализация_doc_id(вход, ожидание):
    assert state.нормализовать_doc_id(вход) == ожидание


def test_кросс_источниковый_дубль_arxiv_openalex():
    """arxiv и openalex дают разные doc_id, но нормализация совпадает → дедуп."""
    с = state._значения_по_умолчанию()

    # Первый раз пришёл из arxiv
    assert not state.уже_скачан(с, "arxiv:2304.12345v1")
    state.пометить_скачанным(с, "arxiv:2304.12345v1")
    assert state.уже_скачан(с, "arxiv:2304.12345v1")

    # То же самое через openalex с DOI-алиасом arxiv
    assert state.уже_скачан(с, "openalex:10.48550/arXiv.2304.12345"), (
        "openalex-документ с тем же arxiv-id должен считаться дублем"
    )

    # То же самое через europepmc
    assert state.уже_скачан(с, "europepmc:10.48550/arxiv.2304.12345")


def test_кросс_источниковый_дубль_по_DOI():
    """openalex и europepmc часто дают один и тот же документ через DOI."""
    с = state._значения_по_умолчанию()

    state.пометить_скачанным(с, "openalex:10.1038/s41586-023-12345")
    assert state.уже_скачан(с, "europepmc:10.1038/s41586-023-12345"), (
        "документ с тем же DOI из europepmc должен считаться дублем"
    )
    assert state.уже_скачан(с, "chemrxiv:10.1038/s41586-023-12345")


def test_разные_документы_не_считаются_дублями():
    с = state._значения_по_умолчанию()
    state.пометить_скачанным(с, "arxiv:2304.12345")
    assert not state.уже_скачан(с, "arxiv:2304.12346")
    assert not state.уже_скачан(с, "openalex:10.1038/s41586-023-99999")


def test_миграция_старого_state_без_normalized_ids(tmp_path, monkeypatch):
    """Старый state.json без поля normalized_ids должен мигрировать при чтении."""
    import json
    фейк_state = tmp_path / "state.json"
    фейк_state.write_text(json.dumps({
        "version": 2,
        "sources": {},
        "downloaded_ids": [
            "arxiv:2304.12345v1",
            "openalex:10.1038/s41586-023-12345",
            "europepmc:PMC1234567",
        ],
    }), encoding="utf-8")

    monkeypatch.setattr(state, "ФАЙЛ_СОСТОЯНИЯ", str(фейк_state))

    прочитано = state.прочитать()

    # v4+ — миграция добавила и normalized_ids, и domain_counts (следующий PR)
    assert прочитано["version"] >= 3
    assert "normalized_ids" in прочитано
    assert "arxiv:2304.12345" in прочитано["normalized_ids"]
    assert "doi:10.1038/s41586-023-12345" in прочитано["normalized_ids"]
    assert "pmc:pmc1234567" in прочитано["normalized_ids"]

    # После миграции кросс-источниковый дедуп работает
    assert state.уже_скачан(прочитано, "europepmc:10.1038/s41586-023-12345")


def test_пометить_скачанным_идемпотентен():
    """Повторное пометить не должно плодить дубликаты в списках."""
    с = state._значения_по_умолчанию()
    state.пометить_скачанным(с, "arxiv:2304.12345v1")
    state.пометить_скачанным(с, "arxiv:2304.12345v1")
    state.пометить_скачанным(с, "arxiv:2304.12345v1")

    assert с["downloaded_ids"].count("arxiv:2304.12345v1") == 1
    assert с["normalized_ids"].count("arxiv:2304.12345") == 1
