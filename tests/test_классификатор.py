"""Smoke-тесты эмбеддингового классификатора и scope-guard.

Скачивает модель (один раз) и проверяет, что:
- ин-скоуп вопросы попадают в правильные домены
- офф-скоуп вопросы режутся scope-guard'ом
- авторазметка чанков сходится с ожидаемым доменом

Запуск: python -m pytest tests/ -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def модель():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("intfloat/multilingual-e5-base")


@pytest.fixture(scope="module")
def прототипы(модель):
    from классификатор import подготовить_прототипы
    return подготовить_прототипы(модель)


def test_in_scope_chemistry_question(модель, прототипы):
    from классификатор import проверить_scope
    метки, прото, негативы = прототипы
    in_scope, домен, _, скор = проверить_scope(
        "Какие графовые нейросети применяются для предсказания свойств молекул?",
        модель, метки, прото, негативы,
    )
    assert in_scope, f"должен быть in-scope, score={скор}"
    assert домен in {"it_chem", "chemistry", "it"}


def test_in_scope_pure_it_question(модель, прототипы):
    from классификатор import проверить_scope
    метки, прото, негативы = прототипы
    in_scope, домен, _, скор = проверить_scope(
        "Что такое механизм внимания в трансформерах?",
        модель, метки, прото, негативы,
    )
    assert in_scope
    assert домен in {"it", "it_chem"}


def test_in_scope_pure_chemistry(модель, прототипы):
    from классификатор import проверить_scope
    метки, прото, негативы = прототипы
    in_scope, домен, суб, скор = проверить_scope(
        "Что такое реакция Виттига?",
        модель, метки, прото, негативы,
    )
    assert in_scope
    assert домен == "chemistry"


@pytest.mark.parametrize("вопрос", [
    "Кто выиграл чемпионат мира по футболу в 2022 году?",
    "Расскажи рецепт борща",
    "Что подарить на день рождения подруге?",
    "Какая столица Франции?",
    "Кто написал Войну и мир?",
    "Сколько лет Пушкину?",
    "Где купить хлеб?",
])
def test_off_scope_questions_rejected(модель, прототипы, вопрос):
    from классификатор import проверить_scope
    метки, прото, негативы = прототипы
    in_scope, _, _, скор = проверить_scope(
        вопрос, модель, метки, прото, негативы,
    )
    assert not in_scope, f"должен быть off-scope: {вопрос} (score={скор})"


def test_chunk_routes_to_cheminformatics(модель, прототипы):
    from классификатор import классифицировать_текст
    метки, прото, _ = прототипы
    домен, суб, _ = классифицировать_текст(
        "We use SMILES strings and Morgan fingerprints with RDKit "
        "to compute molecular similarity for virtual screening.",
        модель, метки, прото,
    )
    assert домен == "it_chem"
    assert суб in {"cheminformatics", "drug_discovery_ml", "ml_for_chem"}


def test_chunk_routes_to_dft(модель, прототипы):
    from классификатор import классифицировать_текст
    метки, прото, _ = прототипы
    домен, суб, _ = классифицировать_текст(
        "We performed DFT calculations using B3LYP functional and "
        "6-31G(d) basis set to optimize geometry of the catalyst.",
        модель, метки, прото,
    )
    assert домен in {"it_chem", "chemistry"}


def test_chunk_routes_to_pure_ml(модель, прототипы):
    from классификатор import классифицировать_текст
    метки, прото, _ = прототипы
    домен, суб, _ = классифицировать_текст(
        "We trained a transformer-based language model on the corpus "
        "with cross-entropy loss and Adam optimizer.",
        модель, метки, прото,
    )
    assert домен == "it"


def test_язык_ru():
    from классификатор import детерминировать_язык
    assert детерминировать_язык("Это русский текст с символами кириллицы.") == "ru"


def test_язык_en():
    from классификатор import детерминировать_язык
    assert детерминировать_язык("This is an English text with Latin letters only.") == "en"


def test_язык_mixed():
    from классификатор import детерминировать_язык
    результат = детерминировать_язык("Half русский half English текст mixed.")
    assert результат in {"ru", "en", "mixed"}
