"""Pytest fixtures и настройка sys.path.

Добавляет корень репо и подпапки `core/`, `pipeline/`, `ui/`, `scripts/`
в sys.path, чтобы тесты могли импортить модули по плоским именам
(`from cases import ...`, `import notebooks` и т. д.) как раньше.
"""
import os
import sys
from pathlib import Path


os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")


_БАЗА = Path(__file__).resolve().parent
for _подпапка in ("", "core", "pipeline", "ui", "scripts"):
    _путь = str(_БАЗА / _подпапка) if _подпапка else str(_БАЗА)
    if _путь not in sys.path:
        sys.path.insert(0, _путь)
