"""DEPRECATED: legacy эмбеддинг-инкремент.

Этот скрипт удалён в пользу `embed_resume_v2.py`, который работает с
`knowledge_hybrid` (dense + sparse) и идемпотентен по `text_hash`.

Если ты пришёл по ссылке из старой документации — запускай вместо этого:

    python embed_resume_v2.py
"""
from __future__ import annotations

import sys


def main() -> int:
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
