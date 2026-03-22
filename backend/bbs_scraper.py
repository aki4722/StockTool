"""
BBS (掲示板) ranking scraper for Yahoo Finance Japan.

Fetches top 50 stocks by post count, scrapes latest 100 posts per stock,
and persists data to MySQL (stocktool_bbs database).

Page structure notes (as of 2026-03):
  - Ranking page: https://finance.yahoo.co.jp/stocks/ranking/bbs?market=all
    Server-side rendered table with class RankingTable__table__*
    Stock code in first <li class="RankingTable__supplement__vv_m">
    BBS link in <a class="RankingTable__bbsLink__2r_y">
    Post count is NOT shown in the table; we use the scraped post count.
  - BBS page: https://finance.yahoo.co.jp/quote/{CODE}.T/forum
    Next.js app; post data is embedded in self.__next_f.push([1, "..."]) scripts
    under preloadedStore.bbsComment.bbs (each entry has title, body, postDate).
    Pagination: ?page=N (0-indexed), isFetchedAllComments signals end.
"""

import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pymysql
import pymysql.cursors
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from scraper import get_stock_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

RANKING_URL = 'https://finance.yahoo.co.jp/stocks/ranking/bbs?market=all'
FORUM_URL_TEMPLATE = 'https://finance.yahoo.co.jp/quote/{code}.T/forum'

DATABASE_NAME = 'stocktool_bbs'

DB_CONFIG: dict = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection(database: Optional[str] = None) -> pymysql.Connection:
    config = DB_CONFIG.copy()
    if database:
        config['database'] = database
    return pymysql.connect(**config)


def setup_database() -> None:
    """Create database and tables if they do not exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE `{DATABASE_NAME}`")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS bbs_rankings (
                    id             INT AUTO_INCREMENT PRIMARY KEY,
                    date           DATE         NOT NULL,
                    symbol         VARCHAR(20)  NOT NULL,
                    company_name   VARCHAR(255),
                    post_count     INT,
                    status         ENUM('new', 'existing', 'dropped') NOT NULL,
                    price          DECIMAL(12,2),
                    `change`       DECIMAL(12,2),
                    change_percent DECIMAL(8,4),
                    INDEX idx_date        (date),
                    INDEX idx_symbol      (symbol),
                    INDEX idx_date_symbol (date, symbol)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)

            # Add price columns to existing tables (safe on re-run; ignore duplicate column errors)
            for col, definition in [
                ('price',          'DECIMAL(12,2)'),
                ('`change`',       'DECIMAL(12,2)'),
                ('change_percent', 'DECIMAL(8,4)'),
            ]:
                try:
                    cur.execute(f"ALTER TABLE bbs_rankings ADD COLUMN {col} {definition}")
                except pymysql.err.OperationalError as exc:
                    if exc.args[0] == 1060:  # Duplicate column name
                        pass
                    else:
                        raise

            cur.execute("""
                CREATE TABLE IF NOT EXISTS bbs_posts (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    ranking_id   INT          NOT NULL,
                    symbol       VARCHAR(20)  NOT NULL,
                    post_content TEXT,
                    created_at   DATETIME,
                    FOREIGN KEY (ranking_id) REFERENCES bbs_rankings(id) ON DELETE CASCADE,
                    INDEX idx_ranking_id (ranking_id),
                    INDEX idx_symbol     (symbol)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)

        conn.commit()
        log.info("Database '%s' is ready.", DATABASE_NAME)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------

