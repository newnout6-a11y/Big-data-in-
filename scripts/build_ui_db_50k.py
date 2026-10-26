"""Собрать сбалансированную UI-базу Qdrant на 50 000 фрагментов."""
from __future__ import annotations

import sys

from build_balanced_ui_databases import main


if __name__ == "__main__":
    sys.exit(main(["--sizes", "50000", *sys.argv[1:]]))
