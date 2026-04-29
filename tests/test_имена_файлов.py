"""Тесты человекочитаемых имён файлов в harvester/run.py."""
from __future__ import annotations

from harvester.run import _безопасное_имя, _слаг


def test_слаг_кириллицу_транслитерирует():
    assert _слаг("Цифровая модель местности") == "tsifrovaya-model-mestnosti"


def test_слаг_английский_лоуэркейс_дефисы():
    assert _слаг("Recursive Multi-Agent Systems") == "recursive-multi-agent-systems"


def test_слаг_спецсимволы_убираются():
    assert _слаг("HYG-mol: An Interpretable, Multimodal!") == "hyg-mol-an-interpretable-multimodal"


def test_слаг_не_рвёт_слово_при_обрезании():
    из = "abcdefghij " * 20
    результат = _слаг(из, макс_длина=30)
    # последний дефис — на границе слова, ничего не обрывается посередине
    assert not результат.endswith("-")
    assert len(результат) <= 30


def test_безопасное_имя_короткий_id():
    имя = _безопасное_имя("arxiv:2604.25917v1", "x.pdf", заголовок="Recursive Multi-Agent Systems")
    assert имя == "recursive-multi-agent-systems__arxiv-2604.25917v1.pdf"


def test_безопасное_имя_длинный_id_получает_хэш():
    """Когда doc_id длинный (например URL), он обрезается + добавляется хэш для уникальности."""
    имя1 = _безопасное_имя(
        "cyberleninka:https://cyberleninka.ru/article/n/aaa/pdf", "",
        заголовок="Обзор исследований",
    )
    имя2 = _безопасное_имя(
        "cyberleninka:https://cyberleninka.ru/article/n/bbb/pdf", "",
        заголовок="Обзор исследований",
    )
    # Заголовки одинаковые — но хэш разный, файлы не коллидируют
    assert имя1 != имя2
    assert имя1.endswith(".pdf")
    assert "obzor-issledovaniy__" in имя1


def test_безопасное_имя_пустой_заголовок_только_id():
    имя = _безопасное_имя("xx:1", "", заголовок="")
    assert имя == "xx-1.pdf"


def test_безопасное_имя_расширение_txt_для_se():
    имя = _безопасное_имя("se:chemistry:42", "", расширение=".txt", заголовок="Why does sodium react")
    assert имя.endswith(".txt")
    assert "why-does-sodium-react" in имя