def _get_soup(url: str, timeout: int = 30, retries: int = 2) -> Optional[BeautifulSoup]:
    """Fetch URL using Playwright (headless browser) and return BeautifulSoup.
    
    Args:
        url: Target URL to fetch
        timeout: Timeout in seconds (default 30)
        retries: Number of retry attempts (default 2)
    
    Returns:
        BeautifulSoup object or None if fetch fails after all retries
    """
    for attempt in range(retries):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(user_agent=HEADERS['User-Agent'])
                # Navigate with strict networkidle wait
                page.goto(url, wait_until='networkidle', timeout=timeout * 1000)
                # Extended delay for JS to fully execute (Yahoo uses lazy-loaded content)
                time.sleep(5)
                html = page.content()
                browser.close()
                log.debug(f"Fetched {len(html)} bytes from {url}")
                return BeautifulSoup(html, 'html.parser')
        except Exception as exc:
            log.warning(f"Playwright fetch attempt {attempt + 1}/{retries} failed for {url}: {exc}")
            if attempt < retries - 1:
                time.sleep(3)  # Brief pause before retry
                continue
            else:
                log.error(f"Playwright fetch {url} failed after {retries} attempts")
                return None
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalise whitespace."""
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'&[a-z]+;', ' ', clean)   # HTML entities
    return re.sub(r'\s+', ' ', clean).strip()


# ---------------------------------------------------------------------------
# Ranking page parsing
# ---------------------------------------------------------------------------

def _parse_ranking_page(soup: BeautifulSoup) -> list[dict]:
    """
    Parse the BBS ranking table.

    Returns list of {'code': '6740', 'company_name': '...', 'bbs_url': '...'}.
    The post count is not available on the ranking page itself.
    """
    # Table uses a class like RankingTable__table__*
    table = soup.find('table', class_=re.compile(r'RankingTable'))
    if not table:
        log.warning("RankingTable not found – trying fallback selectors.")
        table = soup.find('table')

    if not table:
        log.error("No table found on ranking page.")
        return []

    entries = []
    rows = table.select('tbody tr')
    log.info("Ranking table: %d rows", len(rows))

    for row in rows:
        # Company name: first <a> in the row (not the BBS link)
        anchors = row.find_all('a')
        name = ''
        bbs_url = ''
        for a in anchors:
            cls = ' '.join(a.get('class', []))
            href = a.get('href', '')
            if 'bbsLink' in cls or 'forum' in href:
                bbs_url = href if href.startswith('http') else 'https://finance.yahoo.co.jp' + href
            elif not name and '/quote/' in href:
                name = a.get_text(strip=True)

        # Stock code: first <li class="RankingTable__supplement__*"> that's all digits/alphanum
        code = ''
        for li in row.find_all('li'):
            txt = li.get_text(strip=True)
            # Code is 4 chars (digits or like "285A"), market names are longer
            if re.match(r'^[0-9A-Z]{4}$', txt):
                code = txt
                break

        if not code:
            # Fallback: extract from /quote/XXXX.T
            for a in anchors:
                m = re.search(r'/quote/([^./]+)\.T', a.get('href', ''))
                if m:
                    code = m.group(1)
                    break

        if not code:
            continue

        # Build BBS URL if not found via link
        if not bbs_url:
            bbs_url = FORUM_URL_TEMPLATE.format(code=code)

        entries.append({
            'code': code,
            'company_name': name,
            'bbs_url': bbs_url,
        })

    return entries


# ---------------------------------------------------------------------------
# BBS post extraction from Next.js SSR payload
# ---------------------------------------------------------------------------

def _extract_nextf_preloaded(soup: BeautifulSoup) -> Optional[dict]:
    """
    Find the self.__next_f.push([1, "..."]) script tag that contains
    preloadedStore/bbsComment and return the parsed bbsComment dict.
    """
    for script in soup.find_all('script'):
        txt = script.string or ''
        if 'preloadedStore' not in txt or 'bbsComment' not in txt:
            continue

        # The script content is: self.__next_f.push([1,"<escaped-json>"])
        m = re.search(r'__next_f\.push\(\[1,\"(.*)\"\]\)\s*$', txt, re.DOTALL)
        if not m:
            continue

        try:
            # Unescape the outer JS string literal to get the inner JSON string
            unescaped: str = json.loads('"' + m.group(1) + '"')
        except json.JSONDecodeError as exc:
            log.warning("Failed to unescape __next_f content: %s", exc)
            continue

        # The string looks like: "6:{\"preloadedStore\":{...}}"
        ps_start = unescaped.find('{"preloadedStore"')
        if ps_start == -1:
            log.debug(f"preloadedStore not found in unescaped content (first 200 chars): {unescaped[:200]}")
            continue

        json_fragment = unescaped[ps_start:]
        # Parse incrementally: find the minimal valid JSON object
        try:
            # json.JSONDecoder.raw_decode stops at the first complete object
            obj, _ = json.JSONDecoder().raw_decode(json_fragment)
            return obj.get('preloadedStore', {}).get('bbsComment')
        except json.JSONDecodeError as exc:
            log.warning("JSON parse error in preloadedStore: %s", exc)

    log.warning(f"No preloadedStore/bbsComment scripts found. Total scripts: {len(soup.find_all('script'))}")
    return None


def _posts_from_bbs_data(bbs_data: dict) -> list[str]:
    """Convert bbsComment.bbs list into plain-text post strings."""
    posts = []
    for item in bbs_data.get('bbs', []):
        title = item.get('title', '')
        body = item.get('body', '')
        date_str = item.get('postDate', '')

        # Strip HTML entities & tags from title and body
        title_clean = _strip_html(title)
        body_clean = _strip_html(body)

        parts = [p for p in [title_clean, body_clean] if p]
        text = ' | '.join(parts)
        if date_str:
            text = f"[{date_str}] {text}"
        if text.strip():
            posts.append(text)
    return posts


# ---------------------------------------------------------------------------
# Public API: fetch_bbs_rankings + fetch_bbs_posts
# ---------------------------------------------------------------------------

def fetch_bbs_posts(code: str, limit: int = 100) -> list[str]:
    """
    Scrape up to `limit` latest posts from a stock's BBS page.

    Args:
        code: numeric/alphanum Yahoo Finance code, e.g. '6740'
        limit: maximum posts to return

    Returns:
        List of post text strings.
    """
    posts: list[str] = []
    page = 0  # Yahoo Finance Japan uses 0-indexed pages for SSR content

    while len(posts) < limit:
        if page == 0:
            url = FORUM_URL_TEMPLATE.format(code=code)
        else:
            url = FORUM_URL_TEMPLATE.format(code=code) + f'?page={page}'

        soup = _get_soup(url, timeout=60)  # Extended timeout for slower systems like Mac Mini
        if soup is None:
            break

        bbs_data = _extract_nextf_preloaded(soup)
        if not bbs_data:
            log.warning("No BBS data found at %s", url)
            break

        page_posts = _posts_from_bbs_data(bbs_data)
        posts.extend(page_posts)

        if not page_posts:
            break
        if bbs_data.get('isFetchedAllComments', True):
            break  # No more pages

        page += 1
        time.sleep(0.3)

    return posts[:limit]


def fetch_bbs_rankings() -> list[dict]:
    """
    Scrape the Yahoo Finance Japan BBS ranking for all markets.

    Returns list (up to 50) of dicts:
        {
            'symbol':       '6758.T',
            'company_name': 'ソニーグループ',
            'post_count':   72,          # number of posts scraped
            'posts':        ['...', ...],
        }
    """
    log.info("Fetching BBS ranking from %s", RANKING_URL)
    soup = _get_soup(RANKING_URL)
    if soup is None:
        log.error("Failed to fetch ranking page")
        return []

    entries = _parse_ranking_page(soup)
    log.info("Found %d stocks in ranking.", len(entries))

    results = []
    for i, entry in enumerate(entries[:50], 1):
        code = entry['code']
        log.info(
            "[%d/%d] %s  %s",
            i, min(len(entries), 50), code, entry.get('company_name', '')
        )
        try:
            posts = fetch_bbs_posts(code)
            log.info(f"[{i}/{min(len(entries), 50)}] {code}: fetched {len(posts)} posts")
        except Exception as e:
            log.error(f"Error fetching posts for {code}: {e}")
            posts = []
            
        symbol = f"{code}.T"
        stock = get_stock_data(symbol)
        results.append({
            'symbol': symbol,
            'company_name': entry.get('company_name', ''),
            'post_count': len(posts),
            'posts': posts,
            'price': stock['price'] if stock else None,
            'change': stock['change'] if stock else None,
            'change_percent': stock['change_percent'] if stock else None,
        })
        time.sleep(0.5)  # polite delay between stocks

    return results


# ---------------------------------------------------------------------------
# MySQL persistence
# ---------------------------------------------------------------------------

def _get_previous_symbols(conn: pymysql.Connection, prev_date: date) -> set[str]:
    """Return symbols that were in the top-50 ranking on prev_date."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol FROM bbs_rankings WHERE date = %s AND status != 'dropped'",
            (prev_date,)
        )
        rows = cur.fetchall()
    return {row['symbol'] for row in rows}


