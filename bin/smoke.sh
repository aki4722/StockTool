#!/bin/bash
# Smoke-test the web front door. Usage: bin/smoke.sh [port]   (default 80)
PORT=${1:-80}
BASE="http://127.0.0.1:$PORT"
fail=0
check() {  # $1=path $2=pattern that must appear in the body
  local body code
  body=$(curl -s -m 60 -w '\n%{http_code}' "$BASE/$1")
  code=${body##*$'\n'}; body=${body%$'\n'*}
  if [ "$code" = 200 ] && grep -q -- "$2" <<<"$body" \
     && ! grep -qiE '(Warning|Notice|Fatal error)</b>|Could not connect' <<<"$body"; then
    echo "OK   $code /$1"
  else
    echo "FAIL $code /$1"; fail=1
  fi
}
check ""                                   "StockTool"
check "bbs_ranking.php"                    "bbs-table"
check "bbs_ranking_csv.php?date=2026-10-01" ",TKY,"
check "margin_tracking.php"                "Tracked Symbols"
check "health"                             '"ok"'
check "api/bbs-dates"                      "2026-"
check "memocrip/"                          "<html"
check "memocrip/api/memos"                 "\["
exit $fail
