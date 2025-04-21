import telebot
import MetaTrader5 as mt5
import re
import logging
import os
import sys

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
MT5_ACCOUNT = int(os.getenv('MT5_ACCOUNT', '0'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
MT5_SERVER = os.getenv('MT5_SERVER', '')
# Optional: specify terminal path via env
MT5_TERMINAL_PATH = os.getenv('MT5_TERMINAL_PATH', r"C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe")

AUTHORIZED_USER_IDS = [6154595002]  # Replace with your Telegram user ID(s)
TRADE_VOLUME = float(os.getenv('TRADE_VOLUME', '0.1'))  # default lot size
DEVIATION = int(os.getenv('DEVIATION', '20'))

# --- LOGGER SETUP ---
logging.basicConfig(
    filename='trade_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- INIT TELEGRAM BOT ---
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- MT5 CONNECTION ---
def initialize_mt5():
    """
    Initialize and login to MT5. Returns (True, '') on success, (False, error_message) on failure.
    """
    ok = mt5.initialize(
        path=MT5_TERMINAL_PATH,
        login=MT5_ACCOUNT,
        password=MT5_PASSWORD,
        server=MT5_SERVER
    )
    if not ok:
        err = mt5.last_error()
        logging.error(f"MT5 initialize/login failed: {err}")
        return False, f"Initialize/login failed: {err}"
    logging.info("MT5 initialized and logged in successfully.")
    return True, ''

# --- TRADE EXECUTION ---
def open_trade(action, symbol, sl=None, tp=None):
    symbol = symbol.upper()

    if not mt5.symbol_select(symbol, True):
        err = mt5.last_error()
        logging.error(f"Symbol select failed for {symbol}: {err}")
        return f"❌ Symbol select failed: {err}"

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        err = mt5.last_error()
        logging.error(f"Tick fetch failed for {symbol}: {err}")
        return f"❌ Failed to fetch tick data: {err}"

    price = tick.ask if action == 'BUY' else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL

    sl_price = float(sl) if sl else None
    tp_price = float(tp) if tp else None

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": TRADE_VOLUME,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": DEVIATION,
        "magic": 10032025,
        "comment": "Trade via Telegram Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed: {result.retcode} | {result.comment}")
        return f"❌ Order failed: {result.comment} (Code {result.retcode})"

    logging.info(f"Trade executed: {action} {symbol} SL={sl} TP={tp}")
    return f"✅ Trade executed: {action} {symbol}\nSL: {sl or 'None'} | TP: {tp or 'None'}"

# --- PARSE MESSAGES ---
def parse_trade_signal(text):
    match = re.match(r'(BUY|SELL)\s+([A-Z]+)(?:\s+SL=([\d.]+))?(?:\s+TP=([\d.]+))?', text.upper())
    if match:
        return {
            "action": match.group(1),
            "symbol": match.group(2),
            "sl": match.group(3),
            "tp": match.group(4)
        }
    return None

# --- TELEGRAM HANDLER ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    if user_id not in AUTHORIZED_USER_IDS:
        bot.reply_to(message, "⛔ Unauthorized user.")
        logging.warning(f"Unauthorized access attempt by user {user_id}")
        return

    parsed = parse_trade_signal(message.text)
    if not parsed:
        bot.reply_to(message, "⚠️ Invalid format. Use: BUY|SELL SYMBOL [SL=...] [TP=...]")
        return

    success, err_msg = initialize_mt5()
    if not success:
        bot.reply_to(message, f"❌ Failed to connect to MetaTrader 5:\n{err_msg}")
        return

    result_msg = open_trade(
        parsed["action"],
        parsed["symbol"],
        parsed.get("sl"),
        parsed.get("tp")
    )
    bot.reply_to(message, result_msg)

# --- START BOT ---
if __name__ == '__main__':
    print("📡 Telegram MT5 Trade Bot is running...")
    try:
        bot.polling()
    except Exception as e:
        logging.exception(f"Bot polling failed: {e}")
        sys.exit(1)
