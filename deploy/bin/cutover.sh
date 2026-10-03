#!/bin/bash
# Production cutover: serve port 80 from this environment instead of the legacy
# web container (stocktool-app-1). The database (stocktool-mysql-1) and memocrip
# are not touched. Run only after the MacBook jobs are stopped (RUNBOOK.md step 1).
# On a failed smoke test it rolls back automatically.
set -euo pipefail
cd "$(dirname "$0")/.."
ts=$(date +%Y%m%d-%H%M%S)
step() { echo "=== $(date '+%T') $*"; }

step "preflight"
[ "$(docker inspect -f '{{.State.Health.Status}}' stocktool-integrated-backend-1)" = healthy ] || { echo "backend not healthy"; exit 1; }
[ "$(docker inspect -f '{{.State.Health.Status}}' stocktool-mysql-1)" = healthy ] || { echo "stocktool-mysql-1 not healthy"; exit 1; }
grep -qx 'BACKEND_MYSQL_HOST=stocktool-mysql-1' .env || { echo "backend is not pointed at stocktool-mysql-1"; exit 1; }
[ "$(docker exec stocktool-integrated-backend-1 printenv MYSQL_HOST)" = stocktool-mysql-1 ] || { echo "running backend uses another DB"; exit 1; }
bin/smoke.sh 8080 >/dev/null || { echo "smoke test on :8080 failed"; exit 1; }

step "backup .env and crontab -> backups/*.$ts"
mkdir -p -m 700 backups
cp -p .env "backups/env.$ts"
crontab -l > "backups/crontab.$ts" 2>/dev/null || : > "backups/crontab.$ts"

step "stop legacy web (stocktool-app-1)"
docker stop stocktool-app-1

step "start new web on :80"
sed -i 's/^WEB_HOST_PORT=.*/WEB_HOST_PORT=80/' .env
docker compose up -d web
for i in $(seq 1 60); do curl -s -o /dev/null -m 2 http://127.0.0.1/health && break; sleep 1; done

step "smoke test :80"
if ! bin/smoke.sh 80; then
  step "SMOKE TEST FAILED -> rolling back"
  bin/rollback.sh "$ts"
  exit 1
fi

step "crontab: drop dead legacy entry, add scheduled jobs"
{ grep -vF '/home/akimoto/StockTool/cron-bbs-scrape.sh' "backups/crontab.$ts" | grep -vF 'bin/run-job.sh' || true
  cat crontab.txt; } | crontab -
crontab -l | grep -E 'run-job|cron-bbs' || true

step "stop verification MySQL (volume kept)"
docker compose --profile testdb stop mysql

step "done"
docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'
