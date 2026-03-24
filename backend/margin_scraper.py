"""
Margin Position Scraper

Scrapes margin long/short positions from Yahoo Finance Japan
and stores historical data for trend analysis.

Execution: Daily at 17:00 JST
"""

import logging
import os
import re
from datetime import date
from typing import Optional

import pymysql
import pymysql.cursors
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

DATABASE_NAME = 'stocktool_bbs'

DB_CONFIG: dict = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': DATABASE_NAME,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}


def extract_company_name(html_content: str) -> Optional[str]:
    """
    Extract company name from Yahoo Finance Japan page.
    Looks for patterns like: <h1>Sony ... | 6178</h1> or similar
    """
    try:
        # Try to find company name in h1 or title
        h1_match = re.search(r'<h1[^>]*>(.*?)\s*[\|／]\s*([0-9]+)', html_content)
        if h1_match:
            return h1_match.group(1).strip()
        
        # Fallback: look for company name in meta tags
        title_match = re.search(r'<title>(.*?)\s*-', html_content)
        if title_match:
            return title_match.group(1).strip()
        
        return None
    except Exception as e:
        log.warning(f'Could not extract company name: {e}')
        return None


def extract_margin_data(html_content: str) -> dict:
    """
    Extract margin position data from Yahoo Finance page HTML.
    
    Looks for patterns like:
    - 信用買残：1,495,100株
    - 信用売残：206,800株
    - 信用倍率：7.24倍
    """
    data = {
        'long_position': None,
        'short_position': None,
        'margin_ratio': None,
        'weekly_change_long': None,
        'weekly_change_short': None,
        'company_name': None,
    }
    
    # 信用買残 (long positions) - extract from <dd> tag after <dt>信用買残
    # Pattern: <dt>信用買残</dt><dd>...数字...株</dd>
    long_match = re.search(
        r'<dt[^>]*>.*?信用買残.*?</dt>\s*<dd[^>]*>.*?([0-9,]+)\s*株',
        html_content,
        re.DOTALL | re.IGNORECASE
    )
    if long_match:
        data['long_position'] = int(long_match.group(1).replace(',', ''))
    
    # 信用売残 (short positions)
    short_match = re.search(
        r'<dt[^>]*>.*?信用売残.*?</dt>\s*<dd[^>]*>.*?([0-9,]+)\s*株',
        html_content,
        re.DOTALL | re.IGNORECASE
    )
    if short_match:
        data['short_position'] = int(short_match.group(1).replace(',', ''))
    
    # 信用倍率 (margin ratio)
    ratio_match = re.search(
        r'<dt[^>]*>.*?信用倍率.*?</dt>\s*<dd[^>]*>.*?([0-9]+\.[0-9]+)\s*倍',
        html_content,
        re.DOTALL | re.IGNORECASE
    )
    if ratio_match:
        data['margin_ratio'] = float(ratio_match.group(1))
    
    # 前週比買い (weekly change long)
    weekly_long_match = re.search(r'前週比.*?([+\-]?[0-9,]+)\s*株', html_content)
    if weekly_long_match:
        data['weekly_change_long'] = int(weekly_long_match.group(1).replace(',', ''))
    
    # 前週比売り (weekly change short) - more complex
    # Try to find second occurrence
    weekly_matches = re.findall(r'([+\-]?[0-9,]+)\s*株', html_content)
    if len(weekly_matches) >= 2:
        try:
            data['weekly_change_short'] = int(weekly_matches[1].replace(',', ''))
        except (ValueError, IndexError):
            pass
    
    return data


async def fetch_margin_data(symbol: str) -> Optional[dict]:
    """
    Fetch margin position data for a stock using Playwright.
    
    Args:
        symbol: Stock symbol (e.g., '6178.T')
    
    Returns:
        Dict with margin data or None if fetch fails
    """
    url = f'https://finance.yahoo.co.jp/quote/{symbol}'
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.set_default_timeout(60000)  # 60 second timeout
        
        try:
            log.info(f'Fetching margin data for {symbol}...')
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(5000)  # Extra wait for dynamic content
            
            content = await page.content()
            
            # DEBUG: Save HTML to file for inspection
            debug_file = f'/tmp/margin_debug_{symbol.replace(".", "_")}.html'
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content)
            log.info(f'DEBUG: Saved HTML to {debug_file}')
            
            data = extract_margin_data(content)
            company_name = extract_company_name(content)
            
            if company_name:
                data['company_name'] = company_name
            
            if data['long_position'] and data['short_position']:
                log.info(f'{symbol}: {company_name or symbol}, Buy={data["long_position"]}, Sell={data["short_position"]}, Ratio={data["margin_ratio"]}')
                return data
            else:
                log.warning(f'{symbol}: No margin data found in page')
                return None
        
        except Exception as e:
            log.error(f'Error fetching {symbol}: {e}')
            return None
        
        finally:
            await browser.close()


def create_tables(conn):
    """Create margin tracking tables if they don't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS margin_tracking (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL UNIQUE,
                company_name VARCHAR(255),
                added_date DATE,
                INDEX idx_symbol (symbol)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS margin_positions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                date DATE NOT NULL,
                long_position INT,
                short_position INT,
                margin_ratio DECIMAL(8,2),
                weekly_change_long INT,
                weekly_change_short INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (symbol) REFERENCES margin_tracking(symbol) ON DELETE CASCADE,
                INDEX idx_symbol_date (symbol, date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        conn.commit()
        log.info('Tables created/verified')


def get_tracked_symbols(conn) -> list:
    """Get list of symbols to track from database."""
    with conn.cursor() as cur:
        cur.execute('SELECT symbol FROM margin_tracking ORDER BY symbol')
        results = cur.fetchall()
        return [row['symbol'] for row in results]


def save_margin_data(conn, symbol: str, data: dict):
    """Save margin position data to database."""
    today = date.today()
    company_name = data.get('company_name')
    
    with conn.cursor() as cur:
        # Update company name if available
        if company_name:
            cur.execute(
                'UPDATE margin_tracking SET company_name = %s WHERE symbol = %s',
                (company_name, symbol)
            )
            conn.commit()
        
        # Check if data already exists for today
        cur.execute(
            'SELECT id FROM margin_positions WHERE symbol = %s AND date = %s',
            (symbol, today)
        )
        
        if cur.fetchone():
            log.info(f'{symbol} data already exists for {today}, skipping')
            return
        
        # Insert new data
        cur.execute("""
            INSERT INTO margin_positions
            (symbol, date, long_position, short_position, margin_ratio, 
             weekly_change_long, weekly_change_short)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            symbol,
            today,
            data['long_position'],
            data['short_position'],
            data['margin_ratio'],
            data['weekly_change_long'],
            data['weekly_change_short'],
        ))
        
        conn.commit()
        log.info(f'Saved margin data for {symbol}')


async def scrape_all_margins():
    """Main scraping function for all tracked symbols."""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        create_tables(conn)
        
        symbols = get_tracked_symbols(conn)
        
        if not symbols:
            log.warning('No tracked symbols found in database')
            conn.close()
            return
        
        log.info(f'Starting margin position scrape for {len(symbols)} symbols')
        
        for symbol in symbols:
            data = await fetch_margin_data(symbol)
            
            if data:
                save_margin_data(conn, symbol, data)
            else:
                log.warning(f'Failed to get margin data for {symbol}')
        
        log.info('Margin position scrape completed')
        conn.close()
    
    except Exception as e:
        log.error(f'Fatal error during margin scrape: {e}')
        raise


if __name__ == '__main__':
    import asyncio
    asyncio.run(scrape_all_margins())
