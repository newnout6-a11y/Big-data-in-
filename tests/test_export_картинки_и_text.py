"""Регрессия: экспорт ответа в .docx и .md

Скрин 192318 показал два бага при скачивании:
  1. Маркеры `[img:N.M]` попадали в документ как plain text.
  2. LaTeX-команды `\\text{...}` внутри $$-блоков не распознавались парсером
     OMML и лезли сырыми литералами в Word.

Дополнительно: `\\text{...}` вне $-блоков (LLM иногда забывает обернуть) —
должен быть нормализован до простого содержимого, иначе в docx и в .md
остаются непонятные `\\text{Схема отстойника:}`.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from study_tools import docx_export, markdown_export  # noqa: E402


@pytest.fixture
def картинка(tmp_path: Path) -> Path:
    fitz = pytest.importorskip("fitz")
    путь = tmp_path / "page_23_img_1.png"
    pm = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 32), False)
    pm.set_rect(pm.irect, (220, 220, 220))
    pm.save(str(путь))
    return путь


def _resolver(путь: Path):
    """Фейковый резолвер: всё сводит к одной картинке."""
    def _(n: int, m: int):
        return (путь, f"[{n}.{m}] стр. 23 · Отстойник непрерывного действия", "OCR caption")
    return _


def test_docx_экспорт_встраивает_картинку_вместо_маркера(картинка):
    body = (
        "Схема отстойника включает вращающиеся скребки.\n\n"
        "[img:1.1] Отстойник непрерывного действия с вращающимися скребками\n\n"
        "Описание компонентов ниже."
    )

    data = docx_export(
        "Ответ",
        body,
        image_resolver=_resolver(картинка),
    )

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")
        media = [n for n in z.namelist() if n.startswith("word/media/")]

    # 1. Сырого маркера [img:1.1] в документе НЕТ
    assert "[img:1.1]" not in document_xml, (
        "Маркер [img:N.M] попал в docx как plain text — он должен быть заменён "
        "встроенной картинкой."
    )
    # 2. В архиве docx действительно лежит хотя бы одна картинка
    assert media, "В word/media/ должна быть вставленная картинка."


def test_docx_экспорт_без_резолвера_просто_удаляет_маркер():
    body = "Первый абзац.\n\n[img:1.1] подпись\n\nВторой абзац."

    data = docx_export("Ответ", body)

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert "[img:1.1]" not in document_xml
    assert "Первый абзац" in document_xml
    assert "Второй абзац" in document_xml


def test_docx_text_команда_в_формуле_рендерится_как_текст():
    """\\text{Цилиндрический корпус} внутри $$...$$ должно стать простым
    текстом внутри OMML, а не сырым литералом '\\text{...}'."""
    body = (
        "Схема отстойника:\n\n"
        r"$$\text{Схема отстойника:} 1 - \text{Цилиндрический корпус}; "
        r"2 - \text{Вращающиеся скребки}$$"
    )

    data = docx_export("Ответ", body)

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")

    # Сам OMML создан
    assert "<m:oMath" in document_xml
    # Сырые литералы \text не должны протекать в документ
    assert r"\text" not in document_xml, (
        "Команда \\text не распознана парсером — остаётся сырой в docx."
    )
    # А содержимое команд должно оказаться внутри run'ов формулы
    assert "Цилиндрический корпус" in document_xml
    assert "Вращающиеся скребки" in document_xml


def test_docx_text_команда_вне_формулы_нормализуется():
    """LLM иногда вставляет \\text{...} в обычный текст без $-обёртки.
    Тогда оно должно стать просто содержимым, а не утечь литералом."""
    body = r"В слайде сказано: \text{Осветленная жидкость} — верхний продукт."

    data = docx_export("Ответ", body)

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        document_xml = z.read("word/document.xml").decode("utf-8")

    assert r"\text" not in document_xml
    assert "Осветленная жидкость" in document_xml


def test_markdown_экспорт_встраивает_картинку_base64(картинка):
    body = "Схема.\n\n[img:1.1] Отстойник\n\nОписание."

    data = markdown_export(
        "Ответ",
        body,
        image_resolver=_resolver(картинка),
        embed_base64=True,
    )

    text = data.decode("utf-8")

    # Сырой маркер ушёл, появилась Markdown-картинка с data: URI
    assert "[img:1.1]" not in text
    assert "![" in text and "](data:image/png;base64," in text


def test_markdown_экспорт_без_резолвера_просто_удаляет_маркер():
    body = "Первый абзац.\n\n[img:1.1] подпись\n\nВторой абзац."

    data = markdown_export("Ответ", body)

    text = data.decode("utf-8")
    assert "[img:1.1]" not in text
    assert "Первый абзац" in text
    assert "Второй абзац" in text


def test_markdown_экспорт_чистит_text_команды_вне_формул():
    body = r"Это \text{важное} уточнение."
    data = markdown_export("Ответ", body)
    text = data.decode("utf-8")
    assert r"\text" not in text
    assert "важное" in text


def test_markdown_экспорт_не_трогает_formulas():
    """Внутри $$...$$ / $...$ — текст не должен быть изменён."""
    body = r"$E = mc^2$ и $$\frac{a}{b}$$"
    data = markdown_export("Ответ", body)
    text = data.decode("utf-8")
    assert "$E = mc^2$" in text
    assert r"\frac{a}{b}" in text
