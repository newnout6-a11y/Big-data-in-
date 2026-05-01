"""Визуальная обработка страниц PDF для тетрадей.

Три уровня (tier'а) обработки каждой страницы:

  Tier 0 — PyMuPDF text extraction (бесплатно, мгновенно).
  Tier 1 — RapidOCR по рендеру страницы (бесплатно, ~1–3 сек/стр).
  Tier 2 — Groq Vision caption (платно, ~$0.0004/стр, опция).

Каждая обработанная страница кэшируется глобально по page_hash (SHA-256
от рендера), поэтому одинаковые страницы не обрабатываются дважды даже
из разных тетрадей / PDF.

Кэш: visual_index/pages/<page_hash>.json
Бюджет: visual_index/budget.json
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

_БАЗА = Path(__file__).resolve().parent
ПАПКА_КЭША = _БАЗА / "visual_index" / "pages"
ФАЙЛ_БЮДЖЕТА = _БАЗА / "visual_index" / "budget.json"

RENDER_DPI = 200
MIN_WORDS_GOOD = 30
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
VISION_PROMPT = (
    "Опиши содержимое этой страницы документа на русском языке. "
    "Если есть графики, таблицы, схемы или формулы — опиши их суть. "
    "Будь кратким (3–5 предложений)."
)
VISION_PROMPT_VERSION = 1
MAX_GROQ_PAGES_DEFAULT = int(os.getenv("NOTEBOOK_VISION_MAX_PAGES", "30"))

_rapidocr_lock = threading.Lock()
_rapidocr_cache: dict[str, Any] = {}


# ---------------------------------------------------------------------------
#  Dataclass для результата обработки страницы
# ---------------------------------------------------------------------------

@dataclass
class СтраницаВизуал:
    page_number: int
    text: str = ""
    ocr_text: str = ""
    visual_caption: str = ""
    tier_used: int = 0
    page_hash: str = ""
    image_path: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
#  Утилиты
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    if not text:
        return 0
    return sum(1 for w in text.split() if len(w) >= 2)


def _page_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _render_page(page: Any, dpi: int = RENDER_DPI) -> bytes:
    """Рендерит страницу fitz.Page в PNG bytes."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


# ---------------------------------------------------------------------------
#  Кэш
# ---------------------------------------------------------------------------

def _read_cache(ph: str) -> dict | None:
    path = ПАПКА_КЭША / f"{ph}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(ph: str, data: dict) -> None:
    ПАПКА_КЭША.mkdir(parents=True, exist_ok=True)
    path = ПАПКА_КЭША / f"{ph}.json"
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ---------------------------------------------------------------------------
#  Бюджет Groq Vision
# ---------------------------------------------------------------------------

def _read_budget() -> dict:
    if not ФАЙЛ_БЮДЖЕТА.exists():
        return {"total_pages": 0, "total_tokens_input": 0, "total_tokens_output": 0,
                "calls": []}
    try:
        with ФАЙЛ_БЮДЖЕТА.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"total_pages": 0, "total_tokens_input": 0, "total_tokens_output": 0,
                "calls": []}


def _update_budget(tokens_in: int = 0, tokens_out: int = 0) -> None:
    ФАЙЛ_БЮДЖЕТА.parent.mkdir(parents=True, exist_ok=True)
    budget = _read_budget()
    budget["total_pages"] = budget.get("total_pages", 0) + 1
    budget["total_tokens_input"] = budget.get("total_tokens_input", 0) + tokens_in
    budget["total_tokens_output"] = budget.get("total_tokens_output", 0) + tokens_out
    budget.setdefault("calls", []).append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    })
    tmp = ФАЙЛ_БЮДЖЕТА.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(budget, f, ensure_ascii=False, indent=2)
    tmp.replace(ФАЙЛ_БЮДЖЕТА)


def budget_summary() -> dict:
    """Краткая сводка по бюджету Groq Vision (для UI)."""
    b = _read_budget()
    cost_input = b.get("total_tokens_input", 0) * 0.11 / 1_000_000
    cost_output = b.get("total_tokens_output", 0) * 0.34 / 1_000_000
    return {
        "total_pages": b.get("total_pages", 0),
        "estimated_cost_usd": round(cost_input + cost_output, 4),
    }


