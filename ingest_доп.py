"""DEPRECATED: legacy «доп. ингест» (CSV/TXT/etc).

Этот скрипт удалён. Сейчас весь ингест — через `ingest_v2.py` (для корпуса)
и через UI «Мои документы» (для пользовательских тетрадей в `notebooks.py`).
Если нужно догрузить tabular/text — клади файлы в папку и запускай:

    python ingest_v2.py
    python embed_resume_v2.py
"""
from __future__ import annotations

import sys


def main() -> int:
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
