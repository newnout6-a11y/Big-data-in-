"""Общий модуль извлечения картинок из PDF-страниц.

Используется двумя независимыми пайплайнами:
  - pipeline/ingest_v2.py  — массовый ингест корпуса (harvest)
  - core/notebooks.py      — загрузка пользовательских документов

Обеспечивает:
  • фильтр декоративных картинок (полоски, иконки шаблона, логотипы <80px)
  • детекцию повторяющихся фоновых изображений шаблонов презентаций
  • автопривязку подписей Fig./Рис./Scheme/Table по геометрии страницы (bbox)
  • fallback-caption для слайдов лекций (заголовок/тело слайда)
  • OCR рисунков-схем через easyocr (опционально, cv2.imdecode для кириллических путей)
  • Groq Vision caption (опционально)
"""
from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

try:
    import easyocr as _easyocr_mod  # type: ignore
except ImportError:  # pragma: no cover
    _easyocr_mod = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# easyocr — ленивая инициализация (thread-safe)
# ─────────────────────────────────────────────────────────────────────────────

_easyocr_lock = threading.Lock()
_easyocr_reader: Any = None
_easyocr_init_failed = False


def _получить_easyocr_reader() -> Any:
    """Thread-safe ленивая инициализация easyocr.Reader (RU+EN, CPU).
    Первый вызов скачает модели (~70 MB). При неудаче возвращает None.
    """
    global _easyocr_reader, _easyocr_init_failed
    if _easyocr_reader is not None:
        return _easyocr_reader
    with _easyocr_lock:
        if _easyocr_reader is not None:
            return _easyocr_reader
        if _easyocr_init_failed or _easyocr_mod is None:
            return None
        try:
            _easyocr_reader = _easyocr_mod.Reader(["ru", "en"], gpu=False, verbose=False)
            return _easyocr_reader
        except Exception:
            _easyocr_init_failed = True
            return None


def ocr_картинки(путь_файла: Path) -> str:
    """Распознаёт текст на картинке через easyocr (до 400 символов).
    Пустая строка если OCR недоступен или ничего не распознано.

    Использует cv2.imdecode вместо cv2.imread — workaround для кириллических
    путей на Windows, где imread тихо возвращает None.
    """
    reader = _получить_easyocr_reader()
    if reader is None:
        return ""
    try:
        import numpy as np
        import cv2
        данные = np.fromfile(str(путь_файла), dtype=np.uint8)
        if данные.size == 0:
            return ""
        изображение = cv2.imdecode(данные, cv2.IMREAD_COLOR)
        if изображение is None:
            return ""
        результаты = reader.readtext(изображение, detail=0, paragraph=True)
    except Exception:
        return ""
    куски = [s.strip() for s in (результаты or []) if s and isinstance(s, str) and s.strip()]
    if not куски:
        return ""
    текст = re.sub(r"\s+", " ", " ".join(куски)).strip()
    if len(текст) > 400:
        текст = текст[:397].rstrip() + "…"
    return текст


# ─────────────────────────────────────────────────────────────────────────────
# Подписи Fig./Рис./Scheme/Table — regex-парсинг + bbox-привязка
# ─────────────────────────────────────────────────────────────────────────────

CAPTION_REGEX = re.compile(
    r"(?im)(?:^|\n|\.)\s*"
    r"(?P<tag>Fig(?:ure|\.)?|Рис(?:унок|\.)?|Scheme|Схема|Схемы|Table|Таблица)"
    r"\s*(?P<num>\d+)[\.:\)\s-]+"
    r"(?P<body>[^\n]{10,400})"
)


def извлечь_подписи_со_страницы(текст: str) -> list[dict[str, str]]:
    """Возвращает список подписей `{tag, num, prefix, body, full}` в порядке
    появления в тексте страницы."""
    if not текст:
        return []
    результат: list[dict[str, str]] = []
    for m in CAPTION_REGEX.finditer(текст):
        tag = m.group("tag").strip().rstrip(".")
        num = m.group("num")
        body = m.group("body").strip()
        if len(body) > 220:
            точка = body.find(". ")
            if 40 < точка < 220:
                body = body[:точка + 1]
        full = f"{tag} {num}. {body}"
        prefix = f"{tag} {num}"
        результат.append({"tag": tag, "num": num, "prefix": prefix, "body": body, "full": full})
    return результат


