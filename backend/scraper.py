import logging
from typing import Optional

import yfinance as yf

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)


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
