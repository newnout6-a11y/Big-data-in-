"""Регрессии под аудит-фиксы (Critical-уровень).

C1. embed_resume_v2: стабильные ID + дедуп по text_hash.
C2. визуальная_обработка.обработать_pdf: не дропает страницы с одной диаграммой.
C3. harvester/state: уже_скачан/пометить_скачанным работают за O(1) на больших set'ах.
"""
from __future__ import annotations

import json
import time
import uuid


# ---------- C1: стабильные ID embed_resume_v2 ----------

def test_C1_id_зависит_только_от_text_hash():
    """Один и тот же text_hash → один и тот же UUID. Разный → разный."""
    from embed_resume_v2 import _id_для_чанка

    чанк_a = {"text": "что-то", "text_hash": "deadbeef"}
    чанк_b = {"text": "другое", "text_hash": "deadbeef"}  # тот же hash
    чанк_c = {"text": "что-то", "text_hash": "cafebabe"}

    id_a = _id_для_чанка(чанк_a)
    id_b = _id_для_чанка(чанк_b)
    id_c = _id_для_чанка(чанк_c)

    # Парсится как UUID
    uuid.UUID(id_a)

    # Идемпотентность: одинаковый text_hash → одинаковый id
    assert id_a == id_b, "ID должен зависеть только от text_hash"
    # Разные hash → разные id
    assert id_a != id_c


def test_C1_id_не_зависит_от_позиции_в_файле():
    """Перетасовка чанков не должна менять их id (защита от reorder в jsonl)."""
    from embed_resume_v2 import _id_для_чанка

    чанки = [
        {"text": f"тест {i}", "text_hash": f"hash-{i}"} for i in range(5)
    ]
    id_по_порядку = [_id_для_чанка(ч) for ч in чанки]
    # Перевернули — id должны остаться теми же для тех же чанков
    id_наоборот = [_id_для_чанка(ч) for ч in reversed(чанки)]
    assert id_по_порядку == list(reversed(id_наоборот))


def test_C1_fallback_на_текст_если_нет_text_hash():
    """text_hash может отсутствовать (теоретически) — fallback на хэш текста."""
    from embed_resume_v2 import _id_для_чанка

    чанк_1 = {"text": "тестовый текст"}
    чанк_2 = {"text": "тестовый текст"}
    чанк_3 = {"text": "другой текст"}

    assert _id_для_чанка(чанк_1) == _id_для_чанка(чанк_2)
    assert _id_для_чанка(чанк_1) != _id_для_чанка(чанк_3)


# ---------- C2: визуальная_обработка не дропает страницы без текста ----------

def test_C2_страница_только_с_диаграммой_не_теряется(tmp_path, monkeypatch):
    """Страница без OCR-результата и без текста, но с встроенной картинкой —
    не выкидывается из обработать_pdf. Раньше `if combined_text < 40: continue`
    дропал её, и встроенные диаграммы оставались сиротами в payload.

    Проверяем поведение функции напрямую через мок-страниц."""
    from визуальная_обработка import обработать_pdf, СтраницаВизуал
    import визуальная_обработка as виз

    # Замоканная версия `обработать_страницу`, возвращающая «нет текста, нет OCR»
    def фейк_обработать_страницу(page, idx, native_text, **kwargs):
        return СтраницаВизуал(
            page_number=idx,
            text="",
            ocr_text="",
            visual_caption="",
            tier_used=0,
            page_hash=f"page_{idx}_hash",
            image_path="",
        )

    # Замокаем fitz.open, чтобы вернуть «PDF» из 3 страниц
    class ФейкДок:
        def __init__(self):
            self.страницы = [object(), object(), object()]
        def __iter__(self):
            return iter(self.страницы)
        def close(self):
            pass

    class ФейкFitz:
        @staticmethod
        def open(_):
            return ФейкДок()

    # PDF файл должен существовать (read_bytes для file_hash)
    путь = tmp_path / "fake.pdf"
    путь.write_bytes(b"%PDF-1.4 stub")

    monkeypatch.setattr(виз, "fitz", ФейкFitz)
    monkeypatch.setattr(виз, "обработать_страницу", фейк_обработать_страницу)

    pages = обработать_pdf(путь, save_images=False)

    # Все 3 страницы должны попасть в результат, даже без текста.
    # Раньше тут возвращался [] из-за `if len(combined_text) < 40: continue`.
    assert len(pages) == 3
    assert [p["page"] for p in pages] == [1, 2, 3]
    assert all(p["text"] == "" for p in pages)
    assert all(p["tier_used"] == 0 for p in pages)


# ---------- C3: O(1) lookup в harvester/state ----------

