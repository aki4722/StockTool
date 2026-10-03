# MacBook 側の停止手順 (本番切り替え 2026-10-03)

MacBook (192.168.2.15) で StockTool を動かしていた起動元:

| 処理 | 起動元 | 時刻 (JST) |
|---|---|---|
| Flask (`app.py`, :5001) | launchd `com.stocktool.backend` (`KeepAlive`, `RunAtLoad`) | 常駐 |
| BBS (`stocktool-cron.sh`) | launchd `com.stocktool.cron` (`RunAtLoad`) | 08:00 / 20:00 |
| BBS (`stocktool-cron.sh`) | OpenClaw `ca5c2d1a-b870-471c-b461-262181a96604` / `7e5a2134-c515-463a-a27b-b6d3e70b9bf1` | 08:00 / 20:00 |
| 信用残 (`margin_scraper.py`) | OpenClaw `d0f7d86b-8163-422e-ba82-a85e3d53165c` | 17:00 |
| ログ監視 (`monitor-stocktool.sh`) | launchd `com.akimoto.stocktool.monitor` | 10 分ごと |

## フェーズ 1: 定期処理の停止 (Mac mini の `bin/cutover.sh` より前)

```bash
# 1-0. 実行中のジョブが無いことを確認 (あれば終わるまで待つ)
pgrep -fl "stocktool-cron.sh|bbs_scraper|margin_scraper" || echo "no job running"

# 1-1. OpenClaw の StockTool ジョブ 3 件を無効化 (削除しない・他のジョブは触らない)
#      サブコマンド名は openclaw cron --help で確認すること
openclaw cron disable ca5c2d1a-b870-471c-b461-262181a96604   # StockTool Backend 08:00 JST
openclaw cron disable 7e5a2134-c515-463a-a27b-b6d3e70b9bf1   # StockTool Backend 20:00 JST
openclaw cron disable d0f7d86b-8163-422e-ba82-a85e3d53165c   # StockTool Margin Scraper (Daily 17:00)
openclaw cron list                                           # 上の 3 件だけ disabled になっていること

# 1-2. launchd の BBS ジョブを停止し、再ログインで復活しないよう plist を退避
launchctl bootout gui/$(id -u)/com.stocktool.cron
mkdir -p ~/Library/LaunchAgents.disabled
mv ~/Library/LaunchAgents/com.stocktool.cron.plist ~/Library/LaunchAgents.disabled/

# 1-3. 確認
launchctl list | grep com.stocktool.cron || echo "launchd cron: stopped"
```

## フェーズ 3: Flask とログ監視の停止 (Mac mini の切り替え成功後)

```bash
# 3-1. Flask (KeepAlive なので kill ではなく bootout) とログ監視を停止
launchctl bootout gui/$(id -u)/com.stocktool.backend
launchctl bootout gui/$(id -u)/com.akimoto.stocktool.monitor
mv ~/Library/LaunchAgents/com.stocktool.backend.plist \
   ~/Library/LaunchAgents/com.akimoto.stocktool.monitor.plist ~/Library/LaunchAgents.disabled/

# 3-2. 確認
sleep 3
pgrep -fl "app.py" || echo "flask: stopped"
curl -s -m 3 http://localhost:5001/health || echo "port 5001: down"
launchctl list | grep stocktool || echo "launchd: no stocktool jobs"

# 3-3. (推奨) 安全策: 旧コードが誤って動いても本番 DB に書けないよう接続情報を退避
mv ~/.openclaw/workspace/StockTool/.env ~/.openclaw/workspace/StockTool/.env.disabled-20261003
```

## 切り戻し (MacBook)

```bash
mv ~/.openclaw/workspace/StockTool/.env.disabled-20261003 ~/.openclaw/workspace/StockTool/.env   # 3-3 を実施した場合
mv ~/Library/LaunchAgents.disabled/com.stocktool.backend.plist \
   ~/Library/LaunchAgents.disabled/com.stocktool.cron.plist \
   ~/Library/LaunchAgents.disabled/com.akimoto.stocktool.monitor.plist ~/Library/LaunchAgents/
for j in com.stocktool.backend com.akimoto.stocktool.monitor com.stocktool.cron; do
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/$j.plist
done
openclaw cron enable ca5c2d1a-b870-471c-b461-262181a96604
openclaw cron enable 7e5a2134-c515-463a-a27b-b6d3e70b9bf1
openclaw cron enable d0f7d86b-8163-422e-ba82-a85e3d53165c
```
注意: `com.stocktool.cron` は `RunAtLoad` のため、bootstrap した瞬間に BBS スクレイプが 1 回走る。
