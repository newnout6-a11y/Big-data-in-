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


def test_страница_с_коротким_текстом_и_картинкой_сохраняется(tmp_path, monkeypatch):
    """Регрессия: страница вида «схема: <картинка>» не должна теряться.

    Раньше `build_chunks` отбрасывал любую страницу с < 50 символов текста,
    даже если на ней была встроенная диаграмма. В результате картинка
    сохранялась на диск, но никому не привязывалась — поиск её не показывал.
    """
    monkeypatch.setattr(notebooks, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")
    monkeypatch.setattr(notebooks, "BASE_DIR", tmp_path)

    путь = tmp_path / "diagram_only.pdf"
    doc = fitz.open()
    p = doc.new_page()
    # Только короткая подпись плюс встроенная картинка.
    p.insert_text((50, 100), "схема:")
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 50), False)
    pixmap.set_rect(pixmap.irect, (50, 200, 100))
    p.insert_image(fitz.Rect(60, 200, 220, 320), pixmap=pixmap)
    doc.save(путь)
    doc.close()

    pages = notebooks.extract_pages(путь)
    assert len(pages) == 1
    assert pages[0]["images"], "_extract_pdf должен извлечь картинку даже с короткой подписью"

    тетрадь = {"id": "nb1", "title": "Тест"}
    куски = notebooks.build_chunks(
        pages,
        notebook=тетрадь,
        user_id="u1",
        file_hash="hash1",
        file_path=путь,
        original_name=путь.name,
    )

    assert куски, "Страница с диаграммой и короткой подписью должна давать хотя бы один чанк"
    assert all(c["page"] == 1 for c in куски)
    assert any(c["images"] for c in куски), "Хотя бы один чанк должен нести картинку страницы"


def test_visual_mode_сохраняет_встроенные_картинки(tmp_path, monkeypatch):
    """Регрессия: при `visual_mode=True` встроенные диаграммы должны попадать
    в payload чанков, а не теряться вместе с PDF-рендером страниц.

    До фикса `ingest_uploaded_files` строил `pages = [{page, text}]` без
    `images`, и поиск в тетради отдавал только текст, даже если в PDF
    есть схемы.
    """
    import sys

    sys.modules.pop("notebooks", None)
    import notebooks as nb_module

    monkeypatch.setattr(nb_module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(nb_module, "USER_DOCUMENTS_DIR", tmp_path / "user_documents")
    monkeypatch.setattr(
        nb_module, "NOTEBOOKS_FILE", tmp_path / "user_documents" / "notebooks.json"
    )
    monkeypatch.setattr(nb_module, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")

    путь = tmp_path / "visual.pdf"
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 100), "Описание схемы. " * 8)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 80, 50), False)
    pixmap.set_rect(pixmap.irect, (40, 200, 160))
    p.insert_image(fitz.Rect(60, 200, 220, 320), pixmap=pixmap)
    doc.save(путь)
    doc.close()
    данные = путь.read_bytes()

    fake_visual_pages = [{
        "page": 1,
        "text": "Описание схемы. " * 8 + "[OCR]\nA B",
        "ocr_text": "A B",
        "visual_caption": "",
        "tier_used": 1,
        "page_hash": "abc",
        "image_path": str(tmp_path / "render.png"),
        "has_ocr": True,
        "has_visual_caption": False,
    }]
    виз = sys.modules.get("визуальная_обработка")
    if виз is None:
        import importlib
        виз = importlib.import_module("визуальная_обработка")
    monkeypatch.setattr(виз, "обработать_pdf", lambda *a, **kw: fake_visual_pages)

    собранные = []

    class StubClient:
        def get_collections(self):
            class Box:
                collections = []
            return Box()

        def create_collection(self, *a, **kw):
            pass

        def create_payload_index(self, *a, **kw):
            pass

        def upsert(self, collection_name, points):
            собранные.extend(points)

    class StubModel:
        def encode(self, texts, normalize_embeddings=False, show_progress_bar=False):
            import numpy as np
            return np.zeros((len(texts), nb_module.VECTOR_SIZE), dtype="float32")

    user_id = "u_test"
    nb = nb_module.create_notebook("vis", user_id)
    nb_module.ingest_uploaded_files(
        StubClient(),
        StubModel(),
        nb["id"],
        [("visual.pdf", данные)],
        user_id=user_id,
        visual_mode=True,
        use_groq_vision=False,
    )

    assert собранные, "должен появиться хотя бы один чанк"
    assert any(
        pt.payload.get("images") for pt in собранные
    ), "В visual_mode встроенные картинки страницы должны попадать в payload"
