"""Тесты топик-балансировки: классификация доменов + коэффициенты бюджета."""
import pytest

from harvester import домены, state


# ---------- классификатор ----------

@pytest.mark.parametrize("источник,название,abstract,ожидание", [
    # Chemrxiv всегда chem, даже с "neural network" в названии
    ("chemrxiv", "Neural network for reactions", "", "chem"),
    # Явно IT
    ("arxiv", "Transformer attention in language models",
     "We propose a GPT variant for NLP.", "it"),
    # Явно chem
    ("openalex", "DFT calculation of catalyst reaction",
     "Density functional theory study of catalysis.", "chem"),
    # Смесь — GNN для молекул → chem (маркеры chem перевешивают)
    ("openalex", "Graph neural network for molecular property prediction",
     "A GNN model predicts drug properties from SMILES strings.",
     "chem"),
    # Без маркеров → other
    ("europepmc", "Random title", "Nothing interesting here.", "other"),
    # Русский текст chem
    ("cyberleninka", "Синтез полимеров", "Органическая химия.", "chem"),
])
def test_классификатор_домена(источник, название, abstract, ожидание):
    результат = домены.классифицировать(
        источник=источник, название=название, abstract=abstract,
    )
    assert результат == ожидание


def test_stackexchange_по_сайту_в_doc_id():
    # Chemistry SE → chem
    assert домены.классифицировать(
        источник="stackexchange", doc_id="se:chemistry:12345",
        название="What is pH", abstract="",
    ) == "chem"
    # Stack Overflow → it
    assert домены.классифицировать(
        источник="stackexchange", doc_id="se:stackoverflow:98765",
        название="Python dict", abstract="",
    ) == "it"


# ---------- коэффициенты ----------

def test_малый_объем_все_1():
    """При малом общем объёме коэффициенты = 1.0 (не колбасим случайный шум)."""
    counts = {"chem": 5, "it": 10, "other": 0}  # всего 15
    коэф = домены.рассчитать_коэффициенты(counts, минимум_всего=50)
    assert коэф == {"chem": 1.0, "it": 1.0, "other": 1.0}


def test_chem_отстает_получает_буст():
    # 200 total, chem=20 (10%), it=170 (85%), other=10 (5%)
    # идеал chem=45%, it=45%, other=10%. chem сильно отстал.
    counts = {"chem": 20, "it": 170, "other": 10}
    коэф = домены.рассчитать_коэффициенты(counts)
    assert коэф["chem"] > 1.5, f"chem должен получить буст, получили {коэф['chem']}"
    assert коэф["it"] < 1.0, f"it должен получить пенальти, получили {коэф['it']}"


def test_идеальный_баланс_около_1():
    # 45/45/10 — все коэффициенты должны быть ~1.0
    counts = {"chem": 450, "it": 450, "other": 100}
    коэф = домены.рассчитать_коэффициенты(counts)
    for дом, v in коэф.items():
        assert 0.95 <= v <= 1.05, f"{дом}={v} должен быть ~1.0"


def test_отсутствующий_домен_максимальный_буст():
    counts = {"chem": 0, "it": 500, "other": 500}
    коэф = домены.рассчитать_коэффициенты(counts)
    assert коэф["chem"] == 2.0  # хардкод-буст когда домен = 0


# ---------- state миграция v3 → v4 ----------

def test_state_миграция_добавляет_domain_counts(tmp_path, monkeypatch):
    import json
    фейк = tmp_path / "state.json"
    фейк.write_text(json.dumps({
        "version": 3,
        "sources": {},
        "downloaded_ids": [],
        "normalized_ids": [],
    }), encoding="utf-8")
    monkeypatch.setattr(state, "ФАЙЛ_СОСТОЯНИЯ", str(фейк))

    прочитано = state.прочитать()
    assert прочитано["version"] == 4
    assert прочитано["domain_counts"] == {"chem": 0, "it": 0, "other": 0}
