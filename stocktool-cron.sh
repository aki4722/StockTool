#!/bin/bash
# StockTool Backend - MacBook Cron
# 毎日 08:00 / 20:00 実行

cd /Users/akimoto/.openclaw/workspace/StockTool || exit 1

# Python venv 有効化
source venv/bin/activate

# 環境変数を読み込む
set -a
source .env
set +a

# ログ開始
LOG_FILE="/tmp/stocktool-macbook.log"
{
  echo "=== Cron job started at $(date) ==="
  echo "Environment: MYSQL_HOST=$MYSQL_HOST, ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:0:20}..."
  
  # Stage 1: BBS スクレイピング
  echo "Stage 1: Scraping BBS posts..."
  cd backend
  python3 bbs_scraper.py >> "$LOG_FILE" 2>&1
  SCRAPE_EXIT=$?
  echo "BBS scraping exit code: $SCRAPE_EXIT"
  
  # Stage 2: 感情分析
  echo "Stage 2: Analyzing sentiment..."
  python3 sentiment_analyzer.py >> "$LOG_FILE" 2>&1
  SENTIMENT_EXIT=$?
  echo "Sentiment analysis exit code: $SENTIMENT_EXIT"
  
  echo "=== Cron job completed at $(date) ==="
} >> "$LOG_FILE" 2>&1

exit 0
