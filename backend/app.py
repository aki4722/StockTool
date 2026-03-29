import json
import os
from datetime import date, timedelta

import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request
from flask_cors import CORS

from scraper import get_stock_data

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


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
    scrape_time = request.args.get('scrape_time', '08:00:00')  # Default to 08:00
    
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
                    r.scrape_time,
                    s.sentiment_score,
                    s.key_topics,
                    s.risk_level
                FROM bbs_rankings r
                LEFT JOIN bbs_sentiment s
                    ON s.symbol = r.symbol AND s.date = r.date AND s.scrape_time = r.scrape_time
                WHERE r.date = %s AND r.scrape_time = %s
                ORDER BY r.post_count DESC
                """,
                (target, scrape_time)
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


@app.route('/api/bbs-ranking-csv', methods=['GET'])
def bbs_ranking_csv():
    """
    Export BBS ranking as CSV with optional filters.
    
    Query params:
      date: YYYY-MM-DD (default: today)
      scrape_time: HH:MM:SS (default: 08:00:00)
      sentiment_min: float (default: -1.0)
      sentiment_max: float (default: 1.0)
      risk_level: comma-separated (low,medium,high) (default: all)
      status: comma-separated (new,existing,dropped) (default: all)
    
    Output format: symbol,company_name,TKY,,,,,,
    """
    date_str = request.args.get('date', str(date.today()))
    scrape_time = request.args.get('scrape_time', '08:00:00')
    
    # Parse filter parameters
    sentiment_min = float(request.args.get('sentiment_min', -1.0))
    sentiment_max = float(request.args.get('sentiment_max', 1.0))
    
    risk_levels = request.args.get('risk_level', '').strip()
    if risk_levels:
        risk_levels = [r.strip() for r in risk_levels.split(',') if r.strip()]
    else:
        risk_levels = ['low', 'medium', 'high']
    
    statuses = request.args.get('status', '').strip()
    if statuses:
        statuses = [s.strip() for s in statuses.split(',') if s.strip()]
    else:
        statuses = ['new', 'existing', 'dropped']
    
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        return 'Invalid date format', 400
    
    try:
        conn = _bbs_connection()
    except Exception as exc:
        return f'Database error: {exc}', 503
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    r.symbol,
                    r.company_name,
                    r.post_count,
                    r.status,
                    s.sentiment_score,
                    s.risk_level
                FROM bbs_rankings r
                LEFT JOIN bbs_sentiment s
                    ON s.symbol = r.symbol AND s.date = r.date AND s.scrape_time = r.scrape_time
                WHERE r.date = %s AND r.scrape_time = %s
                ORDER BY r.post_count DESC
                """,
                (target, scrape_time)
            )
            rows = cur.fetchall()
        
        # Apply filters
        filtered = []
        for row in rows:
            # Sentiment filter
            sentiment = row['sentiment_score']
            if sentiment is not None:
                if sentiment < sentiment_min or sentiment > sentiment_max:
                    continue
            
            # Risk level filter
            if row['risk_level'] and row['risk_level'] not in risk_levels:
                continue
            
            # Status filter
            if row['status'] not in statuses:
                continue
            
            filtered.append(row)
        
        # Generate CSV
        import io
        output = io.StringIO()
        for row in filtered:
            symbol = row['symbol'].replace('.T', '')  # Remove .T suffix
            company = row['company_name'] or ''
            output.write(f"{symbol},{company},TKY,,,,,,\n")
        
        csv_data = output.getvalue()
        
        # Return as downloadable file
        from flask import Response
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=bbs_ranking_{date_str}_{scrape_time.replace(":", "")}.csv'
            }
        )
    except Exception as exc:
        return f'Error: {exc}', 500
    finally:
        conn.close()


# ===== MARGIN TRACKING ENDPOINTS =====

@app.route('/api/margin-symbols', methods=['GET'])
def margin_symbols_get():
    """Get list of tracked margin symbols with company names."""
    try:
        conn = _bbs_connection()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT symbol, company_name FROM margin_tracking ORDER BY symbol')
            rows = cur.fetchall()
        symbols = [
            {
                'symbol': row['symbol'],
                'company_name': row['company_name'] or row['symbol']
            }
            for row in rows
        ]
        return jsonify(symbols)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@app.route('/api/margin-symbols', methods=['POST'])
def margin_symbols_post():
    """Add a new symbol to margin tracking."""
    data = request.get_json()
    symbol = data.get('symbol', '').strip().upper()
    
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    
    try:
        conn = _bbs_connection()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    
    try:
        with conn.cursor() as cur:
            # Check if already tracked
            cur.execute('SELECT id FROM margin_tracking WHERE symbol = %s', (symbol,))
            if cur.fetchone():
                return jsonify({'error': f'{symbol} already tracked'}), 409
            
            # Insert new symbol
            cur.execute(
                'INSERT INTO margin_tracking (symbol, added_date) VALUES (%s, %s)',
                (symbol, date.today())
            )
            conn.commit()
        return jsonify({'symbol': symbol, 'status': 'added'}), 201
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@app.route('/api/margin-symbols/<symbol>', methods=['DELETE'])
def margin_symbols_delete(symbol):
    """Remove symbol from margin tracking."""
    symbol = symbol.strip().upper()
    
    try:
        conn = _bbs_connection()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM margin_tracking WHERE symbol = %s', (symbol,))
            conn.commit()
        return jsonify({'symbol': symbol, 'status': 'removed'})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@app.route('/api/margin-data', methods=['GET'])
def margin_data():
    """Get margin position data for all tracked symbols."""
    try:
        conn = _bbs_connection()
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    
    try:
        with conn.cursor() as cur:
            # Get all symbols
            cur.execute('SELECT symbol FROM margin_tracking ORDER BY symbol')
            symbols = [row['symbol'] for row in cur.fetchall()]
            
            result = {}
            for symbol in symbols:
                cur.execute("""
                    SELECT 
                        date, symbol, long_position, short_position, 
                        margin_ratio, weekly_change_long, weekly_change_short
                    FROM margin_positions
                    WHERE symbol = %s
                    ORDER BY date DESC
                    LIMIT 60
                """, (symbol,))
                rows = cur.fetchall()
                
                result[symbol] = [
                    {
                        'date': str(row['date']),
                        'symbol': row['symbol'],
                        'long_position': row['long_position'],
                        'short_position': row['short_position'],
                        'margin_ratio': float(row['margin_ratio']) if row['margin_ratio'] else None,
                        'weekly_change_long': row['weekly_change_long'],
                        'weekly_change_short': row['weekly_change_short'],
                    }
                    for row in rows
                ]
            
            return jsonify(result)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
