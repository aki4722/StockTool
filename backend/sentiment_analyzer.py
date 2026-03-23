"""
Stage 2: LLM-powered sentiment analysis engine.

Reads bbs_posts from MySQL (stocktool_bbs), analyzes each symbol's posts
using Claude API, and saves results to bbs_sentiment table.

Functions:
  analyze_posts_sentiment(symbol, posts_list) -> float
  analyze_bbs_ranking(date_str) -> None
"""

import json
import logging
import os
from datetime import date, datetime
from typing import Optional

import anthropic
import pymysql
import pymysql.cursors

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

# Use latest Claude model for sentiment analysis
CLAUDE_MODEL = 'claude-3-5-sonnet-20241022'  # Fast, balanced model for sentiment analysis


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection() -> pymysql.Connection:
    return pymysql.connect(**DB_CONFIG)


def setup_sentiment_table() -> None:
    """Create bbs_sentiment table if it does not exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bbs_sentiment (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    symbol          VARCHAR(20)   NOT NULL,
                    date            DATE          NOT NULL,
                    sentiment_score FLOAT         NOT NULL COMMENT '-1.0 (bearish) to +1.0 (bullish)',
                    key_topics      TEXT          COMMENT 'JSON array of key topics',
                    risk_level      ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
                    analyzed_at     DATETIME      NOT NULL,
                    price           DECIMAL(12,2),
                    `change`        DECIMAL(12,2),
                    change_percent  DECIMAL(8,4),
                    UNIQUE KEY uq_symbol_date (symbol, date),
                    INDEX idx_date (date)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)

            # Add price columns to existing tables (safe on re-run; ignore duplicate column errors)
            for col, definition in [
                ('price',          'DECIMAL(12,2)'),
                ('`change`',       'DECIMAL(12,2)'),
                ('change_percent', 'DECIMAL(8,4)'),
            ]:
                try:
                    cur.execute(f"ALTER TABLE bbs_sentiment ADD COLUMN {col} {definition}")
                except pymysql.err.OperationalError as exc:
                    if exc.args[0] == 1060:  # Duplicate column name
                        pass
                    else:
                        raise
        conn.commit()
        log.info("bbs_sentiment table is ready.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Core sentiment analysis via Claude API
# ---------------------------------------------------------------------------

def analyze_posts_sentiment(symbol: str, posts_list: list[str]) -> dict:
    """
    Analyze a list of BBS posts for a stock symbol using Claude.

    Args:
        symbol: Stock symbol, e.g. '6758.T'
        posts_list: List of post text strings (up to 100)

    Returns:
        Dict with:
          sentiment_score: float (-1.0 to +1.0)
          key_topics: list[str]
          risk_level: 'low' | 'medium' | 'high'
    """
    if not posts_list:
        return {'sentiment_score': 0.0, 'key_topics': [], 'risk_level': 'medium'}

    client = anthropic.Anthropic()

    # Prepare posts text (truncate very long individual posts)
    posts_text = '\n---\n'.join(posts_list[:100])
    # Cap total input to ~12000 chars to keep cost low
    if len(posts_text) > 12000:
        posts_text = posts_text[:12000] + '\n...(truncated)'

    prompt = f"""You are a Japanese stock market analyst. Analyze the following BBS (bulletin board) posts about stock symbol {symbol} from Yahoo Finance Japan.

These are investor/trader forum posts. Many may be in Japanese.

BBS Posts:
{posts_text}

Analyze these posts and respond with a JSON object containing exactly these fields:
{{
  "sentiment_score": <float between -1.0 and 1.0>,
  "key_topics": <array of 3-7 topic strings in English>,
  "risk_level": "<low|medium|high>",
  "reasoning": "<1-2 sentence summary>"
}}

Scoring guide:
- sentiment_score: -1.0 = strongly bearish/negative, 0.0 = neutral/mixed, +1.0 = strongly bullish/positive
- key_topics: identify main themes (e.g. "earnings beat", "technical breakout", "dividend cut", "insider selling")
- risk_level: low = mostly calm/factual posts, medium = some speculation/concern, high = panic/controversy/risk warnings