# ---------------------------------------------------------------------------
#  Tier 1 — RapidOCR
# ---------------------------------------------------------------------------

def _get_rapidocr():
    if "engine" in _rapidocr_cache:
        return _rapidocr_cache["engine"]
    with _rapidocr_lock:
        if "engine" in _rapidocr_cache:
            return _rapidocr_cache["engine"]
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapidocr_cache["engine"] = RapidOCR()
        except ImportError:
            _rapidocr_cache["engine"] = None
        return _rapidocr_cache["engine"]


def _ocr_page(image_bytes: bytes) -> tuple[str, float]:
    """Выполняет OCR по PNG-байтам. Возвращает (text, confidence)."""
    engine = _get_rapidocr()
    if engine is None:
        return "", 0.0
    import numpy as np
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)
    result, _ = engine(arr)
    if not result:
        return "", 0.0
    lines = []
    total_conf = 0.0
    for box_text in result:
        text_val = box_text[1] if len(box_text) > 1 else ""
        conf_val = float(box_text[2]) if len(box_text) > 2 else 0.0
        if text_val:
            lines.append(str(text_val))
            total_conf += conf_val
    full_text = "\n".join(lines)
    avg_conf = (total_conf / len(result)) if result else 0.0
    return full_text, avg_conf


# ---------------------------------------------------------------------------
#  Tier 2 — Groq Vision
# ---------------------------------------------------------------------------

def _call_groq_vision(image_bytes: bytes, api_key: str,
                      model: str = VISION_MODEL,
                      prompt: str = VISION_PROMPT) -> tuple[str, int, int]:
    """Вызывает Groq Vision API. Возвращает (caption, tokens_in, tokens_out)."""
    from groq import Groq

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = "image/png"

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime};base64,{b64}",
                }},
            ],
        }],
        max_tokens=512,
        temperature=0.3,
    )
    caption = (resp.choices[0].message.content or "").strip()
    usage = resp.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0
    return caption, tokens_in, tokens_out


# ---------------------------------------------------------------------------
#  Главная функция: обработка одной страницы
# ---------------------------------------------------------------------------

