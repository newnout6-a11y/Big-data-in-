from __future__ import annotations

import io
import zipfile

from study_tools import docx_export


def test_docx_export_converts_latex_formulas_to_word_math() -> None:
    body = r"""
Формула выхода реакции:
$$
\eta = \frac{m_{практическая}}{m_{теоретическая}} \times 100\%
$$

где $\eta$ - выход реакции.
"""

    data = docx_export("Ответ Навигатора", body)

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "<m:oMath" in document_xml
    assert "<m:f>" in document_xml
    assert "<m:sSub>" in document_xml
    assert "η" in document_xml
    assert r"\frac" not in document_xml
    assert r"\eta" not in document_xml
