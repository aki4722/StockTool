"""
Stage 2: LLM-powered sentiment analysis engine.

Reads bbs_posts from MySQL (stocktool_bbs), analyzes each symbol's posts
using Claude API, and saves results to bbs_sentiment table.

Functions:
  analyze_posts_sentiment(client, symbol, posts_list) -> dict
  analyze_bbs_ranking(date_str, scrape_time=None) -> dict (counts)
"""

import json
import logging
import math
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import anthropic
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

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
}

# Claude model from environment. The previous fallback (claude-3-5-sonnet-20241022)
# was retired on 2025-10-28 and now fails with 404.
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-opus-5-5')

# Per-request timeout in seconds. The SDK also retries 408/409/429/5xx and
# connection errors CLAUDE_MAX_RETRIES times before raising.
CLAUDE_TIMEOUT = float(os.getenv('CLAUDE_TIMEOUT', '120'))
CLAUDE_MAX_RETRIES = int(os.getenv('CLAUDE_MAX_RETRIES', '3'))

# Abort the run after this many symbols fail in a row (e.g. credit exhausted,
# API outage) instead of making ~50 doomed requests.
MAX_CONSECUTIVE_FAILURES = 5

MAX_POSTS_PER_SYMBOL = 100
MAX_POSTS_CHARS = 12000  # cap on prompt input per symbol to keep cost low

# Request options only the Claude 5.5 models accept (passed via extra_* so they
# work with the 0.x SDK pinned by Python 3.9). Short classification task, so low
# effort; server-side fallback retries on another model if a safety classifier
# declines the request.
_MODEL_EXTRAS = {
    model: {
        'extra_headers': {'anthropic-beta': 'server-side-fallback-2026-07-01'},
        'extra_body': {'fallbacks': 'default', 'output_config': {'effort': 'low'}},
    }
    for model in ('claude-opus-5-5', 'claude-sonnet-5-5')
}


class SentimentAnalysisError(Exception):
    """Analysis failed for one symbol; skip it and continue with the rest."""


class FatalAnalysisError(Exception):
    """Configuration-level failure (bad key, unknown model, ...); abort the run."""


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
                    scrape_time     TIME          NOT NULL DEFAULT '08:00:00',
                    sentiment_score FLOAT         NOT NULL COMMENT '-1.0 (bearish) to +1.0 (bullish)',
                    key_topics      TEXT          COMMENT 'JSON array of key topics',
                    risk_level      ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
                    analyzed_at     DATETIME      NOT NULL,
                    price           DECIMAL(12,2),
                    `change`        DECIMAL(12,2),
                    change_percent  DECIMAL(8,4),
                    UNIQUE KEY uk_date_time_symbol (date, scrape_time, symbol),
                    INDEX idx_date (date)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)

            # Add scrape_time column if it doesn't exist
            try:
                cur.execute("ALTER TABLE bbs_sentiment ADD COLUMN scrape_time TIME NOT NULL DEFAULT '08:00:00' AFTER date")
                log.info("Added scrape_time column to bbs_sentiment")
            except pymysql.err.OperationalError as exc:
                if exc.args[0] == 1060:  # Duplicate column name
                    pass
                else:
                    raise
            
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
            
            # Drop old unique key and add new one with scrape_time
            try:
                cur.execute("ALTER TABLE bbs_sentiment DROP INDEX uq_symbol_date")
                log.info("Dropped old unique key uq_symbol_date")
            except pymysql.err.OperationalError as exc:
                if exc.args[0] == 1091:  # Can't DROP index that doesn't exist
                    pass
                else:
                    raise
            
            try:
                cur.execute("ALTER TABLE bbs_sentiment ADD UNIQUE KEY uk_date_time_symbol (date, scrape_time, symbol)")
                log.info("Added new unique key uk_date_time_symbol")
            except pymysql.err.OperationalError as exc:
                if exc.args[0] == 1061:  # Duplicate key name
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

def create_client() -> anthropic.Anthropic:
    """Build the Claude client once per run (raises FatalAnalysisError if no key)."""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise FatalAnalysisError('ANTHROPIC_API_KEY not found in environment')
    return anthropic.Anthropic(
        api_key=api_key,
        timeout=CLAUDE_TIMEOUT,
        max_retries=CLAUDE_MAX_RETRIES,
    )