def _bbox_подписи(
    страница: Any, подпись: dict[str, str]
) -> tuple[float, float, float, float] | None:
    """Bbox первого вхождения подписи на странице через `page.search_for`."""
    кандидаты = [
        f"{подпись['tag']}. {подпись['num']}",
        f"{подпись['tag']} {подпись['num']}.",
        f"{подпись['tag']} {подпись['num']}",
    ]
    for запрос in кандидаты:
        try:
            попадания = страница.search_for(запрос)
        except Exception:
            попадания = []
        if попадания:
            r = попадания[0]
            return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
    return None


def _bbox_картинки(
    страница: Any, xref: int
) -> tuple[float, float, float, float] | None:
    """Bbox первого размещения картинки `xref` на странице."""
    try:
        прямоугольники = страница.get_image_rects(xref)
    except Exception:
        прямоугольники = []
    if прямоугольники:
        r = прямоугольники[0]
        return (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
    return None


def привязать_подписи(
    страница: Any,
    xrefs_по_порядку: list[int],
    подписи: list[dict[str, str]],
) -> dict[int, str]:
    """Возвращает `{xref → caption}` по геометрии страницы.

    Алгоритм: для каждой подписи находим Y-координату через `search_for`,
    затем привязываем к картинке, чей нижний край ближайший СВЕРХУ к подписи.
    Fallback к порядковой привязке если bbox не найден.
    """
    результат: dict[int, str] = {}
    if not подписи or not xrefs_по_порядку:
        return результат

    bbox_картинок: list[tuple[int, tuple[float, float, float, float]]] = []
    for xref in xrefs_по_порядку:
        bbox = _bbox_картинки(страница, xref)
        if bbox is not None:
            bbox_картинок.append((xref, bbox))

    # Нет bbox ни у одной картинки — порядковая привязка
    if not bbox_картинок:
        for i, xref in enumerate(xrefs_по_порядку):
            if i < len(подписи):
                результат[xref] = подписи[i]["full"]
        return результат

    занятые: set[int] = set()
    непривязанные: list[dict[str, str]] = []
    for подпись in подписи:
        bbox_п = _bbox_подписи(страница, подпись)
        if bbox_п is None:
            непривязанные.append(подпись)
            continue
        y_подписи = bbox_п[1]
        лучший_xref: int | None = None
        лучшее_расстояние = float("inf")
        for xref, (_x0, _y0, _x1, y1) in bbox_картинок:
            if xref in занятые:
                continue
            if y1 <= y_подписи + 5:  # +5 px допуск на перекрытие
                расстояние = y_подписи - y1
                if расстояние < лучшее_расстояние:
                    лучшее_расстояние = расстояние
                    лучший_xref = xref
        if лучший_xref is not None:
            результат[лучший_xref] = подпись["full"]
            занятые.add(лучший_xref)
        else:
            непривязанные.append(подпись)

    # Оставшиеся подписи → оставшиеся картинки по Y-порядку
    if непривязанные:
        свободные = [(xref, b) for xref, b in bbox_картинок if xref not in занятые]
        свободные.sort(key=lambda x: x[1][1])  # по y0
        for подпись, (xref, _) in zip(непривязанные, свободные):
            результат[xref] = подпись["full"]
            занятые.add(xref)

    return результат


# ─────────────────────────────────────────────────────────────────────────────
# Фильтры декоративных/фоновых картинок
# ─────────────────────────────────────────────────────────────────────────────

def картинка_декоративная(pix: Any) -> bool:
    """True если картинка похожа на декоративный элемент шаблона:
    размер меньше 80px по любой стороне или экстремальное соотношение сторон.
    """
    try:
        ширина = int(pix.width)
        высота = int(pix.height)
    except Exception:
        return False
    if ширина < 40 or высота < 40:
        return True
    # Узкая горизонтальная или вертикальная полоска
    стороны = sorted((ширина, высота))
    if стороны[0] < 120 and стороны[1] / max(стороны[0], 1) > 5:
        return True
    return False


def _хэш_pixmap(документ: Any, xref: int) -> str:
    """SHA1 от raw samples картинки. Устойчив к разным xref для визуально
    одинаковых изображений (PowerPoint/Keynote часто дублируют ресурс шаблона
    на каждой странице как отдельный xref).
    """
    try:
        pix = fitz.Pixmap(документ, xref)
        if pix.n >= 5:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return hashlib.sha1(pix.samples).hexdigest()
    except Exception:
        return ""


def найти_фоновые_xref(документ: Any, *, мин_страниц: int = 3) -> set[int]:
    """Определяет xref'ы картинок, повторяющихся на ≥ `мин_страниц` страницах.

    Логика двухуровневая:
    1) Сначала пробуем по xref — быстро для документов где экспорт дедуплицирует
       ресурсы (PDFLaTeX, Acrobat).
    2) Если xref-детекция дала мало результата (≤ кол-во страниц/5), считаем
       хэш содержимого — это ловит PowerPoint/Keynote, которые часто создают
       отдельный xref для одного и того же фона на каждом слайде.

    Возвращает множество xref'ов, относящихся к повторяющимся изображениям.
    Для коротких документов (< 6 страниц) возвращает пустое множество —
    статистики недостаточно.
    """
    if fitz is None:
        return set()
    try:
        всего_страниц = len(документ)
    except Exception:
        return set()
    if всего_страниц < 6:
        return set()

    # Шаг 1: счётчик по xref
    счётчик_xref: dict[int, int] = {}
    все_xref_по_страницам: list[set[int]] = []
    for страница in документ:
        try:
            xrefs_страницы = {з[0] for з in страница.get_images(full=True)}
        except Exception:
            xrefs_страницы = set()
        все_xref_по_страницам.append(xrefs_страницы)
        for xref in xrefs_страницы:
            счётчик_xref[xref] = счётчик_xref.get(xref, 0) + 1

    результат: set[int] = {xref for xref, n in счётчик_xref.items() if n >= мин_страниц}

    # Шаг 2: если xref-детекция нашла мало (например, ничего), пытаемся по хэшу
    # содержимого. Это спасает презентации, где фон шаблона на каждом слайде
    # запакован как отдельный ресурс.
    все_xref = {xref for страница_xref in все_xref_по_страницам for xref in страница_xref}
    # Кандидаты на хэширование — все xref, которые ещё не помечены фоновыми.
    кандидаты = все_xref - результат
    if len(кандидаты) > 0 and len(результат) < всего_страниц // 3 + 1:
        хэши: dict[str, list[int]] = {}
        # Какие xref'ы появляются на каких страницах — для подсчёта частоты по хэшу
        xref_на_страницах: dict[int, set[int]] = {}
        for i, xrefs_стр in enumerate(все_xref_по_страницам):
            for xref in xrefs_стр:
                xref_на_страницах.setdefault(xref, set()).add(i)

        for xref in кандидаты:
            h = _хэш_pixmap(документ, xref)
            if not h:
                continue
            хэши.setdefault(h, []).append(xref)

        for h, xrefs in хэши.items():
            # Считаем на скольких уникальных страницах вообще встречается
            # эта визуальная картинка (через все её xref'ы).
            страницы_с_картинкой: set[int] = set()
            for xref in xrefs:
                страницы_с_картинкой |= xref_на_страницах.get(xref, set())
            if len(страницы_с_картинкой) >= мин_страниц:
                результат.update(xrefs)

    return результат


# ─────────────────────────────────────────────────────────────────────────────
# Fallback caption для слайдов лекций
# ─────────────────────────────────────────────────────────────────────────────

_МАКС_CAPTION_СЛАЙДА = 400


def заголовок_слайда(текст: str) -> str:
    """Краткое описание слайда — конкатенация строк до 400 символов.

    Fallback для PDF-слайдов лекций, где нет явных подписей Fig./Рис.,
    но содержимое слайда само по себе описывает изображение.
    """
    if not текст:
        return ""
    строки = [s.strip() for s in текст.splitlines() if s.strip()]
    if not строки:
        return ""
    куски: list[str] = []
    собрано = 0
    for s in строки:
        if собрано and собрано + 1 + len(s) > _МАКС_CAPTION_СЛАЙДА:
            if not куски:
                куски.append(s)
            break
        куски.append(s)
        собрано += len(s) + (1 if собрано else 0)
        if собрано >= _МАКС_CAPTION_СЛАЙДА:
            break
    результат = " ".join(куски).strip()
    if len(результат) > _МАКС_CAPTION_СЛАЙДА:
        результат = результат[:_МАКС_CAPTION_СЛАЙДА - 1].rstrip() + "…"
    return результат


# ─────────────────────────────────────────────────────────────────────────────
# Groq Vision caption (опционально)
# ─────────────────────────────────────────────────────────────────────────────

VISION_CAPTION_PROMPT = (
    "Опиши кратко (1–2 предложения) что изображено на этой картинке из научной "
    "статьи. Для схем/диаграмм — тип и ключевые элементы. Для графиков — оси и "
    "смысл. Для формул — запиши саму формулу. Отвечай на русском, без вступлений."
)


def vision_caption_картинки(путь_файла: Path, api_key: str) -> str:
    """Краткое описание картинки через Groq Vision API.
    Пустая строка если api_key не задан или вызов не удался.
    """
    if not api_key:
        return ""
    try:
        данные = путь_файла.read_bytes()
    except OSError:
        return ""
    try:
        import визуальная_обработка as виз
        caption, _, _ = виз._call_groq_vision(данные, api_key, prompt=VISION_CAPTION_PROMPT)
        return (caption or "").strip()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Главная функция: извлечение картинок одной страницы
# ─────────────────────────────────────────────────────────────────────────────

def извлечь_картинки_страницы(
    документ: Any,
    страница: Any,
    номер: int,
    папка: Path,
    *,
    текст_страницы: str = "",
    vision_api_key: str = "",
    фоновые_xref: set[int] | None = None,
    use_ocr: bool = False,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Сохраняет встроенные картинки PDF-страницы и возвращает список с описаниями.

    Формат элементов: `{"path", "page", "kind", "caption"}`.

    Caption заполняется по убыванию приоритета:
      1) Fig./Рис./Scheme/Table — bbox-привязка по геометрии страницы
      2) OCR через easyocr (если use_ocr=True)
      3) Groq Vision (если передан vision_api_key)
      4) Заголовок/тело слайда как fallback (если вообще есть текст страницы)

    Параметры:
      base_dir  — корень репо для вычисления относительного пути в payload.
                  Если None — путь сохраняется абсолютный.
    """
    if fitz is None:
        return []
    результаты: list[dict[str, Any]] = []
    try:
        картинки_страницы = страница.get_images(full=True)
    except Exception:
        return []

    # 1. Сохраняем все подходящие картинки на диск
    сохранённые: list[tuple[int, Path, str]] = []  # (xref, файл, relative_path)
    видели_xref: set[int] = set()
    счётчик = 0
    for запись in картинки_страницы:
        xref = запись[0]
        if xref in видели_xref:
            continue
        видели_xref.add(xref)
        if фоновые_xref and xref in фоновые_xref:
            continue
        try:
            pix = fitz.Pixmap(документ, xref)
            if pix.n >= 5:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if картинка_декоративная(pix):
                continue
            счётчик += 1
            папка.mkdir(parents=True, exist_ok=True)
            файл = папка / f"page_{номер}_img_{счётчик}.png"
            pix.save(str(файл))
        except Exception:
            continue

        if base_dir is not None:
            try:
                относительный = файл.relative_to(base_dir).as_posix()
            except ValueError:
                относительный = str(файл)
        else:
            относительный = str(файл)
        сохранённые.append((xref, файл, относительный))

    if not сохранённые:
        return []

    # 2. Привязка подписей через геометрию страницы
    подписи_страницы = извлечь_подписи_со_страницы(текст_страницы)
    xrefs_порядок = [x for x, _, _ in сохранённые]
    привязка = привязать_подписи(страница, xrefs_порядок, подписи_страницы)

    # 3. Fallback для слайдов лекций: если нет научных подписей, но есть текст
    fallback_caption = ""
    if not подписи_страницы and (текст_страницы or "").strip():
        fallback_caption = заголовок_слайда(текст_страницы)

    # 4. Собираем итоговый список
    for xref, файл, относительный in сохранённые:
        caption = привязка.get(xref, "")
        if not caption and use_ocr:
            ocr_текст = ocr_картинки(файл)
            if ocr_текст:
                caption = ocr_текст
        if not caption and vision_api_key:
            caption = vision_caption_картинки(файл, vision_api_key)
        if not caption and fallback_caption:
            caption = f"Слайд: {fallback_caption}"
        результаты.append({
            "path": относительный,
            "page": номер,
            "kind": "extracted_image",
            "caption": caption,
        })
    return результаты
