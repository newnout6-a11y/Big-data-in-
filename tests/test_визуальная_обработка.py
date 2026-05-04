"""Тесты визуальной обработки страниц PDF (модуль визуальная_обработка)."""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def виз(tmp_path, monkeypatch):
    """Изолированный визуальный модуль с кэшем в tmp_path."""
    import визуальная_обработка as модуль
    importlib.reload(модуль)
    monkeypatch.setattr(модуль, "ПАПКА_КЭША", tmp_path / "pages")
    monkeypatch.setattr(модуль, "ФАЙЛ_БЮДЖЕТА", tmp_path / "budget.json")
    return модуль


def test_count_words_базово(виз):
    assert виз._count_words("") == 0
    assert виз._count_words("один два три") == 3
    assert виз._count_words("a b c d") == 0  # одиночные символы игнорируются
    assert виз._count_words("AI ML 42") == 3


def test_page_hash_стабилен(виз):
    h1 = виз._page_hash(b"hello")
    h2 = виз._page_hash(b"hello")
    h3 = виз._page_hash(b"world")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # SHA-256 hex


def test_кэш_round_trip(виз):
    ph = "abcd" * 16
    виз._write_cache(ph, {"page_hash": ph, "ocr_text": "test", "tier_used": 1})
    cached = виз._read_cache(ph)
    assert cached is not None
    assert cached["ocr_text"] == "test"
    assert cached["tier_used"] == 1


def test_кэш_возвращает_none_для_отсутствующего(виз):
    assert виз._read_cache("nonexistent") is None


def test_бюджет_пустой_по_умолчанию(виз):
    свод = виз.budget_summary()
    assert свод["total_pages"] == 0
    assert свод["estimated_cost_usd"] == 0.0


def test_бюджет_накапливает_вызовы(виз):
    виз._update_budget(tokens_in=2000, tokens_out=200)
    виз._update_budget(tokens_in=1500, tokens_out=150)
    свод = виз.budget_summary()
    assert свод["total_pages"] == 2
    # (2000+1500)*0.11/1M + (200+150)*0.34/1M = 0.000385 + 0.000119 = 0.000504
    assert свод["estimated_cost_usd"] == pytest.approx(0.0005, abs=0.0002)


def test_groq_vision_available_проверяет_env(виз, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    assert виз.groq_vision_available() is False

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert виз.groq_vision_available() is True


def test_first_groq_key_возвращает_первый_заполненный(виз, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "gsk_second")
    assert виз._first_groq_key() == "gsk_second"


def test_обработать_страницу_без_groq_возвращает_native(виз, monkeypatch):
    """Если native_text уже хороший — Tier 1/2 не запускаются."""
    # Подменяем _render_page чтобы не нужен был fitz
    monkeypatch.setattr(виз, "_render_page", lambda page, dpi=200: b"fake_png_bytes")
    monkeypatch.setattr(виз, "_ocr_page", lambda b: ("OCR_TEXT_NEVER_CALLED", 0.99))

    native = "Это нормальная страница с большим количеством слов которая должна пройти Tier 0 без всяких OCR. " * 5
    result = виз.обработать_страницу(
        page=None, page_number=1, native_text=native,
        use_groq_vision=False,
    )
    assert result.tier_used == 0
    assert result.text == native.strip()
    assert result.ocr_text == ""
    assert result.visual_caption == ""


def test_обработать_страницу_тригернет_ocr_если_текста_мало(виз, monkeypatch):
    """Если native_text короткий — должен сработать Tier 1."""
    monkeypatch.setattr(виз, "_render_page", lambda page, dpi=200: b"fake_png_bytes")
    monkeypatch.setattr(виз, "_ocr_page",
                        lambda b: ("распознанный текст со скана с большим количеством "
                                   "осмысленных слов которые покрывают порог", 0.85))

    result = виз.обработать_страницу(
        page=None, page_number=2, native_text="мало",
        use_groq_vision=False,
    )
    assert result.tier_used == 1
    assert "распознанный текст" in result.ocr_text
    assert result.visual_caption == ""


def test_обработать_страницу_кэш_попадание_не_зовёт_ocr(виз, monkeypatch):
    """Если page_hash уже в кэше — OCR/Vision не вызываются."""
    monkeypatch.setattr(виз, "_render_page", lambda page, dpi=200: b"cached_page")
    ph = виз._page_hash(b"cached_page")
    виз._write_cache(ph, {
        "page_hash": ph,
        "ocr_text": "из кэша",
        "visual_caption": "",
        "tier_used": 1,
        "confidence": 0.9,
    })
    зовы = []
    monkeypatch.setattr(виз, "_ocr_page",
                        lambda b: зовы.append("ocr") or ("not from cache", 0.0))

    result = виз.обработать_страницу(
        page=None, page_number=3, native_text="мало",
        use_groq_vision=False,
    )
    assert зовы == [], "OCR не должен зваться при попадании в кэш"
    assert result.ocr_text == "из кэша"
    assert result.tier_used == 1


def test_обработать_страницу_groq_отключён_без_api_key(виз, monkeypatch):
    """Без api_key Groq Vision не вызывается даже если включён."""
    monkeypatch.setattr(виз, "_render_page", lambda page, dpi=200: b"fake")
    monkeypatch.setattr(виз, "_ocr_page", lambda b: ("", 0.0))
    зовы = []
    monkeypatch.setattr(виз, "_call_groq_vision",
                        lambda *a, **kw: зовы.append("groq") or ("caption", 100, 50))

    result = виз.обработать_страницу(
        page=None, page_number=4, native_text="",
        use_groq_vision=True,
        groq_api_key="",  # пусто
        groq_pages_left=10,
    )
    assert зовы == [], "Groq не должен зваться без api_key"
    assert result.tier_used == 0


def test_обработать_страницу_groq_срабатывает_с_бюджетом(виз, monkeypatch):
    monkeypatch.setattr(виз, "_render_page", lambda page, dpi=200: b"fake_for_groq")
    monkeypatch.setattr(виз, "_ocr_page", lambda b: ("", 0.0))
    monkeypatch.setattr(виз, "_call_groq_vision",
                        lambda *a, **kw: ("На странице график зависимости X от Y", 1500, 50))

    result = виз.обработать_страницу(
        page=None, page_number=5, native_text="",
        use_groq_vision=True,
        groq_api_key="gsk_test",
        groq_pages_left=10,
    )
    assert result.tier_used == 2
    assert "график" in result.visual_caption
    свод = виз.budget_summary()
    assert свод["total_pages"] == 1


def test_обработать_страницу_groq_не_зовётся_если_бюджет_исчерпан(виз, monkeypatch):
    monkeypatch.setattr(виз, "_render_page", lambda page, dpi=200: b"fake_2")
    monkeypatch.setattr(виз, "_ocr_page", lambda b: ("", 0.0))
    зовы = []
    monkeypatch.setattr(виз, "_call_groq_vision",
                        lambda *a, **kw: зовы.append("g") or ("c", 0, 0))

    result = виз.обработать_страницу(
        page=None, page_number=6, native_text="",
        use_groq_vision=True,
        groq_api_key="gsk_test",
        groq_pages_left=0,  # бюджет исчерпан
    )
    assert зовы == []
    assert result.tier_used == 0