def обработать_страницу(
    page: Any,
    page_number: int,
    native_text: str,
    *,
    use_groq_vision: bool = False,
    groq_api_key: str = "",
    groq_pages_left: int = 0,
    save_image_dir: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> СтраницаВизуал:
    """Обрабатывает одну страницу PDF через tier'ы.

    page: fitz.Page объект.
    page_number: номер страницы (1-based).
    native_text: текст, уже извлечённый PyMuPDF (Tier 0).
    use_groq_vision: включён ли Tier 2.
    groq_api_key: ключ Groq (нужен если use_groq_vision=True).
    groq_pages_left: сколько Groq-страниц осталось в бюджете для этого upload.
    save_image_dir: если задано, сохраняет PNG рендер страницы в эту папку.
    on_progress: опциональный callback(status_text) для прогресса в UI.
    """
    result = СтраницаВизуал(page_number=page_number, text=native_text.strip())

    if fitz is None:
        return result

    # Рендерим страницу
    try:
        png_bytes = _render_page(page)
    except Exception:
        return result

    ph = _page_hash(png_bytes)
    result.page_hash = ph

    # Сохраняем картинку если нужно
    if save_image_dir:
        img_dir = Path(save_image_dir)
        img_dir.mkdir(parents=True, exist_ok=True)
        img_path = img_dir / f"page_{page_number}.png"
        img_path.write_bytes(png_bytes)
        result.image_path = str(img_path)

    # Проверяем кэш
    cached = _read_cache(ph)
    if cached:
        result.ocr_text = cached.get("ocr_text", "")
        result.visual_caption = cached.get("visual_caption", "")
        result.tier_used = cached.get("tier_used", 0)
        result.confidence = cached.get("confidence", 0.0)
        if on_progress:
            on_progress(f"стр. {page_number}: кэш (tier {result.tier_used})")
        return result

    tier_used = 0
    ocr_text = ""
    visual_caption = ""
    confidence = 0.0

    # Tier 0: уже есть native_text
    combined_words = _count_words(native_text)

    # Tier 1: RapidOCR — если текста мало
    if combined_words < MIN_WORDS_GOOD:
        if on_progress:
            on_progress(f"стр. {page_number}: OCR (RapidOCR)...")
        try:
            ocr_text, confidence = _ocr_page(png_bytes)
            if ocr_text:
                tier_used = 1
                combined_words = _count_words(native_text) + _count_words(ocr_text)
        except Exception:
            pass

    # Tier 2: Groq Vision — если всё ещё мало текста и включено
    if (combined_words < MIN_WORDS_GOOD
            and use_groq_vision
            and groq_api_key
            and groq_pages_left > 0):
        if on_progress:
            on_progress(f"стр. {page_number}: Groq Vision...")
        try:
            visual_caption, tok_in, tok_out = _call_groq_vision(
                png_bytes, groq_api_key)
            tier_used = 2
            _update_budget(tok_in, tok_out)
        except Exception:
            pass

    result.ocr_text = ocr_text
    result.visual_caption = visual_caption
    result.tier_used = tier_used
    result.confidence = confidence

    # Записываем в кэш
    _write_cache(ph, {
        "page_hash": ph,
        "ocr_text": ocr_text,
        "visual_caption": visual_caption,
        "tier_used": tier_used,
        "confidence": confidence,
        "vision_model": VISION_MODEL if tier_used == 2 else None,
        "vision_prompt_v": VISION_PROMPT_VERSION if tier_used == 2 else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return result


# ---------------------------------------------------------------------------
#  Обработка целого PDF
# ---------------------------------------------------------------------------

def обработать_pdf(
    path: str | Path,
    *,
    use_groq_vision: bool = False,
    groq_api_key: str = "",
    max_groq_pages: int = MAX_GROQ_PAGES_DEFAULT,
    save_images: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Извлекает страницы из PDF с визуальной обработкой.

    Возвращает список dict'ов, каждый с ключами:
      page, text, ocr_text, visual_caption, tier_used, page_hash, image_path
    """
    if fitz is None:
        return []

    path = Path(path)
    pages_out: list[dict[str, Any]] = []

    try:
        doc = fitz.open(str(path))
    except Exception:
        return []

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    image_dir = str(_БАЗА / "visual_index" / "images" / file_hash) if save_images else None
    groq_pages_used = 0

    try:
        for idx, page in enumerate(doc, start=1):
            native_text = ""
            try:
                native_text = page.get_text("text") or ""
            except Exception:
                pass

            result = обработать_страницу(
                page, idx, native_text,
                use_groq_vision=use_groq_vision,
                groq_api_key=groq_api_key,
                groq_pages_left=max_groq_pages - groq_pages_used,
                save_image_dir=image_dir,
                on_progress=on_progress,
            )
            if result.tier_used == 2:
                groq_pages_used += 1

            # Собираем enriched text для чанка
            parts = []
            if result.text and len(result.text.strip()) > 20:
                parts.append(result.text.strip())
            if result.ocr_text and len(result.ocr_text.strip()) > 20:
                parts.append(f"[OCR]\n{result.ocr_text.strip()}")
            if result.visual_caption and len(result.visual_caption.strip()) > 10:
                parts.append(f"[Описание изображения]\n{result.visual_caption.strip()}")

            combined_text = "\n\n".join(parts)
            if len(combined_text.strip()) < 40:
                continue

            pages_out.append({
                "page": idx,
                "text": combined_text,
                "ocr_text": result.ocr_text,
                "visual_caption": result.visual_caption,
                "tier_used": result.tier_used,
                "page_hash": result.page_hash,
                "image_path": result.image_path,
                "has_ocr": bool(result.ocr_text),
                "has_visual_caption": bool(result.visual_caption),
            })
    finally:
        doc.close()

    return pages_out


def groq_vision_available() -> bool:
    """Проверяет, есть ли ключ Groq для Vision (для UI)."""
    for name in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"):
        key = os.getenv(name, "").strip()
        if key:
            return True
    return False


def _first_groq_key() -> str:
    """Первый доступный ключ Groq."""
    for name in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"):
        key = os.getenv(name, "").strip()
        if key:
            return key
    return ""
