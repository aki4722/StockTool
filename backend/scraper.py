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


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_equity_ratio(ticker: yf.Ticker) -> Optional[float]:
    """Return equity ratio (%) from balance sheet if available.

    equity_ratio = total_equity / total_assets * 100
    """
    try:
        bs = ticker.balance_sheet
        if bs is None or bs.empty:
            return None

        equity_keys = [
            'Total Equity Gross Minority Interest',
            'Stockholders Equity',
            'Total Equity',
        ]
        assets_keys = [
            'Total Assets',
        ]

        equity = None
        assets = None

        for key in equity_keys:
            if key in bs.index:
                equity = _safe_float(bs.loc[key].iloc[0])
                if equity is not None:
                    break

        for key in assets_keys:
            if key in bs.index:
                assets = _safe_float(bs.loc[key].iloc[0])
                if assets is not None:
                    break

        if equity is None or assets is None or assets == 0:
            return None

        return round((equity / assets) * 100, 2)
    except Exception as e:
        log.debug('Could not fetch equity ratio: %s', e)
        return None


def _valuation_label(per: Optional[float], pbr: Optional[float], equity_ratio: Optional[float]) -> Optional[str]:
    if per is None and pbr is None and equity_ratio is None:
        return None

    # 割安候補
    if (
        per is not None and per < 12 and
        pbr is not None and pbr < 1.2 and
        equity_ratio is not None and equity_ratio >= 40
    ):
        return 'undervalued'

    # 割高/注意
    if (
        (per is not None and per > 20) or
        (pbr is not None and pbr > 2.0) or
        (equity_ratio is not None and equity_ratio < 25)
    ):
        return 'overvalued'

    # 中立
    return 'neutral'


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

    # Fundamentals
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    per = _safe_float(info.get('trailingPE') or info.get('forwardPE'))
    pbr = _safe_float(info.get('priceToBook'))

    dividend_yield = _safe_float(info.get('dividendYield'))
    if dividend_yield is not None:
        dividend_yield = round(dividend_yield * 100, 2)  # fraction -> %

    equity_ratio = _fetch_equity_ratio(ticker)
    valuation_label = _valuation_label(per, pbr, equity_ratio)

    if symbol.endswith('.T'):
        name = get_japanese_name(symbol)
        if not name:
            # Final fallback: English name from yfinance
            try:
                name = info.get('longName') or symbol
            except Exception:
                name = symbol
    else:
        try:
            name = info.get('longName') or symbol
        except Exception:
            name = symbol

    log.info(
        'Result — symbol=%s name=%s price=%s change=%s change_pct=%s PER=%s PBR=%s equity_ratio=%s valuation=%s',
        symbol, name, price, change, change_pct, per, pbr, equity_ratio, valuation_label
    )

    return {
        'symbol': symbol,
        'name': name,
        'price': round(price, 2),
        'change': round(change, 2),
        'change_percent': round(change_pct, 2),
        'per': round(per, 2) if per is not None else None,
        'pbr': round(pbr, 2) if pbr is not None else None,
        'dividend_yield': dividend_yield,
        'equity_ratio': equity_ratio,
        'valuation_label': valuation_label,
    }
