"""Изолированные регрессии UI без Streamlit, моделей и API-вызовов."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest


APP = Path(__file__).resolve().parents[1] / "ui" / "app.py"


def _load_ui_symbols(*names, **globals_):
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names
            for target in node.targets
        ):
            nodes.append(node)
    namespace = {"re": re, **globals_}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), "exec"), namespace)
    return namespace


@pytest.mark.parametrize(
    "banner",
    [
        "*Это общеизвестное знание, в найденных фрагментах конкретного ответа не было.*",
        "Это ответ из общих знаний, в корпусе конкретный ответ отсутствует.",
        "_Это общеизвестное знание, в базе конкретного ответа нет_",
    ],
)
def test_general_knowledge_banner_is_removed_completely(banner):
    symbols = _load_ui_symbols("_ПЛАШКА_ОБЩИХ_ЗНАНИЙ", "_срезать_плашку_общих_знаний")
    clean = symbols["_срезать_плашку_общих_знаний"]
    assert clean(f"Ответ подтверждён [1].\n\n{banner}") == "Ответ подтверждён [1]."


def test_general_knowledge_cleanup_preserves_the_next_sentence():
    symbols = _load_ui_symbols("_ПЛАШКА_ОБЩИХ_ЗНАНИЙ", "_срезать_плашку_общих_знаний")
    clean = symbols["_срезать_плашку_общих_знаний"]
    text = (
        "Это общеизвестное знание, в найденных фрагментах ответа не было. "
        "Следующий факт подтверждён [1]."
    )
    assert clean(text) == "Следующий факт подтверждён [1]."


def test_new_quiz_does_not_reuse_previous_answers_or_grade():
    state = {
        "квиз_результат": {"questions": [{"id": 1, "question": "Старый вопрос"}]},
        "ответ_квиз_1": "Старый ответ",
        "ответ_квиз_2": "Ещё старый ответ",
        "квиз_ответы_сохранённые": {"1": "Старый ответ"},
        "оценка_квиза": {"total": 2, "max_total": 2},
        "тема_квиза": "Химия",
        "карточки_результат": {"cards": ["Карточка"]},
    }
    symbols = _load_ui_symbols("_сохранить_новый_квиз", st=SimpleNamespace(session_state=state))
    questions = [{"id": 1, "question": "Новый вопрос"}]
    fragments = [{"text": "Новый учебный материал"}]
    symbols["_сохранить_новый_квиз"](questions, fragments)

    assert state["квиз_результат"] == {"questions": questions, "фрагменты": fragments}
    assert "оценка_квиза" not in state
    assert "квиз_ответы_сохранённые" not in state
    assert not any(key.startswith("ответ_квиз_") for key in state)
    assert state["тема_квиза"] == "Химия"
    assert state["карточки_результат"] == {"cards": ["Карточка"]}


def test_first_quiz_can_be_saved_in_an_empty_session():
    state = {}
    symbols = _load_ui_symbols("_сохранить_новый_квиз", st=SimpleNamespace(session_state=state))
    symbols["_сохранить_новый_квиз"]([], [])
    assert state == {"квиз_результат": {"questions": [], "фрагменты": []}}
