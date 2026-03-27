# StockTool デプロイ手順

## 📁 ディレクトリ構造

### MacBook（開発環境）
```
~/.openclaw/workspace/
├── StockTool/                    # Backend (Python)
│   ├── backend/
│   │   ├── bbs_scraper.py
│   │   ├── sentiment_analyzer.py
│   │   ├── margin_scraper.py
│   │   └── app.py (Flask API)
│   ├── venv/
│   └── deploy.sh
│
└── StockTool-Frontend/           # Frontend (PHP) 開発用
    ├── bbs_ranking.php
    ├── dashboard.php
    ├── index.php
    └── css/
```

### Mac Mini（本番環境）
```
~/StockTool/                      # フロントエンド本番 (Docker)
├── bbs_ranking.php               ← 直下に配置（frontend/ではない）
├── dashboard.php
├── index.php
├── css/
├── docker-compose.yml
└── Dockerfile
```

**重要**: Mac Miniでは`~/StockTool/`直下にPHPファイルが配置されています。
`~/StockTool/frontend/`サブディレクトリは**存在しません**。

---

## 🚀 デプロイ方法

### 方法1: 自動デプロイ（推奨）

MacBookで実行：
```bash
cd ~/.openclaw/workspace/StockTool
./deploy.sh
```

すべて自動で：
1. Backend更新 + Flask API再起動
2. Frontend更新（Mac Miniへrsync）
3. サービス稼働確認

---

### 方法2: 個別デプロイ

#### Backend（MacBook）
```bash
cd ~/.openclaw/workspace/StockTool
git pull origin master
source venv/bin/activate
pip install -r backend/requirements.txt

# Flask API再起動
launchctl restart com.stocktool.backend
```

#### Frontend（Mac Mini）

**単一ファイル:**
```bash
cd ~/.openclaw/workspace/StockTool-Frontend
cat bbs_ranking.php | ssh akimoto@192.168.2.27 'cat > ~/StockTool/bbs_ranking.php'
```

**複数ファイル:**
```bash
cd ~/.openclaw/workspace/StockTool-Frontend
rsync -av *.php css/ akimoto@192.168.2.27:~/StockTool/
```

**Mac Mini上で直接編集:**
```bash
ssh akimoto@192.168.2.27
cd ~/StockTool
nano bbs_ranking.php
```

---

## ✅ 動作確認

### Frontend
```bash
curl http://192.168.2.27/
```

### Backend API
```bash
curl http://192.168.2.15:5001/health
```

### Flask API プロセス
```bash
launchctl list | grep stocktool
```

### Docker（Mac Mini）
```bash
ssh akimoto@192.168.2.27 'docker ps'
```

---

## ⚠️ 注意事項

1. **Cronジョブ**: Pythonコード変更は次回実行時から自動反映（再起動不要）
2. **Flask API**: `launchctl restart`で即座に反映
3. **Frontend**: ファイルコピー後は即座に反映（Docker再起動不要）
4. **データベーススキーマ**: 手動でMySQLに接続して実行

---

## 🔧 トラブルシューティング

### Flask APIが起動しない
```bash
launchctl list | grep stocktool
tail -f /tmp/stocktool-backend.log
tail -f /tmp/stocktool-backend-error.log
```

### Frontendが表示されない
```bash
ssh akimoto@192.168.2.27
docker logs stocktool-app-1
docker compose restart
```

### Cronジョブが実行されない
```bash
tail -f /tmp/stocktool-macbook.log
```

---

## 📋 デプロイチェックリスト

- [ ] Backend更新: `git pull` → `pip install -r requirements.txt`
- [ ] Flask API再起動: `launchctl restart com.stocktool.backend`
- [ ] Frontend更新: `rsync` または `deploy.sh`
- [ ] 動作確認: Frontend/API両方にアクセス
- [ ] Cron確認: ログファイルで次回実行時刻を確認
