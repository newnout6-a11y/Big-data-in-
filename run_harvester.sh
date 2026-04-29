#!/usr/bin/env bash
# Локальный запуск harvester'а на Linux / macOS.
# Запуск: ./run_harvester.sh
#
# По умолчанию: бюджет 200, все источники, год >= 2020.
# Переопределить через env vars:
#   HARVESTER_BUDGET=500 ./run_harvester.sh
#   HARVESTER_SOURCES=arxiv,europepmc ./run_harvester.sh
#
# Для cron-режима добавь в crontab:
#   0 */6 * * * cd /path/to/Big-data-in- && ./run_harvester.sh >> ~/.harvester.log 2>&1

set -euo pipefail

cd "$(dirname "$0")"

: "${HARVESTER_BUDGET:=200}"
: "${HARVESTER_SOURCES:=arxiv,chemrxiv,openalex,europepmc,cyberleninka,stackexchange}"
: "${HARVESTER_YEAR_MIN:=2020}"
: "${HARVESTER_EMAIL:=you@example.com}"

echo "=== Harvester ==="
echo "  budget:  $HARVESTER_BUDGET"
echo "  sources: $HARVESTER_SOURCES"
echo "  year>=:  $HARVESTER_YEAR_MIN"
echo "  email:   $HARVESTER_EMAIL"
echo

python -m harvester.harvest_full \
  --budget "$HARVESTER_BUDGET" \
  --sources "$HARVESTER_SOURCES" \
  --year-min "$HARVESTER_YEAR_MIN" \
  --email "$HARVESTER_EMAIL" \
  --time-limit-min 60

echo
echo "Готово. Чанки в qdrant_db/, PDF в all_pdfs/."
