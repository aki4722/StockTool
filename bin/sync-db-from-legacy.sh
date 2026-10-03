#!/bin/bash
# Copy the StockTool tables from the legacy MySQL (stocktool-mysql-1, ~/StockTool)
# into this environment's MySQL. Replaces those tables here (mysqldump emits
# DROP TABLE IF EXISTS); never writes to the legacy database.
# memocrip_* tables are left in the legacy DB (memocrip still connects there).
set -euo pipefail
cd "$(dirname "$0")/.."

TABLES="bbs_rankings bbs_posts bbs_sentiment margin_tracking margin_positions"
LEGACY_ROOT=$(grep '^MYSQL_ROOT_PASSWORD=' ~/StockTool/.env | cut -d= -f2-)
NEW_ROOT=$(grep '^MYSQL_ROOT_PASSWORD=' .env | cut -d= -f2-)

count() {  # $1=container $2=password
  docker exec -e MYSQL_PWD="$2" "$1" mysql -uroot -N stocktool_bbs -e \
    "SELECT CONCAT_WS(' ', 'rankings', COUNT(*), MAX(date)) FROM bbs_rankings
     UNION ALL SELECT CONCAT_WS(' ', 'posts', COUNT(*), MAX(created_at)) FROM bbs_posts
     UNION ALL SELECT CONCAT_WS(' ', 'sentiment', COUNT(*), MAX(date)) FROM bbs_sentiment
     UNION ALL SELECT CONCAT_WS(' ', 'margin_positions', COUNT(*), MAX(date)) FROM margin_positions
     UNION ALL SELECT CONCAT_WS(' ', 'margin_tracking', COUNT(*)) FROM margin_tracking"
}

echo "=== $(date '+%F %T') copying: $TABLES"
docker exec -e MYSQL_PWD="$LEGACY_ROOT" stocktool-mysql-1 \
  mysqldump -uroot --single-transaction --quick --set-gtid-purged=OFF --no-tablespaces stocktool_bbs $TABLES \
  | docker compose exec -T -e MYSQL_PWD="$NEW_ROOT" mysql mysql -uroot stocktool_bbs

legacy=$(count stocktool-mysql-1 "$LEGACY_ROOT")
new=$(count stocktool-integrated-mysql-1 "$NEW_ROOT")
echo "--- legacy:"; echo "$legacy"
echo "--- new:";    echo "$new"
if [ "$legacy" = "$new" ]; then echo "=== OK: identical"; else echo "=== MISMATCH" >&2; exit 1; fi
