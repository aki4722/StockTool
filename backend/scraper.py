from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


def get_stock_data(symbol: str) -> Optional[dict]:
    url = f'https://finance.yahoo.com/quote/{symbol}'
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.text, 'lxml')

    def find_value(data_field: str) -> Optional[str]:
        tag = soup.find(attrs={'data-field': data_field})
        return tag.get_text(strip=True) if tag else None

    price_tag = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketPrice'})
    price = price_tag.get_text(strip=True) if price_tag else None

    change_tag = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketChange'})
    change = change_tag.get_text(strip=True) if change_tag else None

    change_pct_tag = soup.find('fin-streamer', {'data-symbol': symbol, 'data-field': 'regularMarketChangePercent'})
    change_pct = change_pct_tag.get_text(strip=True) if change_pct_tag else None

    return {
        'symbol': symbol,
        'price': price,
        'change': change,
        'change_percent': change_pct,
    }
