#!/bin/bash
# Run a scheduled StockTool job inside the backend container.
# Usage: bin/run-job.sh bbs|margin      (meant for the host crontab, see crontab.txt)
set -u
cd "$(dirname "$0")/.." || exit 1

JOB=${1:-}
case "$JOB" in
  bbs)    CMD=(python3 bbs_scraper.py) ;;
  margin) CMD=(python3 margin_scraper.py) ;;
  *)      echo "usage: $0 bbs|margin" >&2; exit 2 ;;
esac

mkdir -p logs
LOG="logs/$JOB-$(date +%Y%m).log"

# One run per job at a time (a slow scrape must not overlap the next one)
exec 9>"logs/$JOB.lock"
if ! flock -n 9; then
  echo "=== $(date '+%F %T') $JOB skipped: previous run still in progress" >> "$LOG"
  exit 0
fi

{
  echo "=== $(date '+%F %T') $JOB start"
  docker compose exec -T backend "${CMD[@]}"
  rc=$?
  echo "=== $(date '+%F %T') $JOB end exit=$rc"
} >> "$LOG" 2>&1
exit $rc
