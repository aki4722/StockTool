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
from pathlib import Path
from typing import Optional

import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Load environment variables from .env file in parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

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
    'autocommit': False,
}


def extract_company_name(html_content: str) -> Optional[str]:
    """
    Extract company name from Yahoo Finance Japan page using BeautifulSoup.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for company name in PriceBoard section
        # Class: PriceBoard__name__166W
        name_element = soup.find('h2', class_=re.compile(r'PriceBoard__name'))
        if name_element:
            company_name = name_element.get_text(strip=True)
            log.info(f'Extracted company name: {company_name}')
            return company_name
        
        # Fallback: try meta title
        title = soup.find('title')
        if title:
            title_text = title.get_text()
            # Usually format: "Company Name【CODE】- Yahoo!ファイナンス"
            if '【' in title_text:
                company_name = title_text.split('【')[0].strip()
                log.info(f'Extracted company name from title: {company_name}')
                return company_name
        
        return None
    except Exception as e:
        log.warning(f'Could not extract company name: {e}')
        return None


def extract_margin_data(html_content: str) -> dict:
    """
    Extract margin position data from Yahoo Finance page HTML using BeautifulSoup.
    
    Looks for:
    - 信用買残：long position (shares)
    - 信用売残：short position (shares)
    - 信用倍率：margin ratio
    - 前週比：weekly changes
    """
    data = {
        'long_position': None,
        'short_position': None,
        'margin_ratio': None,
        'weekly_change_long': None,
        'weekly_change_short': None,
        'company_name': None,
    }
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all dt/dd pairs in the margin information section
        margin_section = soup.find('section', id='margin')
        if not margin_section:
            log.warning('Margin section not found in page')
            return data
        
        # Find all dt elements
        dt_elements = margin_section.find_all('dt')
        
        for dt in dt_elements:
            dt_text = dt.get_text(strip=True)
            
            # Find the next dd sibling
            dd = dt.find_next_sibling('dd')
            if not dd:
                continue
            
            # Extract value from nested spans
            # Look for <span class="StyledNumber__value__3rXW">
            value_span = dd.find('span', class_=re.compile(r'StyledNumber__value'))
            if not value_span:
                continue
            
            value_text = value_span.get_text(strip=True)
            
            # Parse based on label
            if '信用買残' in dt_text:
                # Long position
                try:
                    data['long_position'] = int(value_text.replace(',', ''))
                    log.info(f'Extracted long_position: {data["long_position"]}')
                except ValueError:
                    log.warning(f'Could not parse long_position: {value_text}')
            
            elif '信用売残' in dt_text:
                # Short position
                try:
                    data['short_position'] = int(value_text.replace(',', ''))
                    log.info(f'Extracted short_position: {data["short_position"]}')
                except ValueError:
                    log.warning(f'Could not parse short_position: {value_text}')
            
            elif '信用倍率' in dt_text:
                # Margin ratio
                try:
                    data['margin_ratio'] = float(value_text.replace(',', ''))
                    log.info(f'Extracted margin_ratio: {data["margin_ratio"]}')
                except ValueError:
                    log.warning(f'Could not parse margin_ratio: {value_text}')
            
            elif '前週比' in dt_text and '買' not in dt_text and '売' not in dt_text:
                # Weekly change - determine if it's for long or short
                # First occurrence is usually for long positions
                parent_li = dt.find_parent('li')
                if parent_li:
                    # Check if this is the first or second weekly change
                    all_weekly_changes = margin_section.find_all('dt', string=re.compile('前週比'))
                    if all_weekly_changes and all_weekly_changes[0] == dt:
                        # First occurrence - weekly change for long
                        try:
                            clean_value = value_text.replace(',', '').replace('+', '')
                            data['weekly_change_long'] = int(clean_value)
                            log.info(f'Extracted weekly_change_long: {data["weekly_change_long"]}')
                        except ValueError:
                            log.warning(f'Could not parse weekly_change_long: {value_text}')
                    elif len(all_weekly_changes) > 1 and all_weekly_changes[1] == dt:
                        # Second occurrence - weekly change for short
                        try:
                            clean_value = value_text.replace(',', '').replace('+', '')
                            data['weekly_change_short'] = int(clean_value)
                            log.info(f'Extracted weekly_change_short: {data["weekly_change_short"]}')
                        except ValueError:
                            log.warning(f'Could not parse weekly_change_short: {value_text}')
        
        return data
    
    except Exception as e:
        log.error(f'Error parsing HTML with BeautifulSoup: {e}')
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
        
        existing = cur.fetchone()
        
        if existing:
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
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        create_tables(conn)
        
        symbols = get_tracked_symbols(conn)
        
        if not symbols:
            log.warning('No tracked symbols found in database')
            if conn:
                conn.close()
            return
        
        log.info(f'Starting margin position scrape for {len(symbols)} symbols')
        
        for symbol in symbols:
            data = await fetch_margin_data(symbol)
            
            if data:
                save_margin_data(conn, symbol, data)
            else:
                log.warning(f'Failed to get margin data for {symbol}')
        
        # Ensure all changes are committed before closing
        conn.commit()
        log.info('All changes committed to database')
        log.info('Margin position scrape completed')
    
    except Exception as e:
        log.error(f'Fatal error during margin scrape: {e}')
        if conn:
            conn.rollback()
        raise
    
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(scrape_all_margins())