def _parse_result(text: str) -> dict:
    """Extract the JSON object from the model's text answer."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise SentimentAnalysisError(f'response is not valid JSON: {text[:200]!r}')


def analyze_posts_sentiment(client: anthropic.Anthropic, symbol: str, posts_list: list[str]) -> dict:
    """
    Analyze a list of BBS posts for a stock symbol using Claude.

    Args:
        client: Claude client from create_client()
        symbol: Stock symbol, e.g. '6758.T'
        posts_list: List of post text strings (up to 100)

    Returns:
        Dict with:
          sentiment_score: float (-1.0 to +1.0)
          key_topics: list[str]
          risk_level: 'low' | 'medium' | 'high'

    Raises:
        SentimentAnalysisError: this symbol could not be analyzed (nothing is saved
            for it, so the UI shows "not analyzed" rather than a fake neutral 0.0).
        FatalAnalysisError: the request can never succeed (bad key, unknown model).
    """
    if not posts_list:
        raise SentimentAnalysisError('no posts to analyze')

    posts_text = '\n---\n'.join(posts_list[:MAX_POSTS_PER_SYMBOL])
    if len(posts_text) > MAX_POSTS_CHARS:
        posts_text = posts_text[:MAX_POSTS_CHARS] + '\n...(truncated)'

    prompt = f"""あなたは日本株市場のアナリストです。Yahoo Finance Japanの株式掲示板の投稿を分析してください。

対象銘柄: {symbol}

掲示板の投稿:
{posts_text}

以下のフィールドを含むJSONオブジェクトで回答してください:
{{
  "sentiment_score": <-1.0から1.0の間の数値>,
  "key_topics": <3〜7個のキーワードの配列（日本語で）>,
  "risk_level": "<low|medium|high>",
  "reasoning": "<1〜2文の要約（日本語で）>"
}}

スコアリング基準:
- sentiment_score: -1.0 = 強い弱気/ネガティブ, 0.0 = 中立/混在, +1.0 = 強い強気/ポジティブ
- key_topics: 主なテーマを特定（例: "決算好調", "テクニカル上昇", "配当減配", "インサイダー売却", "地政学リスク"など、必ず日本語で）
- risk_level: low = 冷静/事実的な投稿が多い, medium = 投機的/懸念が一部, high = パニック/論争/リスク警告

JSON形式のみで回答し、他の文章は含めないでください。"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            # Room for adaptive thinking (on by default for Claude 5.x) plus the JSON answer
            max_tokens=4096,
            messages=[{'role': 'user', 'content': prompt}],
            **_MODEL_EXTRAS.get(CLAUDE_MODEL, {}),
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise FatalAnalysisError(f'Claude API rejected the credentials: {exc}') from exc
    except anthropic.NotFoundError as exc:
        raise FatalAnalysisError(f'Claude model {CLAUDE_MODEL!r} not found (retired?): {exc}') from exc
    except anthropic.APIStatusError as exc:
        # Retryable statuses were already retried by the SDK
        raise SentimentAnalysisError(f'Claude API error {exc.status_code}: {exc}') from exc
    except anthropic.APIConnectionError as exc:  # includes timeouts
        raise SentimentAnalysisError(f'Claude API connection error: {exc}') from exc

    if response.stop_reason in ('refusal', 'max_tokens'):
        raise SentimentAnalysisError(f'response stopped early (stop_reason={response.stop_reason})')

    text = next((b.text for b in response.content if b.type == 'text'), '')
    result = _parse_result(text)

    try:
        sentiment_score = float(result['sentiment_score'])
    except (KeyError, TypeError, ValueError) as exc:
        raise SentimentAnalysisError(f'missing or invalid sentiment_score: {result!r}'[:300]) from exc
    if not math.isfinite(sentiment_score):
        raise SentimentAnalysisError(f'non-finite sentiment_score: {sentiment_score}')
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
        key_topics[:3], str(result.get('reasoning') or '')[:80]
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

def _fetch_symbols_with_posts(conn: pymysql.Connection, target_date: date, scrape_time: str) -> list[dict]:
    """
    Return one dict per ranked symbol: symbol, price, change, change_percent, posts.

    Posts are read row by row from bbs_posts (not via GROUP_CONCAT, which MySQL
    silently truncates at group_concat_max_len = 1024 bytes by default, i.e. only
    a few Japanese posts). Exact duplicate posts (from re-runs of the scraper)
    are dropped, keeping the original order, and capped at MAX_POSTS_PER_SYMBOL.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.symbol, r.price, r.`change`, r.change_percent
            FROM bbs_rankings r
            WHERE r.date = %s AND r.scrape_time = %s AND r.status != 'dropped'
            ORDER BY r.symbol, r.id
            """,
            (target_date, scrape_time)
        )
        rankings = cur.fetchall()
        if not rankings:
            return []

        ranking_ids = [r['id'] for r in rankings]
        placeholders = ', '.join(['%s'] * len(ranking_ids))
        cur.execute(
            f"""
            SELECT ranking_id, post_content
            FROM bbs_posts
            WHERE ranking_id IN ({placeholders})
            ORDER BY ranking_id, id
            """,
            ranking_ids
        )
        post_rows = cur.fetchall()

    symbol_of = {r['id']: r['symbol'] for r in rankings}
    symbols: dict[str, dict] = {}
    for r in rankings:
        symbols.setdefault(r['symbol'], {
            'symbol': r['symbol'],
            'price': r['price'],
            'change': r['change'],
            'change_percent': r['change_percent'],
            'posts': [],
            '_seen': set(),
        })

    for row in post_rows:
        entry = symbols[symbol_of[row['ranking_id']]]
        post = (row['post_content'] or '').strip()
        if not post or post in entry['_seen'] or len(entry['posts']) >= MAX_POSTS_PER_SYMBOL:
            continue
        entry['_seen'].add(post)
        entry['posts'].append(post)

    for entry in symbols.values():
        del entry['_seen']
    return list(symbols.values())


