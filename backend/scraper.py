import json
import logging
import os
from typing import Optional

import yfinance as yf

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

_JAPAN_STOCKS_PATH = os.path.join(os.path.dirname(__file__), 'japan_stocks.json')
try:
    with open(_JAPAN_STOCKS_PATH, encoding='utf-8') as _f:
        _JAPAN_NAMES: dict[str, str] = json.load(_f)
    log.debug('Loaded %d Japan stock name mappings', len(_JAPAN_NAMES))
except Exception as _e:
    log.warning('Could not load japan_stocks.json: %s', _e)
    _JAPAN_NAMES = {}


def get_stock_data(symbol: str) -> Optional[dict]:
    log.debug('Fetching %s via yfinance', symbol)
    try:
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        price = fast.last_price
        prev_close = fast.previous_close
        if price is None or prev_close is None:
            log.error('Missing price data for %s', symbol)
            return None
        change = price - prev_close
        change_pct = (change / prev_close) * 100
    except Exception as e:
        log.error('yfinance error for %s: %s', symbol, e)
        return None

    if symbol.endswith('.T') and symbol in _JAPAN_NAMES:
        name = _JAPAN_NAMES[symbol]
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
