# server.py
from flask import Flask, request, jsonify
import MetaTrader5 as mt5
import os, hmac, hashlib, logging

# Read config from env
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '').encode()
MT5_LOGIN      = int(os.getenv('MT5_LOGIN', '0'))
MT5_PASSWORD   = os.getenv('MT5_PASSWORD', '')
MT5_SERVER     = os.getenv('MT5_SERVER', '')

# Initialize MT5
print(MT5_SERVER)

if not mt5.initialize(server=MT5_SERVER, login=MT5_LOGIN, password=MT5_PASSWORD):
    raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def verify_signature(body: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        return True  # skip if no secret set
    mac = hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    sig = request.headers.get('X-Signature', '')
    if not verify_signature(request.data, sig):
        return jsonify({'error': 'invalid signature'}), 401

    data   = request.get_json() or {}
    action = data.get('action', '').upper()
    symbol = data.get('symbol', '')
    qty    = float(data.get('qty', 0))
    price  = float(data.get('price', 0))

    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    req = {
        'action':      mt5.TRADE_ACTION_DEAL,
        'symbol':      symbol,
        'volume':      qty,
        'type':        order_type,
        'price':       price,
        'deviation':   20,
        'magic':       123456,
        'comment':     'TV→MT5 auto',
        'type_time':   mt5.ORDER_TIME_GTC,
        'type_filling':mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(req)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed: {result}")
        return jsonify({'error': result._asdict()}), 500

    logging.info(f"Order successful: {result}")
    return jsonify({'status': 'success', 'order': result._asdict()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