Respond ONLY with the JSON object, no other text."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = next((b.text for b in response.content if b.type == 'text'), '{}')

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(0))
            except json.JSONDecodeError:
                result = {}
        else:
            result = {}

    sentiment_score = float(result.get('sentiment_score', 0.0))
    sentiment_score = max(-1.0, min(1.0, sentiment_score))

    key_topics = result.get('key_topics', [])
    if not isinstance(key_topics, list):
        key_topics = []

    risk_level = result.get('risk_level', 'medium')
    if risk_level not in ('low', 'medium', 'high'):
        risk_level = 'medium'

    log.info(
        "%s: score=%.3f risk=%s topics=%s | %s",
        symbol, sentiment_score, risk_level,
        key_topics[:3], result.get('reasoning', '')[:80]
    )

    # Log token usage for cost tracking
    usage = response.usage
    log.debug(
        "%s token usage: input=%d output=%d",
        symbol, usage.input_tokens, usage.output_tokens
    )

    return {
        'sentiment_score': sentiment_score,
        'key_topics': key_topics,
        'risk_level': risk_level,
    }


# ---------------------------------------------------------------------------
# Batch analysis
# ---------------------------------------------------------------------------

def analyze_bbs_ranking(date_str: str) -> None:
    """
    Read today's bbs_posts from MySQL, analyze each symbol's posts via Claude,
    and save results to bbs_sentiment table.

    Args:
        date_str: Date string in 'YYYY-MM-DD' format
    """
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    setup_sentiment_table()

    conn = get_connection()
    try:
        # Fetch all symbols, their posts, and price data for the target date
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.symbol, r.company_name,
                       r.price, r.`change`, r.change_percent,
                       GROUP_CONCAT(p.post_content SEPARATOR '\n---\n') AS posts_text
                FROM bbs_rankings r
                JOIN bbs_posts p ON p.ranking_id = r.id
                WHERE r.date = %s AND r.status != 'dropped'
                GROUP BY r.symbol, r.company_name, r.price, r.`change`, r.change_percent
                ORDER BY r.symbol
                """,
                (target_date,)
            )
            rows = cur.fetchall()

        if not rows:
            log.warning("No posts found in DB for date %s. Run bbs_scraper.py first.", date_str)
            return

        log.info("Analyzing sentiment for %d symbols on %s", len(rows), date_str)

        analyzed_at = datetime.now()
        total_input_tokens = 0
        total_output_tokens = 0

        for i, row in enumerate(rows, 1):
            symbol = row['symbol']
            posts_text = row['posts_text'] or ''
            posts_list = [p.strip() for p in posts_text.split('\n---\n') if p.strip()]

            log.info("[%d/%d] Analyzing %s (%d posts)", i, len(rows), symbol, len(posts_list))

            result = analyze_posts_sentiment(symbol, posts_list)

            # Upsert into bbs_sentiment (replace if already exists for this symbol+date)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bbs_sentiment
                        (symbol, date, sentiment_score, key_topics, risk_level, analyzed_at,
                         price, `change`, change_percent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        sentiment_score = VALUES(sentiment_score),
                        key_topics      = VALUES(key_topics),
                        risk_level      = VALUES(risk_level),
                        analyzed_at     = VALUES(analyzed_at),
                        price           = VALUES(price),
                        `change`        = VALUES(`change`),
                        change_percent  = VALUES(change_percent)
                    """,
                    (
                        symbol,
                        target_date,
                        result['sentiment_score'],
                        json.dumps(result['key_topics'], ensure_ascii=False),
                        result['risk_level'],
                        analyzed_at,
                        row.get('price'),
                        row.get('change'),
                        row.get('change_percent'),
                    )
                )
            conn.commit()

    finally:
        conn.close()

    log.info("=== Sentiment analysis complete for %s ===", date_str)

    # Show results
    _print_results(target_date)


def _print_results(target_date: date) -> None:
    """Print a summary of sentiment results from DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, sentiment_score, key_topics, risk_level, analyzed_at
                FROM bbs_sentiment
                WHERE date = %s
                ORDER BY sentiment_score DESC
                """,
                (target_date,)
            )
            rows = cur.fetchall()

        log.info("=== Sentiment Results for %s (%d symbols) ===", target_date, len(rows))
        for row in rows:
            topics = json.loads(row['key_topics'] or '[]')
            log.info(
                "  %-12s score=%+.3f risk=%-6s topics=%s",
                row['symbol'],
                row['sentiment_score'],
                row['risk_level'],
                ', '.join(topics[:3]),
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run sentiment analysis for 2026-03-20 and verify results."""
    log.info("=== Stage 2: LLM Sentiment Analysis ===")
    analyze_bbs_ranking('2026-03-20')


if __name__ == '__main__':
    main()