def _scrape_time_for_now() -> str:
    """Scrape slot (08:00 or 20:00) matching the scraper's logic in bbs_scraper.save_to_mysql."""
    current_hour = datetime.now().hour
    if 18 <= current_hour <= 23 or 0 <= current_hour < 2:
        return '20:00:00'
    # 06:00-14:00, and the default for manual runs
    return '08:00:00'


def analyze_bbs_ranking(date_str: str, scrape_time: Optional[str] = None) -> dict:
    """
    Read bbs_posts from MySQL, analyze each symbol's posts via Claude,
    and save results to bbs_sentiment table.

    A failure on one symbol is logged and skipped; the remaining symbols are
    still analyzed. Nothing is written for a failed symbol.

    Args:
        date_str: Date string in 'YYYY-MM-DD' format
        scrape_time: 'HH:MM:SS'; defaults to the slot for the current hour

    Returns:
        Counts: {'total', 'analyzed', 'failed', 'skipped'}

    Raises:
        FatalAnalysisError: on configuration errors or too many consecutive failures.
    """
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    if scrape_time is None:
        scrape_time = _scrape_time_for_now()

    log.info(f"Analyzing sentiment for scrape_time={scrape_time}")

    client = create_client()
    setup_sentiment_table()

    stats = {'total': 0, 'analyzed': 0, 'failed': 0, 'skipped': 0}
    conn = get_connection()
    try:
        rows = _fetch_symbols_with_posts(conn, target_date, scrape_time)

        if not rows:
            log.warning("No ranking data in DB for %s %s. Run bbs_scraper.py first.", date_str, scrape_time)
            return stats

        stats['total'] = len(rows)
        log.info("Analyzing sentiment for %d symbols on %s", len(rows), date_str)

        analyzed_at = datetime.now()
        consecutive_failures = 0

        for i, row in enumerate(rows, 1):
            symbol = row['symbol']
            posts_list = row['posts']

            if not posts_list:
                log.warning("[%d/%d] %s: no posts stored, skipping", i, len(rows), symbol)
                stats['skipped'] += 1
                continue

            log.info("[%d/%d] Analyzing %s (%d posts)", i, len(rows), symbol, len(posts_list))

            try:
                result = analyze_posts_sentiment(client, symbol, posts_list)
            except SentimentAnalysisError as exc:
                stats['failed'] += 1
                consecutive_failures += 1
                log.error("[%d/%d] %s: analysis failed, skipping: %s", i, len(rows), symbol, exc)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    raise FatalAnalysisError(
                        f'{consecutive_failures} consecutive failures, aborting '
                        f'(last: {symbol}: {exc})'
                    ) from exc
                continue
            consecutive_failures = 0

            # Upsert into bbs_sentiment (replace if already exists for this symbol+date)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bbs_sentiment
                        (symbol, date, scrape_time, sentiment_score, key_topics, risk_level, analyzed_at,
                         price, `change`, change_percent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        scrape_time,
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
            stats['analyzed'] += 1

    finally:
        conn.close()

    log.info(
        "=== Sentiment analysis complete for %s %s: analyzed=%d failed=%d skipped=%d (of %d) ===",
        date_str, scrape_time, stats['analyzed'], stats['failed'], stats['skipped'], stats['total'],
    )

    # Show results
    _print_results(target_date, scrape_time)
    return stats


def _print_results(target_date: date, scrape_time: str = '08:00:00') -> None:
    """Print a summary of sentiment results from DB."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, sentiment_score, key_topics, risk_level, analyzed_at
                FROM bbs_sentiment
                WHERE date = %s AND scrape_time = %s
                ORDER BY sentiment_score DESC
                """,
                (target_date, scrape_time)
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

def main(argv: list[str]) -> int:
    """
    Run sentiment analysis. Usage:
      python3 sentiment_analyzer.py                      # today, slot for current hour
      python3 sentiment_analyzer.py 2026-10-01 08:00:00  # re-run a specific slot

    Exit code: 0 = all symbols analyzed, 1 = some symbols failed or run aborted.
    """
    log.info("=== Stage 2: LLM Sentiment Analysis (model=%s) ===", CLAUDE_MODEL)
    date_str = argv[1] if len(argv) > 1 else date.today().isoformat()
    scrape_time = argv[2] if len(argv) > 2 else None
    log.info(f"Analyzing BBS data for {date_str}")
    try:
        stats = analyze_bbs_ranking(date_str, scrape_time)
    except FatalAnalysisError as exc:
        log.error("Sentiment analysis aborted: %s", exc)
        return 1
    return 1 if stats['failed'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
