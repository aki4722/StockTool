#!/bin/bash
# StockTool Full Deployment Script

set -e

echo "🚀 StockTool Deployment Starting..."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Backend Deployment (MacBook)
echo -e "${BLUE}[1/3] Deploying Backend (MacBook)...${NC}"
cd ~/.openclaw/workspace/StockTool
git pull origin master
source venv/bin/activate
pip install -q -r backend/requirements.txt

# Restart Flask API
echo "Restarting Flask API..."
launchctl stop com.stocktool.backend 2>/dev/null || true
sleep 2
launchctl start com.stocktool.backend
echo -e "${GREEN}✅ Backend deployed${NC}"

# 2. Frontend Deployment (Mac Mini)
echo -e "${BLUE}[2/3] Deploying Frontend (Mac Mini)...${NC}"
cd ~/.openclaw/workspace/StockTool-Frontend
git pull origin main

# Copy files to Mac Mini (direct to ~/StockTool/, no frontend/ subdirectory)
echo "Copying files to Mac Mini..."
rsync -av --exclude 'venv' --exclude '.git' --exclude 'deploy.sh' --exclude 'README.md' \
  ./*.php ./css/ akimoto@192.168.2.27:~/StockTool/

echo -e "${GREEN}✅ Frontend deployed${NC}"

# 3. Verify deployment
echo -e "${BLUE}[3/3] Verifying deployment...${NC}"

# Check Flask API
if curl -s http://192.168.2.15:5001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Flask API is running${NC}"
else
    echo -e "⚠️  Flask API health check failed"
fi

# Check Frontend
if curl -s http://192.168.2.27/ > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is accessible${NC}"
else
    echo -e "⚠️  Frontend health check failed"
fi

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo "Services:"
echo "  Frontend: http://192.168.2.27/"
echo "  Backend API: http://192.168.2.15:5001/"
echo ""
echo "Next Cron runs:"
echo "  BBS Scraping: 08:00 & 20:00 JST"
echo "  Margin Scraping: 17:00 JST"
