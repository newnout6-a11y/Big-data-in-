"""Регрессия: easyocr под капотом использует cv2.imread, который на Windows
не открывает файлы с не-ASCII путями (например, кириллицей в C:\\Big data in химия\\).

Поэтому _ocr_картинки должно читать байты файла само (np.fromfile + cv2.imdecode)
и передавать готовый ndarray в reader.readtext, а не путь.

Без этого фикса OCR молча возвращал пустую строку для ВСЕХ картинок проекта,
и страницы со схемами (где ключевой текст только в растре) были невидимы для
поиска.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

fitz = pytest.importorskip("fitz")
cv2 = pytest.importorskip("cv2")

import notebooks  # noqa: E402


@pytest.fixture
def непустой_файл(tmp_path: Path) -> Path:
    # Подкаталог с кириллицей в имени — имитируем условие, на котором
    # ломается cv2.imread в реальном проекте (C:\Big data in химия\…).
    каталог = tmp_path / "химия_путь"
    каталог.mkdir()
    путь = каталог / "page_23_img_1.png"
    # Валидный PNG через fitz (он уже есть в зависимостях проекта).
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 32), False)
    pixmap.set_rect(pixmap.irect, (220, 220, 220))
    pixmap.save(str(путь))
    assert путь.stat().st_size > 0
    return путь


def test_ocr_читает_байтами_а_не_путем(непустой_файл, monkeypatch):
    """_ocr_картинки должна вызывать reader.readtext с numpy-массивом, а не строкой пути.
    Это гарантирует, что не-ASCII пути на Windows не ломают OCR."""
    captured: dict = {}

    class FakeReader:
        def readtext(self, изображение, detail=0, paragraph=True):
            captured["arg_type"] = type(изображение).__name__
            captured["is_str"] = isinstance(изображение, str)
            return ["Отстойник непрерывного действия"]

    monkeypatch.setattr(notebooks, "_получить_easyocr_reader", lambda: FakeReader())

    результат = notebooks._ocr_картинки(непустой_файл)

    assert "Отстойник" in результат
    assert captured.get("is_str") is False, (
        "_ocr_картинки передал строку-путь в readtext — на не-ASCII путях это сломает OpenCV. "
        "Нужно читать байты через np.fromfile + cv2.imdecode и передавать ndarray."
    )
    # numpy.ndarray — что мы и ожидаем после imdecode
    assert captured.get("arg_type") == "ndarray"


def test_ocr_возвращает_пустую_строку_если_файл_не_декодируется(tmp_path, monkeypatch):
    """Если cv2.imdecode не смог распарсить (битый файл) — возвращаем пусто, а не падаем."""
    путь = tmp_path / "битый.png"
    путь.write_bytes(b"not a png at all")

    class FakeReader:
        def readtext(self, *_a, **_kw):  # pragma: no cover — не должно вызываться
            raise AssertionError("readtext не должен вызываться, если imdecode вернул None")

    monkeypatch.setattr(notebooks, "_получить_easyocr_reader", lambda: FakeReader())

    результат = notebooks._ocr_картинки(путь)
    assert результат == ""
