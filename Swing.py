import os
import time
import pandas as pd
import pyotp
from SmartApi import SmartConnect

# --- CONFIGURATION ---
API_KEY = os.getenv('ANGEL_API_KEY')
CLIENT_ID = os.getenv('ANGEL_CLIENT_ID')
PWD = os.getenv('ANGEL_PASSWORD')
TOTP_SECRET = os.getenv('ANGEL_TOTP_SECRET')

CAPITAL_PER_STOCK = 5000  # Your cash
TOTAL_POWER = CAPITAL_PER_STOCK * 4  # 4x MTF Leverage
STOP_LOSS_PCT = 0.05
RS_PERIOD = 55
WEEKLY_PERIOD = 21

# --- SECTOR DATA ---
SECTOR_MAP = {
    "NIFTY BANK": ["HDFCBANK", "ICICIBANK", "SBIN", "FEDERALBNK", "AXISBANK"],
    "NIFTY IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "NIFTY PHARMA": ["SUNPHARMA", "CIPLA", "DRREDDY", "LUPIN"],
    # Add more sectors as needed...
}

INDEX_TOKENS = {
    "NIFTY 50": "99926000", "NIFTY BANK": "99926009", 
    "NIFTY IT": "99926017", "NIFTY PHARMA": "99926037"
}

# --- FUNCTIONS ---
def get_rsi(df, window=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
    return 100 - (100 / (1 + (gain/loss)))

def get_rs_score(stock_df, nifty_df, period):
    s_ret = (stock_df['close'].iloc[-1] / stock_df['close'].iloc[-period]) - 1
    n_ret = (nifty_df['close'].iloc[-1] / nifty_df['close'].iloc[-period]) - 1
    return s_ret - n_ret

def login():
    obj = SmartConnect(api_key=API_KEY)
    token = pyotp.TOTP(TOTP_SECRET).now()
    obj.generateSession(CLIENT_ID, PWD, token)
    return obj

def run_trading_cycle():
    api = login()
    nifty_daily = pd.DataFrame(api.getCandleData(INDEX_TOKENS["NIFTY 50"], "ONE_DAY"))
    
    for sector, stocks in SECTOR_MAP.items():
        # Sector Tailwind Check
        sec_df = pd.DataFrame(api.getCandleData(INDEX_TOKENS[sector], "ONE_DAY"))
        if get_rs_score(sec_df, nifty_daily, RS_PERIOD) <= 0:
            continue  # Skip weak sectors

        for symbol in stocks:
            try:
                # Fetch Token and Daily Data
                df = pd.DataFrame(api.getCandleData(symbol_token_map[symbol], "ONE_DAY"))
                rs_55 = get_rs_score(df, nifty_daily, RS_PERIOD)
                rsi = get_rsi(df).iloc[-1]
                
                # ENTRY LOGIC
                if rs_55 > 0 and rsi > 50:
                    qty = int(TOTAL_POWER / df['close'].iloc[-1])
                    api.placeOrder({
                        "variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": symbol_token_map[symbol],
                        "transactiontype": "BUY", "exchange": "NSE", "ordertype": "MARKET",
                        "producttype": "MARGIN", "duration": "DAY", "quantity": qty
                    })
                    print(f"MTF Buy Order placed for {symbol}")
                    time.sleep(1) # Prevent Rate Limits
            except Exception as e:
                print(f"Error scanning {symbol}: {e}")

if __name__ == "__main__":
    run_trading_cycle()

