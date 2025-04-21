import telebot
import MetaTrader5 as mt5
import re
import logging

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
MT5_ACCOUNT = 12345678
MT5_PASSWORD = 'your_mt5_password'
MT5_SERVER = 'YourBroker-Server'
AUTHORIZED_USER_IDS = [123456789]  # Replace with your Telegram user ID(s)
TRADE_VOLUME = 0.1  # default lot size
DEVIATION = 20

# --- LOGGER SETUP ---
logging.basicConfig(filename='trade_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- INIT TELEGRAM BOT ---
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- MT5 CONNECTION ---
def initialize_mt5():
    if not mt5.initialize():
        logging.error(f"MT5 Initialize failed: {mt5.last_error()}")
        return False
    if not mt5.login(MT5_ACCOUNT, password=MT5_PASSWORD, server=MT5_SERVER):
        logging.error(f"MT5 Login failed: {mt5.last_error()}")
        return False
    return True

# --- TRADE EXECUTION ---
def open_trade(action, symbol, sl=None, tp=None):
    symbol = symbol.upper()

    if not mt5.symbol_select(symbol, True):
        logging.error(f"Symbol not found or not available: {symbol}")
        return f"❌ Symbol {symbol} not found or not available."

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logging.error(f"Failed to get tick data for {symbol}")
        return f"❌ Failed to get tick data for {symbol}."

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
    else:
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
    if message.from_user.id not in AUTHORIZED_USER_IDS:
        bot.reply_to(message, "⛔ Unauthorized user.")
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id}")
        return

    parsed = parse_trade_signal(message.text)
    if not parsed:
        bot.reply_to(message, "⚠️ Invalid format. Use: BUY|SELL SYMBOL [SL=...] [TP=...]")
        return

    if not initialize_mt5():
        bot.reply_to(message, "❌ Failed to connect to MetaTrader 5.")
        return

    result_msg = open_trade(
        parsed["action"],
        parsed["symbol"],
        parsed.get("sl"),
        parsed.get("tp")
    )

    bot.reply_to(message, result_msg)

# --- START BOT ---
print("📡 Telegram MT5 Trade Bot is running...")
bot.polling()
