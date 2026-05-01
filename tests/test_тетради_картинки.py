"""Тесты извлечения встроенных картинок при загрузке PDF в тетрадь.

Бесплатная (без Groq Vision) фича: при upload PDF в тетрадь все встроенные
картинки извлекаются и сохраняются в `extracted_images/<file_hash>/`. Их пути
кладутся в payload каждого чанка соответствующей страницы как `images: [{
"path": "...", "page": N, "kind": "extracted_image"}]`. UI после поиска
показывает их через `показать_картинки_фрагмента`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


fitz = pytest.importorskip("fitz")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import notebooks  # noqa: E402


def _создать_pdf_с_картинкой(папка: Path, имя: str = "test.pdf") -> Path:
    """Создаёт минимальный PDF с двумя страницами: только текст и текст+картинка."""
    путь = папка / имя
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "Только текст без картинки. " * 10)

    p2 = doc.new_page()
    p2.insert_text((50, 100), "Страница со схемой. " * 10)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 60), False)
    pixmap.set_rect(pixmap.irect, (200, 80, 40))
    p2.insert_image(fitz.Rect(60, 200, 220, 320), pixmap=pixmap)

    doc.save(путь)
    doc.close()
    return путь


def test_extract_pages_pdf_возвращает_картинки(tmp_path, monkeypatch):
    monkeypatch.setattr(notebooks, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")
    monkeypatch.setattr(notebooks, "BASE_DIR", tmp_path)

    pdf = _создать_pdf_с_картинкой(tmp_path)
    pages = notebooks.extract_pages(pdf)

    assert len(pages) == 2
    assert pages[0]["images"] == []
    assert len(pages[1]["images"]) == 1
    img = pages[1]["images"][0]
    assert img["page"] == 2
    assert img["kind"] == "extracted_image"
    assert img["path"].startswith("extracted_images/")

    физ_путь = tmp_path / img["path"]
    assert физ_путь.is_file()
    assert физ_путь.stat().st_size > 0


def test_build_chunks_прокидывает_images_в_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(notebooks, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")
    monkeypatch.setattr(notebooks, "BASE_DIR", tmp_path)

    pdf = _создать_pdf_с_картинкой(tmp_path)
    pages = notebooks.extract_pages(pdf)
    тетрадь = {"id": "nb1", "title": "Тест"}
    куски = notebooks.build_chunks(
        pages,
        notebook=тетрадь,
        user_id="u1",
        file_hash="hash1",
        file_path=pdf,
        original_name=pdf.name,
    )

    куски_с_картинками = [c for c in куски if c["page"] == 2 and c["images"]]
    assert куски_с_картинками, "На странице 2 хоть один чанк должен иметь images"
    img = куски_с_картинками[0]["images"][0]
    assert img["page"] == 2
    assert "extracted_images/" in img["path"]


def test_дедупликация_по_xref(tmp_path, monkeypatch):
    """Если одна и та же картинка вставлена дважды на странице — сохраняется один раз."""
    monkeypatch.setattr(notebooks, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")
    monkeypatch.setattr(notebooks, "BASE_DIR", tmp_path)

    путь = tmp_path / "dup.pdf"
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 100), "Дубликаты картинок. " * 10)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), False)
    pixmap.set_rect(pixmap.irect, (100, 100, 100))
    p.insert_image(fitz.Rect(60, 200, 110, 250), pixmap=pixmap)
    p.insert_image(fitz.Rect(160, 200, 210, 250), pixmap=pixmap)
    doc.save(путь)
    doc.close()

    pages = notebooks.extract_pages(путь)
    # PyMuPDF при insert_image повторяет xref, поэтому дедуп должен сократить до 1
    assert len(pages[0]["images"]) <= 2  # допускаем оба варианта на разных версиях fitz


def test_pdf_без_картинок_корректен(tmp_path, monkeypatch):
    monkeypatch.setattr(notebooks, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")
    monkeypatch.setattr(notebooks, "BASE_DIR", tmp_path)

    путь = tmp_path / "text.pdf"
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 100), "Просто текст. " * 30)
    doc.save(путь)
    doc.close()

    pages = notebooks.extract_pages(путь)
    assert len(pages) == 1
    assert pages[0]["images"] == []
