import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from обзор_содержание import собрать_разделы

ПАПКА = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_pdfs")
ИМЯ = "sovremennye-podkhody-ML-v-khimii-obzor-2024.pdf"


def зарегистрировать_шрифты():
    pdfmetrics.registerFont(TTFont("Times", r"C:\Windows\Fonts\times.ttf"))
    pdfmetrics.registerFont(TTFont("Times-Bold", r"C:\Windows\Fonts\timesbd.ttf"))
    pdfmetrics.registerFont(TTFont("Times-Italic", r"C:\Windows\Fonts\timesi.ttf"))


зарегистрировать_шрифты()


def стили():
    базовые = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=базовые["Title"],
            fontName="Times-Bold", fontSize=14, leading=18,
            alignment=TA_CENTER, spaceAfter=12),
        "authors": ParagraphStyle("authors", parent=базовые["Normal"],
            fontName="Times", fontSize=11, leading=14,
            alignment=TA_CENTER, spaceAfter=6),
        "affil": ParagraphStyle("affil", parent=базовые["Normal"],
            fontName="Times-Italic", fontSize=9, leading=12,
            alignment=TA_CENTER, spaceAfter=14),
        "abstract_h": ParagraphStyle("abstract_h", parent=базовые["Normal"],
            fontName="Times-Bold", fontSize=10, leading=13, spaceAfter=4),
        "abstract": ParagraphStyle("abstract", parent=базовые["Normal"],
            fontName="Times", fontSize=10, leading=13,
            alignment=TA_JUSTIFY, spaceAfter=10),
        "section": ParagraphStyle("section", parent=базовые["Normal"],
            fontName="Times-Bold", fontSize=12, leading=16,
            alignment=TA_LEFT, spaceBefore=14, spaceAfter=8),
        "body": ParagraphStyle("body", parent=базовые["Normal"],
            fontName="Times", fontSize=11, leading=15,
            alignment=TA_JUSTIFY, spaceAfter=6, firstLineIndent=18),
        "formula": ParagraphStyle("formula", parent=базовые["Normal"],
            fontName="Times-Italic", fontSize=11, leading=15,
            alignment=TA_CENTER, spaceBefore=4, spaceAfter=8),
        "ref": ParagraphStyle("ref", parent=базовые["Normal"],
            fontName="Times", fontSize=9, leading=12,
            alignment=TA_JUSTIFY, spaceAfter=3,
            leftIndent=18, firstLineIndent=-18),
    }


def создать_pdf():
    os.makedirs(ПАПКА, exist_ok=True)
    путь = os.path.join(ПАПКА, ИМЯ)

    документ = SimpleDocTemplate(
        путь, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="Современные подходы ML в химии",
        author="Гаврилов А. В. и др."
    )

    С = стили()
    элементы = собрать_разделы(С)
    документ.build(элементы)

    размер = os.path.getsize(путь)
    print(f"PDF создан: {путь}")
    print(f"Размер: {размер // 1024} KB")


if __name__ == "__main__":
    создать_pdf()
