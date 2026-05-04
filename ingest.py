"""DEPRECATED: legacy ingest скрипт.

Этот скрипт удалён в пользу `ingest_v2.py`, который пишет в `chunks_v2.jsonl`
с метаданными для гибридного поиска (`knowledge_hybrid`).

Если ты пришёл по ссылке из старой документации — запускай вместо этого:

    python ingest_v2.py
    python embed_resume_v2.py

Если тебе действительно нужна старая логика (плоский `chunks.jsonl` без
metadata, коллекция `химия`) — посмотри git-историю до коммита, удалившего
этот файл, и восстанови оттуда.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
