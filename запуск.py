"""Шорткат: `python запуск.py` → `scripts/запуск.py`.

После реструктуризации настоящий запускатор живёт в `scripts/`. Этот файл
оставлен в корне, чтобы привычная команда `python запуск.py` продолжала
работать.
"""
import runpy
from pathlib import Path

_цель = Path(__file__).resolve().parent / "scripts" / "запуск.py"
runpy.run_path(str(_цель), run_name="__main__")