def save_to_mysql(rankings_data: list[dict], prev_date: Optional[date] = None) -> None:
    """
    Persist today's ranking data to MySQL.

    Status logic:
      'new'      – symbol in today's top-50 but NOT in prev_date ranking
      'existing' – symbol in both today's and prev_date ranking
      'dropped'  – symbol was in prev_date ranking but NOT in today's top-50
                   (inserted with today's date so history remains continuous)
    """
    today = date.today()
    if prev_date is None:
        prev_date = today - timedelta(days=1)

    conn = get_connection(database=DATABASE_NAME)
    try:
        prev_symbols = _get_previous_symbols(conn, prev_date)
        today_symbols = {r['symbol'] for r in rankings_data}

        with conn.cursor() as cur:
            # Delete today's data to avoid duplicates (idempotent)
            cur.execute("DELETE FROM bbs_rankings WHERE date = %s", (today,))
            log.info(f"Cleared {cur.rowcount} stale rankings for {today}")
            # Insert today's ranked stocks
            for entry in rankings_data:
                symbol = entry['symbol']
                status = 'existing' if symbol in prev_symbols else 'new'
                posts = entry.get('posts', [])
                post_count = len(posts)

                log.debug(f"Saving {symbol}: {post_count} posts")

                cur.execute(
                    """
                    INSERT INTO bbs_rankings
                        (date, symbol, company_name, post_count, status, price, `change`, change_percent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        today, symbol, entry.get('company_name'), post_count, status,
                        entry.get('price'), entry.get('change'), entry.get('change_percent'),
                    )
                )
                ranking_id = cur.lastrowid

                for post_text in posts:
                    if post_text.strip():
                        cur.execute(
                            """
                            INSERT INTO bbs_posts (ranking_id, symbol, post_content, created_at)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (ranking_id, symbol, post_text, datetime.now())
                        )

            # Insert 'dropped' rows for stocks that fell out of today's top-50
            dropped = prev_symbols - today_symbols
            for symbol in dropped:
                cur.execute(
                    """
                    INSERT INTO bbs_rankings (date, symbol, company_name, post_count, status)
                    VALUES (%s, %s, NULL, NULL, 'dropped')
                    """,
                    (today, symbol)
                )
                log.info("Marked '%s' as dropped.", symbol)

        conn.commit()
        log.info(
            "Saved %d ranked + %d dropped entries for %s.",
            len(rankings_data), len(dropped), today
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main (manual test run)
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== BBS Scraper: Stage 1 test run ===")

    # 1. Ensure DB + tables exist
    setup_database()

    # 2. Fetch rankings + posts
    rankings = fetch_bbs_rankings()
    if not rankings:
        log.error("No rankings fetched. Check network / page structure.")
        return

    log.info("Fetched %d stocks.", len(rankings))
    for r in rankings[:5]:
        log.info(
            "  %s | %s | post_count=%d | posts_stored=%d",
            r['symbol'], r['company_name'], r['post_count'], len(r['posts'])
        )

    # 3. Save to MySQL
    save_to_mysql(rankings)

    # 4. Verification queries
    conn = get_connection(database=DATABASE_NAME)
    try:
        today = date.today()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, COUNT(*) AS cnt FROM bbs_rankings WHERE date = %s GROUP BY status",
                (today,)
            )
            status_counts = cur.fetchall()
            log.info("Status counts for %s: %s", today, status_counts)

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM bbs_posts p "
                "JOIN bbs_rankings r ON p.ranking_id = r.id WHERE r.date = %s",
                (today,)
            )
            post_count = cur.fetchone()
            log.info("Total posts stored for %s: %s", today, post_count)

            cur.execute(
                "SELECT symbol, company_name, post_count, status "
                "FROM bbs_rankings WHERE date = %s LIMIT 10",
                (today,)
            )
            sample = cur.fetchall()
            log.info("Sample rows:\n%s", '\n'.join(str(row) for row in sample))
    finally:
        conn.close()

    log.info("=== Stage 1 complete ===")


if __name__ == '__main__':
    main()
