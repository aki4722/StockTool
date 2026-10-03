# StockTool 統合環境 運用手順

Mac mini (192.168.2.27, Ubuntu) 1 台で Frontend + Backend を動かし、本番データは
既存の MySQL コンテナ `stocktool-mysql-1` (旧 `~/StockTool` プロジェクト、memocrip と共用) を使う。

```
browser ─▶ web (nginx+PHP) ─▶ backend (gunicorn+Playwright) ─▶ stocktool-mysql-1 ◀─ memocrip
                                                                 (本番 DB の正本・唯一)
```

## 構成

| サービス | 中身 | ポート |
|---|---|---|
| `web` | nginx + PHP 8.2 (StockTool-Frontend, branch `integrated-env`) | `${WEB_HOST_PORT}` (切替前 8080 / 切替後 80) |
| `backend` | Flask on gunicorn + Playwright (StockTool backend, branch `integrated-env`) | `127.0.0.1:15001` のみ |
| `mysql` | **検証専用** MySQL 8.0 (`COMPOSE_PROFILES=testdb` の時だけ起動)。本番では使わない | 公開しない |

- ディレクトリ配置 (Mac mini):
  ```
  ~/stocktool-integrated/                 ← ビルドコンテキスト
  ├── frontend/        StockTool-Frontend の worktree (branch integrated-env)
  └── backend/         StockTool の worktree (branch integrated-env)
      └── deploy/      ← この手順書。compose はここで実行する
          ├── .env  logs/  backups/       (git 管理外: 秘密情報・実行時データ)
  ```
  コード変更はそれぞれのリポジトリでコミットする。ビルド時の除外は `docker/*.Dockerfile.dockerignore`。
- `web` `backend` は旧ネットワーク `stocktool_default` にも参加し、`stocktool-mysql-1` と memocrip に名前で到達する。
- backend の DB 接続先は `.env` の `BACKEND_MYSQL_HOST` / `BACKEND_MYSQL_PASSWORD` (本番: `stocktool-mysql-1`)。
- センチメント分析 (Stage 2) は無効。`ANTHROPIC_API_KEY` は渡していない。
- 定期実行はホストの crontab (`crontab.txt`) から `bin/run-job.sh` を呼ぶ。ログは `logs/`。

## よく使うコマンド

```bash
cd ~/stocktool-integrated/backend/deploy
docker compose ps
docker compose logs -f backend
docker compose build && docker compose up -d     # コード更新の反映
bin/run-job.sh bbs                               # BBS スクレイプを手動実行 (本番 DB に書く)
```

検証用 DB で試す場合: `.env` の `BACKEND_MYSQL_HOST=stocktool-integrated-mysql-1`、
`BACKEND_MYSQL_PASSWORD` を `MYSQL_PASSWORD` の値にして `COMPOSE_PROFILES=testdb docker compose up -d`。
`bin/sync-db-from-legacy.sh` で本番 DB の StockTool テーブルを検証用 DB にコピーできる (本番 DB には書かない)。

## 本番切り替え

前提: 切替前確認がすべて合格していること。

1. **MacBook: 定期処理を止める** (二重実行防止。利用者への影響なし)
   - launchd (BBS 08:00/20:00, `RunAtLoad` のためログイン時にも 1 回走る):
     ```bash
     launchctl bootout gui/$(id -u)/com.stocktool.cron
     mkdir -p ~/Library/LaunchAgents.disabled
     mv ~/Library/LaunchAgents/com.stocktool.cron.plist ~/Library/LaunchAgents.disabled/
     ```
   - OpenClaw の定期ジョブ 3 件を **無効化** (削除ではなく disable。他のジョブには触らない):
     | ID | 名前 | 時刻 |
     |---|---|---|
     | `ca5c2d1a-b870-471c-b461-262181a96604` | StockTool Backend 08:00 JST (stocktool-cron.sh) | 08:00 |
     | `7e5a2134-c515-463a-a27b-b6d3e70b9bf1` | StockTool Backend 20:00 JST (stocktool-cron.sh) | 20:00 |
     | `d0f7d86b-8163-422e-ba82-a85e3d53165c` | StockTool Margin Scraper (Daily 17:00) | 17:00 |
     これらは結果を Discord (channel 1482885087652741141) に報告していた。切替後この報告は止まる。
2. **Mac mini: `bin/cutover.sh`** (数秒の停止)
   事前チェック → `.env`/crontab をバックアップ (`backups/`) → `docker stop stocktool-app-1` →
   新 web を :80 で起動 → `bin/smoke.sh 80` (失敗したら自動で `bin/rollback.sh`) →
   crontab を差し替え (動いていない旧エントリ `~/StockTool/cron-bbs-scrape.sh` を削除し `crontab.txt` を追加。
   メール監視のエントリはそのまま) → 検証用 MySQL を停止。
   `stocktool-mysql-1` と memocrip には触らない。
3. **MacBook: Flask とログ監視を止める** (旧 web が使っていた API。ここで初めて不要になる)
4. **確認**: http://192.168.2.27/ の各ページ・`/memocrip/`、MacBook で `launchctl list | grep stocktool` が空。
   初回の正式実行: 17:00 信用残 (`logs/margin-YYYYMM.log`、`margin_positions` の当日行)、
   20:00 BBS (`logs/bbs-YYYYMM.log`、`bbs_rankings` の当日 20:00 スロット)。
5. 動作確認後に各リポジトリの `integrated-env` を main へマージ。

注意: 切替後は `~/StockTool/deploy.sh` や `~/StockTool` での `docker compose up` を実行しない
(旧 web がポート 80 を取りに行く)。旧プロジェクトで触ってよいのは `stocktool-mysql-1` だけ。

## 切り戻し

```bash
~/stocktool-integrated/backend/deploy/bin/rollback.sh        # Mac mini: 旧 web を :80 に戻し、新 web は :8080、crontab を復元
```
MacBook 側は停止したジョブを元に戻す (MacBook 手順書の「切り戻し」)。
DB は切替前後で同じ (`stocktool-mysql-1`) なので、データの戻し作業は不要。

## 未解決

- Discord への実行結果通知 (旧 OpenClaw ジョブが担当) は新環境に未移植。
- 旧 MySQL のタイムゾーンは UTC (`margin_positions.created_at` は UTC で記録される)。
- `requirements.txt` はバージョン未固定。
- 旧 MySQL のポート 3306 が LAN に公開されたまま (MacBook の Flask 停止後は不要)。
