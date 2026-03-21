import json
import os
from datetime import date, timedelta

import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request

from scraper import get_stock_data

app = Flask(__name__)


def _db_config():
    return {
        'host': os.environ.get('MYSQL_HOST', 'localhost'),
        'port': int(os.environ.get('MYSQL_PORT', 3306)),
        'user': os.environ.get('MYSQL_USER', 'root'),
        'password': os.environ.get('MYSQL_PASSWORD', ''),
        'database': os.environ.get('MYSQL_DATABASE', 'stocktool_bbs'),
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
    }


def _bbs_connection():
    return pymysql.connect(**_db_config())


@app.route('/stock/<symbol>', methods=['GET'])
def stock(symbol):
    data = get_stock_data(symbol.upper())
    if data is None:
        return jsonify({'error': f'Could not fetch data for {symbol}'}), 404
    return jsonify(data)


@app.route('/stocks', methods=['GET'])
def stocks():
    raw = request.args.get('symbols', '')
    symbols = [s.strip().upper() for s in raw.split(',') if s.strip()]
    if not symbols:
        return jsonify({'error': 'No symbols provided'}), 400
    results = []
    for sym in symbols:
        data = get_stock_data(sym)
        if data is None:
            results.append({'symbol': sym, 'error': f'Could not fetch data for {sym}'})
        else:
            results.append(data)
    return jsonify(results)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/bbs-dates', methods=['GET'])
def bbs_dates():
    try:
        conn = _bbs_connection()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    try:
        with conn.cursor() as cur:
            cutoff = date.today() - timedelta(days=30)
            cur.execute(
                "SELECT DISTINCT date FROM bbs_rankings "
                "WHERE date >= %s ORDER BY date DESC",
                (cutoff,)
            )
            rows = cur.fetchall()
        dates = [str(r['date']) for r in rows]
        return jsonify(dates)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@app.route('/api/bbs-ranking', methods=['GET'])
def bbs_ranking():
    date_str = request.args.get('date', str(date.today()))
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format, use YYYY-MM-DD'}), 400

    try:
        conn = _bbs_connection()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    r.symbol,
                    r.company_name,
                    r.post_count,
                    r.price,
                    r.`change`,
                    r.change_percent,
                    r.status,
                    s.sentiment_score,
                    s.key_topics,
                    s.risk_level
                FROM bbs_rankings r
                LEFT JOIN bbs_sentiment s
                    ON s.symbol = r.symbol AND s.date = r.date
                WHERE r.date = %s
                ORDER BY r.post_count DESC
                """,
                (target,)
            )
            rows = cur.fetchall()

        results = []
        for row in rows:
            key_topics = row['key_topics']
            if key_topics and isinstance(key_topics, str):
                try:
                    key_topics = json.loads(key_topics)
                except json.JSONDecodeError:
                    key_topics = []
            elif key_topics is None:
                key_topics = []

            results.append({
                'symbol':          row['symbol'],
                'company_name':    row['company_name'] or '',
                'post_count':      row['post_count'],
                'sentiment_score': float(row['sentiment_score']) if row['sentiment_score'] is not None else None,
                'key_topics':      key_topics,
                'risk_level':      row['risk_level'],
                'price':           float(row['price']) if row['price'] is not None else None,
                'change':          float(row['change']) if row['change'] is not None else None,
                'change_percent':  float(row['change_percent']) if row['change_percent'] is not None else None,
                'status':          row['status'],
            })
        return jsonify(results)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
