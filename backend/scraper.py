import json
import logging
import os
from typing import Optional

import requests
from bs4 import BeautifulSoup
import yfinance as yf

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# Static fallback mapping (japan_stocks.json)
_JAPAN_STOCKS_PATH = os.path.join(os.path.dirname(__file__), 'japan_stocks.json')
try:
    with open(_JAPAN_STOCKS_PATH, encoding='utf-8') as _f:
        _JAPAN_NAMES_STATIC: dict[str, str] = json.load(_f)
    log.debug('Loaded %d Japan stock name mappings from static file', len(_JAPAN_NAMES_STATIC))
except Exception as _e:
    log.warning('Could not load japan_stocks.json: %s', _e)
    _JAPAN_NAMES_STATIC = {}

# In-memory cache for dynamically fetched Japanese names
_japan_name_cache: dict[str, str] = {}


def _fetch_japanese_name(symbol: str) -> Optional[str]:
    """Scrape Japanese company name from Yahoo Finance Japan."""
    # Convert 1234.T -> 1234 for the Yahoo Finance Japan URL
    code = symbol.replace('.T', '')
    url = f'https://finance.yahoo.co.jp/quote/{code}.T'
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; StockTool/1.0)',
        'Accept-Language': 'ja,en;q=0.9',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Yahoo Finance Japan: company name is in <h1> or a specific class
        # Try common selectors
        for selector in [
            'h1[class*="StyledHeadingTitle"]',
            'h1[class*="name"]',
            'h1',
            '[class*="companyName"]',
            '[class*="stockName"]',
        ]:
            tag = soup.select_one(selector)
            if tag:
                name = tag.get_text(strip=True)
                # Strip page-title suffixes like "の株価・株式情報", "の株価情報"
                for suffix in ['の株価・株式情報', 'の株価情報', 'の株価']:
                    if suffix in name:
                        name = name[:name.index(suffix)]
                        break
                if name:
                    log.debug('Scraped Japanese name for %s: %s (selector: %s)', symbol, name, selector)
                    return name

        log.warning('Could not find Japanese name for %s in page', symbol)
        return None
    except Exception as e:
        log.warning('Failed to scrape Japanese name for %s: %s', symbol, e)
        return None


def get_japanese_name(symbol: str) -> Optional[str]:
    """Return Japanese company name, using cache then scrape then static fallback."""
    if symbol in _japan_name_cache:
        return _japan_name_cache[symbol]

    name = _fetch_japanese_name(symbol)
    if name:
        _japan_name_cache[symbol] = name
        return name

    # Fall back to static JSON
    if symbol in _JAPAN_NAMES_STATIC:
        log.debug('Using static fallback name for %s', symbol)
        _japan_name_cache[symbol] = _JAPAN_NAMES_STATIC[symbol]
        return _JAPAN_NAMES_STATIC[symbol]

    return None


def get_stock_data(symbol: str) -> Optional[dict]:
    log.debug('Fetching %s via yfinance history()', symbol)
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='2d')
        if hist.empty or len(hist) < 1:
            log.error('Empty history for %s', symbol)
            return None
        price = float(hist['Close'].iloc[-1])
        if len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
        else:
            prev_close = price
        change = price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0.0
    except Exception as e:
        log.error('yfinance error for %s: %s', symbol, e)
        return None

    if symbol.endswith('.T'):
        name = get_japanese_name(symbol)
        if not name:
            # Final fallback: English name from yfinance
            try:
                name = ticker.info.get('longName') or symbol
            except Exception:
                name = symbol
    else:
        try:
            name = ticker.info.get('longName') or symbol
        except Exception:
            name = symbol

    log.info('Result — symbol=%s name=%s price=%s change=%s change_pct=%s', symbol, name, price, change, change_pct)

    return {
        'symbol': symbol,
        'name': name,
        'price': round(price, 2),
        'change': round(change, 2),
        'change_percent': round(change_pct, 2),
    }
