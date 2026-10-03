#!/bin/bash
# Undo bin/cutover.sh on the Mac mini: legacy web back on :80, new web on :8080,
# crontab restored. Usage: bin/rollback.sh [backup-timestamp]   (default: latest)
# MacBook jobs must be re-enabled separately (RUNBOOK.md).
set -uo pipefail
cd "$(dirname "$0")/.."
ts=${1:-$(ls -1 backups/crontab.* 2>/dev/null | sed 's/.*crontab\.//' | sort | tail -1)}
step() { echo "=== $(date '+%T') $*"; }

step "move new web back to :8080"
sed -i 's/^WEB_HOST_PORT=.*/WEB_HOST_PORT=8080/' .env
docker compose up -d web

step "start legacy web (stocktool-app-1)"
docker start stocktool-app-1

if [ -n "$ts" ] && [ -f "backups/crontab.$ts" ]; then
  step "restore crontab from backups/crontab.$ts"
  crontab "backups/crontab.$ts"
else
  step "no crontab backup found; removing run-job entries only"
  crontab -l 2>/dev/null | grep -vF 'stocktool-integrated/bin/run-job.sh' | crontab -
fi

sleep 3
step "check :80 (legacy) and :8080 (new)"
curl -s -o /dev/null -w ':80   -> %{http_code}\n' http://127.0.0.1/bbs_ranking.php
curl -s -o /dev/null -w ':8080 -> %{http_code}\n' http://127.0.0.1:8080/bbs_ranking.php
