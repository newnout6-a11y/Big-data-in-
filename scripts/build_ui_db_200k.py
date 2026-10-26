"""Собрать сбалансированную UI-базу Qdrant на 200 000 фрагментов."""
from __future__ import annotations

import sys

from build_balanced_ui_databases import main


if __name__ == "__main__":
    sys.exit(main(["--sizes", "200000", *sys.argv[1:]]))
