from flask import Flask, jsonify, request
from scraper import get_stock_data

app = Flask(__name__)


@app.route('/stock/<symbol>', methods=['GET'])
def stock(symbol):
    data = get_stock_data(symbol.upper())
    if data is None:
        return jsonify({'error': f'Could not fetch data for {symbol}'}), 404
    return jsonify(data)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True)
