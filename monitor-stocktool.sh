#!/bin/bash
set -euo pipefail

LOG_FILE="/tmp/stocktool-macbook.log"
STATE_FILE="/tmp/stocktool-monitor.state"
NOW_EPOCH=$(date +%s)

# Load env (for DISCORD_WEBHOOK_URL)
ENV_FILE="/Users/akimoto/.openclaw/workspace/StockTool/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

# Alert settings
GRACE_MINUTES=40   # allowed delay after scheduled run (08:00/20:00)
WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

send_alert() {
  local msg="$1"
  echo "[ALERT] $msg"

  # dedupe: same message once per run
  local sig
  sig=$(echo "$msg" | shasum | awk '{print $1}')
  if [[ -f "$STATE_FILE" ]] && grep -q "$sig" "$STATE_FILE"; then
    return 0
  fi
  echo "$sig" > "$STATE_FILE"

  if [[ -n "$WEBHOOK_URL" ]]; then
    payload=$(printf '{"content":"🚨 StockTool監視アラート: %s"}' "$(echo "$msg" | sed 's/"/\\"/g')")
    curl -sS -X POST "$WEBHOOK_URL" \
      -H 'Content-Type: application/json' \
      -d "$payload" >/dev/null || true
  fi
}

if [[ ! -f "$LOG_FILE" ]]; then
  send_alert "ログファイルが見つかりません: $LOG_FILE"
  exit 1
fi

# 1) OAuth refresh error detection (recent)
if tail -400 "$LOG_FILE" | grep -q "OAuth token refresh failed for openai-codex"; then
  send_alert "OpenClaw認証エラー検出: OAuth token refresh failed"
  exit 1
fi

# 2) Schedule-aware completion check (08:00 / 20:00 only)
# We alert only when a scheduled run should already have finished.
current_hour=$(date +%H)
current_min=$(date +%M)
current_hm=$((10#$current_hour * 100 + 10#$current_min))

target_date=$(date +%Y-%m-%d)
target_time=""

if (( current_hm >= 840 && current_hm < 2000 )); then
  # Morning run should be done by 08:40
  target_time="08:00:00"
elif (( current_hm >= 2040 )) || (( current_hm < 840 )); then
  # Night run should be done by 20:40.
  # Between 00:00-08:39, check previous day's 20:00 run.
  target_time="20:00:00"
  if (( current_hm < 840 )); then
    target_date=$(date -v-1d +%Y-%m-%d)
  fi
fi

if [[ -n "$target_time" ]]; then
  # Check completion marker for expected window
  if ! grep -q "=== Cron job completed at" "$LOG_FILE"; then
    send_alert "Cron完了ログが見つかりません"
    exit 1
  fi

  # Fallback check via DB for expected snapshot presence
  DB_OK=0
  if command -v python3 >/dev/null 2>&1; then
    if python3 - <<PY >/dev/null 2>&1
from dotenv import load_dotenv
from pathlib import Path
import os, pymysql
load_dotenv(Path('/Users/akimoto/.openclaw/workspace/StockTool/.env'))
conn=pymysql.connect(host=os.getenv('MYSQL_HOST'),port=int(os.getenv('MYSQL_PORT',3306)),user=os.getenv('MYSQL_USER'),password=os.getenv('MYSQL_PASSWORD'),database=os.getenv('MYSQL_DATABASE','stocktool_bbs'))
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM bbs_rankings WHERE date=%s AND scrape_time=%s", ('${target_date}','${target_time}'))
    n=cur.fetchone()[0]
conn.close()
raise SystemExit(0 if n>0 else 1)
PY
    then
      DB_OK=1
    fi
  fi

  if (( DB_OK == 0 )); then
    send_alert "定時データ未反映の可能性: ${target_date} ${target_time} の保存データが見つかりません"
    exit 1
  fi
fi

# healthy: clear dedupe state so next new alert can fire
: > "$STATE_FILE"
echo "OK: StockTool monitor healthy" 
exit 0
