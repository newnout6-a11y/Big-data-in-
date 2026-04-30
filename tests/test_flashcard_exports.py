from __future__ import annotations

import zipfile

import pytest

from study_tools import save_flashcard_exports


def test_flashcard_exports_are_saved_as_local_user_files(tmp_path) -> None:
    pytest.importorskip("genanki")
    cards = [{
        "front": "Что показывает выход реакции?",
        "back": "Долю реально полученного продукта от теоретического.",
        "source": "[1]",
    }]

    exports = save_flashcard_exports(
        cards,
        "Навигатор - выход реакции",
        tmp_path / "local" / "nb_test",
        prefix="Физхимия 3 курс выход реакции",
        package_id="local:nb_test:выход реакции",
    )

    assert exports["tsv_path"].endswith(".tsv")
    assert exports["apkg_path"].endswith(".apkg")
    assert "navigator_flashcards" not in exports["tsv_path"]
    assert "Что показывает выход реакции?".encode("utf-8") in exports["tsv_bytes"]

    with zipfile.ZipFile(exports["apkg_path"]) as package:
        assert "collection.anki2" in package.namelist()
        assert "media" in package.namelist()
