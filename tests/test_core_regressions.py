"""Регрессии повторной индексации тетрадей и экспорта Anki без внешних API."""
from __future__ import annotations

import io
import sqlite3
import zipfile

import numpy as np
import pytest
from qdrant_client import QdrantClient


class _Model:
    def encode(self, texts, **kwargs):
        return np.asarray([[1.0, 0.0, 0.0] for _ in texts])


@pytest.fixture
def indexed_notebook(tmp_path, monkeypatch):
    import notebooks as nb

    monkeypatch.setattr(nb, "USER_DOCUMENTS_DIR", tmp_path / "documents")
    monkeypatch.setattr(nb, "NOTEBOOKS_FILE", tmp_path / "documents" / "notebooks.json")
    monkeypatch.setattr(nb, "VECTOR_SIZE", 3)
    notebook = nb.create_notebook("OCR regression", "user")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"test PDF placeholder")
    notebook["files"] = [{
        "name": "sample.pdf", "path": str(pdf_path), "type": "pdf", "file_hash": "file1",
        "chunks": 2,
    }]
    store = nb.load_store("user")
    store["users"]["user"]["notebooks"] = [notebook]
    nb.save_store(store)
    client = QdrantClient(":memory:")
    monkeypatch.setattr(nb, "ensure_collection", lambda client, notebook: None)
    from qdrant_client.models import Distance, VectorParams
    client.create_collection(notebook["collection"], vectors_config=VectorParams(size=3, distance=Distance.COSINE))
    pages = [
        {"page": 1, "text": "Unchanged content about chemistry. " * 4},
        {"page": 2, "text": "Old content that OCR will replace. " * 4},
    ]
    chunks = nb.build_chunks(pages, notebook=notebook, user_id="user", file_hash="file1",
                             file_path=pdf_path, original_name="sample.pdf")
    unrelated = nb.build_chunks(pages[:1], notebook=notebook, user_id="user", file_hash="other-file",
                                file_path=pdf_path, original_name="other.pdf")
    nb.upsert_chunks(client, _Model(), notebook["collection"], chunks + unrelated)
    yield nb, notebook, client, pages
    client.close()


@pytest.mark.parametrize("failure", ["extract", "empty", "encode", "upsert"])
def test_failed_ocr_reindex_preserves_existing_points(indexed_notebook, monkeypatch, failure):
    nb, notebook, client, pages = indexed_notebook
    before, _ = client.scroll(notebook["collection"], limit=20, with_payload=True)

    def fail(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(nb, "_extract_pdf", fail if failure == "extract" else lambda *a, **kw: [] if failure == "empty" else pages)
    model = _Model()
    if failure == "encode":
        monkeypatch.setattr(model, "encode", fail)
    if failure == "upsert":
        monkeypatch.setattr(client, "upsert", fail)

    with pytest.raises((RuntimeError, ValueError)):
        nb.переиндексировать_файл_с_ocr(client, model, notebook["id"], "file1", user_id="user")

    after, _ = client.scroll(notebook["collection"], limit=20, with_payload=True)
    assert {p.id: p.payload for p in after} == {p.id: p.payload for p in before}
    stored = nb.get_notebook(notebook["id"], "user")["files"][0]
    assert "reindexed_at" not in stored


def test_successful_ocr_reindex_replaces_only_obsolete_points(indexed_notebook, monkeypatch):
    nb, notebook, client, pages = indexed_notebook
    updated = [pages[0], {"page": 3, "text": "Newly recognized OCR content. " * 4}]
    monkeypatch.setattr(nb, "_extract_pdf", lambda *args, **kwargs: updated)

    result = nb.переиндексировать_файл_с_ocr(client, _Model(), notebook["id"], "file1", user_id="user")

    points, _ = client.scroll(notebook["collection"], limit=20, with_payload=True)
    file_points = [point.payload for point in points if point.payload["file_hash"] == "file1"]
    assert sorted(point["page"] for point in file_points) == [1, 3]
    assert len(points) == 3  # Другой файл тетради сохранён.
    assert result == {"chunks": 2, "pages": 2}
    stored = nb.get_notebook(notebook["id"], "user")["files"][0]
    assert stored["use_ocr"] is True
    assert stored["chunks"] == 2


def test_anki_export_keeps_angle_brackets_and_ampersands_as_text(tmp_path):
    pytest.importorskip("genanki")
    from study_tools import build_apkg

    package = build_apkg([{
        "front": "Что означает 0 < p < 1 & T > 0?",
        "back": "A < B; метка <sample> & значение",
        "source": "Глава <2> & примеры",
    }], "Chemistry")
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        database = tmp_path / "collection.anki2"
        database.write_bytes(archive.read("collection.anki2"))
    with sqlite3.connect(database) as connection:
        fields = connection.execute("SELECT flds FROM notes").fetchone()[0].split("\x1f")
    assert "0 &lt; p &lt; 1 &amp; T &gt; 0" in fields[0]
    assert "&lt;sample&gt; &amp;" in fields[1]
    assert "<small>Глава &lt;2&gt; &amp; примеры</small>" in fields[1]
