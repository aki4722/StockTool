# StockTool

A stock price lookup tool with a Python/Flask backend that scrapes Yahoo Finance and a PHP frontend.

## Architecture

```
StockTool/
├── backend/         # Python Flask API
│   ├── app.py       # Flask routes
│   ├── scraper.py   # Yahoo Finance scraper (BeautifulSoup)
│   ├── requirements.txt
│   └── setup.sh     # venv setup helper
└── frontend/        # PHP UI
    ├── index.php    # Search form
    ├── results.php  # Results page
    └── css/
        └── style.css
```

## Setup

### Backend

```bash
cd backend
bash setup.sh
source venv/bin/activate
python app.py
```

The API runs on `http://localhost:5000`.

**Endpoints:**
- `GET /stock/<SYMBOL>` — returns price, change, and change % for a ticker
- `GET /health` — health check

### Frontend

Serve the `frontend/` directory with any PHP-capable web server:

```bash
cd frontend
php -S localhost:8080
```

Then open `http://localhost:8080` in your browser.

> **Note:** `allow_url_fopen` must be enabled in your `php.ini` for the frontend to call the backend API.
