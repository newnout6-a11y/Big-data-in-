#!/usr/bin/env bash
# Бесконечный цикл harvester'а: работа 100-140 мин, сон 20-40 мин (рандом).
#
# Env (опционально):
#   HARVESTER_BUDGET=2000
#   HARVESTER_SOURCES=arxiv,openalex,europepmc,cyberleninka,stackexchange
#   HARVEST_WORK_MIN_LOW=100 HARVEST_WORK_MIN_HIGH=140
#   HARVEST_SLEEP_MIN_LOW=20 HARVEST_SLEEP_MIN_HIGH=40
#
# S3 upload (опционально, Sber Cloud OBS):
#   S3_ENDPOINT_URL=https://obs.ru-moscow-1.hc.sbercloud.ru
#   S3_BUCKET=your-bucket S3_ACCESS_KEY=... S3_SECRET_KEY=...
#
# Запуск: ./run_harvester_loop.sh
# Автостарт на boot (systemd/launchd) — см. документация/ЛОКАЛЬНЫЙ_ЗАПУСК.md

set -euo pipefail

cd "$(dirname "$0")/.."

: "${HARVESTER_BUDGET:=2000}"
: "${HARVESTER_SOURCES:=arxiv,chemrxiv,openalex,europepmc,cyberleninka,stackexchange,semanticscholar}"
: "${HARVESTER_YEAR_MIN:=2020}"
: "${HARVESTER_EMAIL:=you@example.com}"

echo "=== Harvester LOOP ==="
echo "  budget/iter: $HARVESTER_BUDGET"
echo "  sources:     $HARVESTER_SOURCES"
echo "  year_min:    $HARVESTER_YEAR_MIN"
echo "  email:       $HARVESTER_EMAIL"
if [ -n "${S3_BUCKET:-}" ]; then
  echo "  S3:          ${S3_ENDPOINT_URL:-?} / bucket=$S3_BUCKET"
else
  echo "  S3:          off"
fi
echo

exec python -m harvester.loop
