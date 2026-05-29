"""Регрессии под второй раунд аудита (утечки + мёртвая фича).

C1. ingest_uploaded_files: при ошибке индексации удаляет осиротевший файл.
C2. найти_похожие(новая_схема): фильтр «по кейсу» реально применяется.
C3. _загрузить_qdrant_cached: умеет очищаться при смене локальной БД.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- C1: cleanup осиротевших файлов ----------

class _StubClient:
    def __init__(self):
        self.upserted = []

    def get_collections(self):
        from types import SimpleNamespace
        return SimpleNamespace(collections=[])

    def create_collection(self, *a, **kw):
        pass

    def create_payload_index(self, *a, **kw):
        pass

    def upsert(self, collection_name, points):
        self.upserted.extend(points)

    def count(self, *a, **kw):
        from types import SimpleNamespace
        return SimpleNamespace(count=0)

    def delete(self, *a, **kw):
        pass


class _StubModel:
    def encode(self, texts, normalize_embeddings=False, show_progress_bar=False):
        import numpy as np
        # 768-d вектор того же типа что multilingual-e5-base
        return np.zeros((len(texts), 768), dtype="float32")


@pytest.fixture
def изолированные_тетради(tmp_path, monkeypatch):
    """Перенаправляет notebooks. на временные пути и возвращает свежий модуль."""
    sys.modules.pop("notebooks", None)
    import notebooks as nb

    monkeypatch.setattr(nb, "BASE_DIR", tmp_path)
    monkeypatch.setattr(nb, "USER_DOCUMENTS_DIR", tmp_path / "user_documents")
    monkeypatch.setattr(
        nb, "NOTEBOOKS_FILE", tmp_path / "user_documents" / "notebooks.json"
    )
    monkeypatch.setattr(nb, "EXTRACTED_IMAGES_DIR", tmp_path / "extracted_images")
    monkeypatch.setattr(nb, "HIGHLIGHTS_DIR", tmp_path / "user_documents" / "highlights")
    return nb


def test_C1_target_удаляется_при_ошибке_ingest(изолированные_тетради, monkeypatch):
    """Если build_chunks вернул [] (или upsert упал) — PDF не должен оставаться
    на диске сиротой. Раньше файл писался target.write_bytes(data) и при
    `continue` оставался навсегда, копясь со временем."""
    nb = изолированные_тетради

    тетрадь = nb.create_notebook("test_C1", "u_test")

    # Эмулируем валидный PDF, но build_chunks вернёт [] — это путь
    # «не удалось извлечь текст», который попадает в summary["errors"]
    # и делает continue.
    pdf_данные = b"%PDF-1.4 fake but >50 bytes" + b"\n0" * 100

    # Заменяем извлечение страниц на пустой результат
    monkeypatch.setattr(nb, "extract_pages", lambda *a, **kw: [])

    итог = nb.ingest_uploaded_files(
        _StubClient(),
        _StubModel(),
        тетрадь["id"],
        [("test.pdf", pdf_данные)],
        user_id="u_test",
    )

    # Ошибка зафиксирована
    assert any("test.pdf" in e for e in итог["errors"])
    # Файлы в тетради не появились
    assert итог["added_files"] == 0
    # На диске ничего не осталось
    files_dir = nb.USER_DOCUMENTS_DIR / "u_test" / тетрадь["id"] / "files"
    оставшиеся = list(files_dir.glob("*")) if files_dir.exists() else []
    assert оставшиеся == [], (
        f"После неудачной индексации остались сиротские файлы: {оставшиеся}"
    )


def test_C1_target_удаляется_при_исключении_в_upsert(изолированные_тетради, monkeypatch):
    """Если upsert_chunks бросает исключение — файл тоже должен удаляться."""
    nb = изолированные_тетради
    тетрадь = nb.create_notebook("test_C1b", "u_test")

    pdf_данные = b"%PDF-1.4 stub content" + b"x" * 200

    # Эмулируем что extract_pages вернул нормальный текст
    monkeypatch.setattr(nb, "extract_pages",
                        lambda *a, **kw: [{"page": 1, "text": "Какой-то текст. " * 30, "images": []}])

    class FailingClient(_StubClient):
        def upsert(self, *a, **kw):
            raise RuntimeError("Qdrant down")

    итог = nb.ingest_uploaded_files(
        FailingClient(),
        _StubModel(),
        тетрадь["id"],
        [("crash.pdf", pdf_данные)],
        user_id="u_test",
    )

    assert any("Qdrant down" in e for e in итог["errors"])
    assert итог["added_files"] == 0

    files_dir = nb.USER_DOCUMENTS_DIR / "u_test" / тетрадь["id"] / "files"
    оставшиеся = list(files_dir.glob("*")) if files_dir.exists() else []
    assert оставшиеся == []


def test_C1_target_сохраняется_при_успешной_индексации(изолированные_тетради, monkeypatch):
    """Sanity check: успешный ingest не должен удалять файл."""
    nb = изолированные_тетради
    тетрадь = nb.create_notebook("test_C1c", "u_test")

    pdf_данные = b"%PDF-1.4 working file" + b"y" * 200

    monkeypatch.setattr(nb, "extract_pages",
                        lambda *a, **kw: [{"page": 1, "text": "Содержательный текст. " * 30, "images": []}])

    итог = nb.ingest_uploaded_files(
        _StubClient(),
        _StubModel(),
        тетрадь["id"],
        [("ok.pdf", pdf_данные)],
        user_id="u_test",
    )
    assert итог["added_files"] == 1
    assert итог["chunks"] >= 1

    files_dir = nb.USER_DOCUMENTS_DIR / "u_test" / тетрадь["id"] / "files"
    assert any(p.name.endswith("ok.pdf") for p in files_dir.iterdir())


# ---------- C2: фильтр по кейсу реально применяется в новой схеме ----------

def test_C2_фильтр_по_кейсу_передаётся_в_новой_схеме(monkeypatch):
    """Регрессия: ранее в новой схеме был выбранный_кейс=None, и UI-селектор
    «Фильтр по кейсу» становился декоративным. Теперь должно влиять на
    Filter, который попадает в query_points."""
    sys.modules.pop("app", None)
    import app

    # Подменяем модель и Qdrant-клиент на заглушки
    class FakeModel:
        def encode(self, текст, normalize_embeddings=True):
            import numpy as np
            return np.zeros(768)

    class FakeResp:
        points = []

    captured = {}

    class FakeClient:
        def query_points(self, **kwargs):
            captured["filter"] = kwargs.get("query_filter") or kwargs.get("filter")
            return FakeResp()

    monkeypatch.setattr(app, "загрузить_модель", lambda: FakeModel())
    monkeypatch.setattr(app, "загрузить_qdrant", lambda: FakeClient())
    # выбрать_коллекцию: новая_схема=True, гибрид=False (чтобы не делать sparse)
    monkeypatch.setattr(app, "выбрать_коллекцию", lambda: ("knowledge", True, False))

    app.найти_похожие(
        "тестовый вопрос",
        выбранный_кейс="оптимизация_реакции",
        количество=5,
    )

    фильтр = captured.get("filter")
    assert фильтр is not None
    # У Filter есть поле .must со списком FieldCondition'ов
    must = фильтр.must
    keys = [c.key for c in must]
    assert "case" in keys, (
        "Фильтр по кейсу не передан в Qdrant-запрос — UI-селектор остался "
        "мёртвой фичей. keys=" + repr(keys)
    )


def test_C2_фильтр_все_кейсы_не_добавляет_условие(monkeypatch):
    """Sanity: при «Все кейсы» условие на case не добавляется."""
    sys.modules.pop("app", None)
    import app

    class FakeModel:
        def encode(self, текст, normalize_embeddings=True):
            import numpy as np
            return np.zeros(768)

    captured = {}

    class FakeResp:
        points = []

    class FakeClient:
        def query_points(self, **kwargs):
            captured["filter"] = kwargs.get("query_filter")
            return FakeResp()

    monkeypatch.setattr(app, "загрузить_модель", lambda: FakeModel())
    monkeypatch.setattr(app, "загрузить_qdrant", lambda: FakeClient())
    monkeypatch.setattr(app, "выбрать_коллекцию", lambda: ("knowledge", True, False))

    app.найти_похожие("тест", выбранный_кейс="все", количество=5)

    фильтр = captured.get("filter")
    if фильтр is None:
        # Никаких условий вообще — это тоже корректно (no filter)
        return
    keys = [c.key for c in фильтр.must]
    assert "case" not in keys, "при 'все' кейсах фильтр на case не должен ставиться"


# ---------- C3: cache_resource clear ----------

def test_C3_qdrant_кэш_очищается_при_смене_базы():
    """`@st.cache_resource` должен иметь доступный `.clear()` — чтобы при
    смене локальной базы освободить старый клиент. Если streamlit-API
    изменится, тест зафиксирует регрессию."""
    sys.modules.pop("app", None)
    import app

    # Декорированная функция должна иметь .clear() (streamlit API)
    assert hasattr(app._загрузить_qdrant_cached, "clear"), (
        "У @st.cache_resource нет .clear() — фикс C3 (очистка при смене БД) "
        "перестал работать."
    )
    # Вызов .clear() не должен падать
    app._загрузить_qdrant_cached.clear()
