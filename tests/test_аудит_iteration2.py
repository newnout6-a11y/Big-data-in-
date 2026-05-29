"""Регрессии для второго раунда аудита (C11-C16) по обратной связи пользователя.

C11. Ответ не должен содержать «Источник: корпус. Документ: foo.pdf, стр. N»
     — это служебная шапка CONTEXT, а не часть ответа.
C12. DeepSeek получает усиленную инструкцию против ложных «В базе нет данных».
C13. SMILES-валидатор и плейсхолдер-разбор работают правильно.
C14. _диверсифицировать_документы при широкой выдаче не даёт одному документу
     2 фрагмента сразу — сначала пытается набрать по 1 на документ.
C15. _SMILES_БЛОК ловит код-блок и валидирует.
C16. _SMILES_МАРКЕР корректно режет ответ на сегменты.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- C11: чистка служебных шапок CONTEXT ----------

def test_C11_вырезает_источник_корпус_документ():
    """LLM может скопировать `Источник: корпус. Документ: foo.pdf, стр. 15`
    из CONTEXT в свой ответ. Пост-фильтр должен удалить эти шапки."""
    sys.modules.pop("app", None)
    import app

    исходник = (
        "Метрика Reliability оценивает надёжность агента [1]. "
        "Источник: корпус. Документ: holistic-evaluation-and-failure-diagnosis.pdf, стр. 19. "
        "Атака FGSM использует градиент предсказания модели [5]."
    )

    очищенный = app._вырезать_pdf_мусор_из_ответа(исходник)

    assert "Источник: корпус" not in очищенный, (
        f"Не вырезана шапка 'Источник: корпус'. Результат: {очищенный!r}"
    )
    assert "holistic-evaluation-and-failure-diagnosis.pdf" not in очищенный, (
        "Не вырезано имя документа из шапки CONTEXT"
    )
    # Содержательные предложения остаются
    assert "Метрика Reliability" in очищенный
    assert "Атака FGSM" in очищенный


def test_C11_вырезает_документ_стр_без_источник():
    """Голая шапка вида «Документ: foo.pdf, стр. 15» (без префикса
    «Источник:») тоже должна быть удалена."""
    sys.modules.pop("app", None)
    import app

    исходник = (
        "Это первое утверждение [1]. "
        "Документ: mhsa-a-lightweight-framework.pdf, стр. 16. "
        "Это второе утверждение [2]."
    )

    очищенный = app._вырезать_pdf_мусор_из_ответа(исходник)
    assert "mhsa-a-lightweight-framework.pdf" not in очищенный
    assert "стр. 16" not in очищенный
    assert "первое утверждение" in очищенный
    assert "второе утверждение" in очищенный


def test_C11_не_трогает_обычные_упоминания_документов():
    """Слово «документ» в обычном смысле (не как шапка CONTEXT) трогать нельзя."""
    sys.modules.pop("app", None)
    import app

    исходник = "В этом документе говорится о методе X. Документация есть на сайте."
    очищенный = app._вырезать_pdf_мусор_из_ответа(исходник)
    # Должно остаться нетронутым (нет паттерна "Документ: name.pdf, стр. N")
    assert "В этом документе говорится" in очищенный
    assert "Документация есть на сайте" in очищенный


# ---------- C12: усиленная инструкция для DeepSeek ----------

def test_C12_deepseek_дополнительная_инструкция_содержит_жёсткий_протокол():
    """Регрессия: ранее DeepSeek получал мягкую инструкцию ('не отказывай
    из-за недословного совпадения'). Теперь там 3-шаговый протокол."""
    sys.modules.pop("app", None)
    import app

    # Берём реальный код функции, проверяем что инструкция содержит ключевые
    # слова, которые отсутствовали раньше.
    import inspect
    src = inspect.getsource(app.получить_ответ_от_groq)
    assert "ЖЁСТКИЙ ПРОТОКОЛ ОТВЕТА" in src
    assert "Шаг 1" in src and "Шаг 2" in src and "Шаг 3" in src
    assert "перечень" in src.lower()


# ---------- C13/C15: SMILES-парсинг ----------

def test_C13_извлечение_smiles_заменяет_на_плейсхолдер():
    sys.modules.pop("app", None)
    import app

    ответ = (
        "Аспирин — `CC(=O)Oc1ccccc1C(=O)O`, обладает противовоспалительным "
        "действием [1].\n\n"
        "```smiles\n"
        "CC(=O)Oc1ccccc1C(=O)O\n"
        "```\n\n"
        "Бензол является ароматическим [2].\n\n"
        "```smiles\n"
        "c1ccccc1\n"
        "```"
    )
    очищенный, smi = app._извлечь_smiles_из_ответа(ответ)
    assert len(smi) == 2
    assert "CC(=O)Oc1ccccc1C(=O)O" in smi
    assert "c1ccccc1" in smi
    # Плейсхолдеры на местах вместо блоков
    assert "<<<SMILES:0>>>" in очищенный
    assert "<<<SMILES:1>>>" in очищенный
    # Сами SMILES-блоки убраны из текста (должны рендериться отдельно)
    assert "```smiles" not in очищенный


def test_C13_извлечение_smiles_отвергает_невалидные_блоки():
    """В ```smiles``` положили НЕ-SMILES (URL, длинная фраза). Должно
    остаться как есть, не подменяться плейсхолдером."""
    sys.modules.pop("app", None)
    import app

    мусор = (
        "```smiles\nhttps://example.com/molecule\n```\n"
        "```smiles\nЭто длинное предложение с пробелами\n```\n"
    )
    очищенный, smi = app._извлечь_smiles_из_ответа(мусор)
    assert smi == []
    # Невалидные блоки остаются в тексте
    assert "```smiles" in очищенный


def test_C13_smiles_валидатор():
    sys.modules.pop("app", None)
    import app

    assert app._валидный_smiles("CC(=O)Oc1ccccc1C(=O)O")  # аспирин
    assert app._валидный_smiles("c1ccccc1")  # бензол
    assert app._валидный_smiles("[Na+].[Cl-]")  # NaCl
    assert app._валидный_smiles("C/C=C/C")  # стерео
    assert app._валидный_smiles("CC[C@H](O)C")  # @-стерео центр
    # Невалидные
    assert not app._валидный_smiles("")
    assert not app._валидный_smiles("CC С")  # пробел
    assert not app._валидный_smiles("hello world molecule")  # слово
    assert not app._валидный_smiles("https://example.com/x")  # URL
    assert not app._валидный_smiles("C" * 400)  # слишком длинный


# ---------- C14: диверсификация документов ----------

def test_C14_диверсификация_сначала_по_одному_фрагменту():
    """Регрессия: ранее `_диверсифицировать_документы` сразу разрешал по 2
    фрагмента на документ. На широкой выдаче из 5 документов это давало
    [doc1, doc1, doc2, doc2, doc3] — 3 документа, 5 фрагментов.
    Сейчас должно быть [doc1, doc2, doc3, doc4, doc5] (по одному пока хватает)."""
    sys.modules.pop("app", None)
    import app

    def _точка(doc, score, idx):
        return SimpleNamespace(
            id=idx,
            score=score,
            payload={"document": doc, "doc_id": doc, "text": "x" * 200},
        )

    # 10 кандидатов: 2 фрагмента из 5 разных документов
    кандидаты = [
        _точка("doc_a.pdf", 0.95, 1),
        _точка("doc_a.pdf", 0.94, 2),
        _точка("doc_b.pdf", 0.93, 3),
        _точка("doc_b.pdf", 0.92, 4),
        _точка("doc_c.pdf", 0.91, 5),
        _точка("doc_c.pdf", 0.90, 6),
        _точка("doc_d.pdf", 0.89, 7),
        _точка("doc_d.pdf", 0.88, 8),
        _точка("doc_e.pdf", 0.87, 9),
        _точка("doc_e.pdf", 0.86, 10),
    ]
    выбранные = app._диверсифицировать_документы(кандидаты, количество=5)

    документы = [т.payload["document"] for т in выбранные]
    assert len(set(документы)) == 5, (
        f"При выборке 5 фрагментов из 5 документов должно быть 5 разных. "
        f"Получили: {документы}"
    )


def test_C14_диверсификация_спасает_узкую_выдачу():
    """Если все кандидаты из одного документа — должны вернуть всё, что есть,
    не упорствуя в diversity. Без этого пользователь получит пустоту."""
    sys.modules.pop("app", None)
    import app

    def _точка(doc, score, idx):
        return SimpleNamespace(
            id=idx,
            score=score,
            payload={"document": doc, "doc_id": doc, "text": "x" * 200},
        )

    кандидаты = [_точка("only.pdf", 0.9 - 0.01 * i, i) for i in range(8)]
    выбранные = app._диверсифицировать_документы(кандидаты, количество=5)

    assert len(выбранные) == 5
    assert all(т.payload["document"] == "only.pdf" for т in выбранные)


def test_C14_диверсификация_малый_пул_не_теряется():
    """Кандидатов меньше чем нужно — возвращаем всё что есть."""
    sys.modules.pop("app", None)
    import app

    def _точка(doc, score, idx):
        return SimpleNamespace(
            id=idx,
            score=score,
            payload={"document": doc, "doc_id": doc, "text": "x" * 200},
        )

    кандидаты = [_точка("a.pdf", 0.9, 1), _точка("b.pdf", 0.8, 2)]
    выбранные = app._диверсифицировать_документы(кандидаты, количество=5)
    assert len(выбранные) == 2


# ---------- C16: SMILES-плейсхолдеры в потоке вывода ----------

def test_C16_smiles_маркер_парсится_корректно():
    sys.modules.pop("app", None)
    import app

    блок = "Текст до. <<<SMILES:0>>> Текст между. <<<SMILES:1>>> Текст после."
    маркеры = list(app._SMILES_МАРКЕР.finditer(блок))
    assert len(маркеры) == 2
    assert маркеры[0].group(1) == "0"
    assert маркеры[1].group(1) == "1"


# ---------- C17: провайдер-зависимый max_tokens ----------

def test_C17_max_tokens_groq_не_превышает_cap():
    """Groq llama-моделей API режет на 8192. Не должны превышать."""
    sys.modules.pop("app", None)
    import app
    лимит = app._max_tokens("groq:llama-3.3-70b-versatile", режим="default")
    assert лимит <= 8192, f"Groq cap превышен: {лимит}"
    assert лимит >= 4000, f"Groq лимит подозрительно мал: {лимит}"


def test_C17_max_tokens_deepseek_больше_groq():
    """DeepSeek поддерживает гораздо больше токенов — лимит должен быть выше."""
    sys.modules.pop("app", None)
    import app
    groq = app._max_tokens("groq:llama-3.3-70b-versatile", режим="default")
    ds = app._max_tokens("deepseek:deepseek-v4-flash", режим="default")
    assert ds > groq, (
        f"DeepSeek лимит ({ds}) должен быть больше Groq ({groq}) — иначе "
        "пользователь не увидит реальной разницы при выборе провайдера"
    )
    # Sanity: дефолт 32 000 — это уже сильно больше старых 1500
    assert ds >= 16000, f"DeepSeek default слишком мал: {ds}"


def test_C17_max_tokens_env_override(monkeypatch):
    """LLM_MAX_TOKENS_DEEPSEEK должен переопределять дефолт."""
    monkeypatch.setenv("LLM_MAX_TOKENS_DEEPSEEK", "100000")
    sys.modules.pop("app", None)
    import app
    лимит = app._max_tokens("deepseek:deepseek-v4-flash", режим="default")
    assert лимит == 100000


def test_C17_max_tokens_не_превышает_абсолютный_cap(monkeypatch):
    """Даже если в env положили космос — итоговый max_tokens обрезается
    до жёсткого технического cap провайдера, иначе API вернёт ошибку."""
    monkeypatch.setenv("LLM_MAX_TOKENS_DEEPSEEK", "999999999")
    sys.modules.pop("app", None)
    import app
    лимит = app._max_tokens("deepseek:deepseek-v4-flash", режим="default")
    # DeepSeek API максимум 384 000 — выше нельзя
    assert лимит <= 384000


def test_C17_max_tokens_неизвестная_модель_безопасный_default():
    sys.modules.pop("app", None)
    import app
    лимит = app._max_tokens("unknown:foo", режим="default")
    # Должен вернуть число, не упасть
    assert isinstance(лимит, int) and лимит > 0