def test_C3_уже_скачан_работает_за_o1_на_больших_state():
    """С новым in-memory set'ом уже_скачан должен быть O(1).

    Регрессия: раньше каждый вызов делал set(state['downloaded_ids']),
    что давало O(n) на каждый вызов и O(n²) на полный harvest.
    """
    from harvester import state

    # Готовим state с 50000 уже скачанных id (больше чем реальный масштаб).
    с = state._значения_по_умолчанию()
    state._добавить_индексы(с)
    for i in range(50_000):
        с["downloaded_ids"].append(f"arxiv:2024.{i:05d}")
        с["normalized_ids"].append(f"arxiv:2024.{i:05d}")
        с["_downloaded_set"].add(f"arxiv:2024.{i:05d}")
        с["_normalized_set"].add(f"arxiv:2024.{i:05d}")

    # Замеряем 5000 lookup'ов. Должно быть существенно меньше секунды
    # (на нормальной машине ~10 мс). Ставим запас 1.5 с — даже под нагрузкой
    # пройдёт, при O(n²) — нет.
    старт = time.perf_counter()
    for i in range(5_000):
        # часть найдётся (hit), часть нет (miss)
        state.уже_скачан(с, f"arxiv:2024.{i:05d}")
        state.уже_скачан(с, f"openalex:10.1234/missing-{i}")
    прошло = time.perf_counter() - старт

    assert прошло < 1.5, f"уже_скачан слишком медленный: {прошло:.2f}s"


def test_C3_set_не_попадает_в_сериализованный_json(tmp_path, monkeypatch):
    """`_downloaded_set`/`_normalized_set` — внутренние индексы, в JSON не пишем."""
    from harvester import state

    фейк = tmp_path / "state.json"
    monkeypatch.setattr(state, "ФАЙЛ_СОСТОЯНИЯ", str(фейк))

    с = state._значения_по_умолчанию()
    state._добавить_индексы(с)
    state.пометить_скачанным(с, "arxiv:2304.12345")
    state.сохранить(с)

    с_диска = json.loads(фейк.read_text(encoding="utf-8"))
    assert "_downloaded_set" not in с_диска
    assert "_normalized_set" not in с_диска
    # Оригинальные списки сохраняются как обычно
    assert "arxiv:2304.12345" in с_диска["downloaded_ids"]


def test_C3_миграция_старого_state_строит_set():
    """После прочитать() из старого state set'ы построились — следующий уже_скачан O(1)."""
    from harvester import state

    # _значения_по_умолчанию + миграция должны добавить set'ы.
    с = state._добавить_индексы(state._значения_по_умолчанию())
    assert isinstance(с["_downloaded_set"], set)
    assert isinstance(с["_normalized_set"], set)


def test_C3_пометить_скачанным_синхронизирует_set_и_список():
    """Set и list должны оставаться согласованными."""
    from harvester import state

    с = state._добавить_индексы(state._значения_по_умолчанию())
    state.пометить_скачанным(с, "arxiv:2304.12345")

    assert "arxiv:2304.12345" in с["downloaded_ids"]
    assert "arxiv:2304.12345" in с["_downloaded_set"]
    assert "arxiv:2304.12345" in с["_normalized_set"]
    assert state.уже_скачан(с, "arxiv:2304.12345")


# ---------- H6: единый SHA-256 для file_hash ----------

def test_H6_file_hash_использует_sha256(tmp_path):
    """notebooks._file_hash должен возвращать SHA-256, как и остальные модули."""
    import hashlib

    from notebooks import _file_hash

    данные = b"test PDF content"
    путь = tmp_path / "test.pdf"
    путь.write_bytes(данные)

    результат = _file_hash(путь)
    ожидание = hashlib.sha256(данные).hexdigest()

    assert результат == ожидание
    assert len(результат) == 64  # SHA-256 hex = 64 символа (SHA-1 был бы 40)


# ---------- H7: notebook_fragments не выставляет фейковый score ----------

def test_H7_notebook_fragments_не_добавляет_score():
    """Фрагменты от scroll'а — это перечисление документов тетради, не поиск.
    Раньше payload получал бессмысленный score=0.0 — теперь поле просто
    отсутствует, чтобы UI не путался с retrieval-результатами."""
    from types import SimpleNamespace

    import notebooks

    # Мок Qdrant client: возвращает один батч из двух точек, потом stop
    class ФейкКлиент:
        def __init__(self):
            self.вызовов = 0

        def get_collections(self):
            return SimpleNamespace(collections=[SimpleNamespace(name="user_nb_test")])

        def create_collection(self, *a, **kw):
            pass

        def create_payload_index(self, *a, **kw):
            pass

        def scroll(self, **kw):
            self.вызовов += 1
            if self.вызовов > 1:
                return [], None
            return [
                SimpleNamespace(payload={"text": "первый", "page": 1, "document": "doc.pdf"}),
                SimpleNamespace(payload={"text": "второй", "page": 2, "document": "doc.pdf"}),
            ], None

    тетрадь = {"id": "nb-test", "collection": "user_nb_test", "files": []}
    клиент = ФейкКлиент()

    результат = notebooks.notebook_fragments(клиент, тетрадь, user_id="u1")

    assert len(результат) == 2
    for фр in результат:
        assert "score" not in фр, "scroll-результаты не должны содержать поля score"
