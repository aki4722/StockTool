# StockTool 統合環境 運用手順

Mac mini (192.168.2.27, Ubuntu) 1 台で Frontend + Backend + MySQL を動かす環境。
旧環境 (`~/StockTool` の compose プロジェクト `stocktool` + MacBook 上の Flask/cron) とは
プロジェクト名・ポート・ボリューム・パスワードを分けてあり、互いに干渉しない。

## 構成

| サービス | 中身 | ポート |
|---|---|---|
| `web` | nginx + PHP 8.2 (StockTool-Frontend, branch `integrated-env`) | `${WEB_HOST_PORT}` (テスト時 8080) |
| `backend` | Flask on gunicorn + Playwright (StockTool backend, branch `integrated-env`) | `127.0.0.1:15001` のみ |
| `mysql` | MySQL 8.0, volume `stocktool-integrated_mysql_data` | 公開しない |

- `frontend/` `backend/` は各アプリリポジトリの git worktree。コード変更はそれぞれのリポジトリでコミットする。
- `web` は memocrip の `/memocrip/` プロキシのため旧ネットワーク `stocktool_default` にも参加する。
- センチメント分析 (Stage 2) は無効。`ANTHROPIC_API_KEY` は渡していない。
- 定期実行はホストの crontab (`crontab.txt`) から `bin/run-job.sh` を呼ぶ。ログは `logs/`。

## よく使うコマンド

```bash
cd ~/stocktool-integrated
docker compose ps
docker compose logs -f backend
docker compose build && docker compose up -d     # コード更新の反映
bin/run-job.sh bbs                               # BBS スクレイプを手動実行
bin/sync-db-from-legacy.sh                       # 旧 DB → 新 DB へ StockTool テーブルを再コピー
```

## 本番切り替え (要: 事前に日時と DB 方針を決める)

1. **書き込み元を止める** (MacBook): BBS と信用残のスクレイパーの定期実行、Flask (`app.py`) を停止。
   以後、旧 DB に書き込むものは memocrip だけになる。
2. **最終同期**: `bin/sync-db-from-legacy.sh` (テスト中に新 DB に入ったデータは旧 DB の内容で置き換わる)。
   `=== OK: identical` を確認。
3. **ポート 80 の切り替え**:
   ```bash
   docker stop stocktool-app-1                        # 旧 web だけ止める。旧 mysql は memocrip が使うので止めない
   sed -i 's/^WEB_HOST_PORT=.*/WEB_HOST_PORT=80/' .env
   docker compose up -d web
   ```
4. **定期実行を登録**: `crontab -l | cat - crontab.txt | crontab -`
5. **確認**: http://192.168.2.27/ の各ページ、`/memocrip/`、次の 08:00/20:00 のスクレイプ結果 (`logs/`)。

## 切り戻し

```bash
cd ~/stocktool-integrated
crontab -l | grep -v stocktool-integrated | crontab -     # 新環境の定期実行を外す
sed -i 's/^WEB_HOST_PORT=.*/WEB_HOST_PORT=8080/' .env && docker compose up -d web
docker start stocktool-app-1                               # 旧 web を戻す
```
MacBook 側の Flask と定期実行を再開すれば完全に元の状態。旧 DB は切り替え中も変更していない。
(切り替え後に新 DB だけに入ったスクレイプ結果は旧 DB に無い。必要なら逆方向に dump する。)

## 未解決

- memocrip は旧 MySQL (`stocktool-mysql-1`) に接続先をハードコードしている。旧 MySQL を廃止するには memocrip の移行が別途必要。
- MacBook 側の信用残スクレイパー (毎日 08:00) の起動元が未特定 (crontab は空。launchd 等)。
- `requirements.txt` はバージョン未固定。
