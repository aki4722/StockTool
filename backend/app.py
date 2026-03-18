from flask import Flask, jsonify, request
from scraper import get_stock_data

app = Flask(__name__)


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
