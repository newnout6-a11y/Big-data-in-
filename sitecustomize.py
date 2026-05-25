"""Глобальные настройки окружения, применяются при старте Python.

Делает две вещи:
1. Гасит TensorFlow-ветку в transformers (мы используем только PyTorch).
2. Добавляет подпапки `core/`, `pipeline/`, `ui/`, `scripts/` в sys.path,
   чтобы старые импорты вида `from cases import ...` или `import дизайн`
   продолжали работать после реструктуризации файлов по папкам.
"""
import os
import sys
from pathlib import Path


os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")


_БАЗА = Path(__file__).resolve().parent
for _подпапка in ("core", "pipeline", "ui", "scripts"):
    _путь = str(_БАЗА / _подпапка)
    if _путь not in sys.path:
        sys.path.insert(0, _путь)
