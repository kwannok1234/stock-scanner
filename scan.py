import yfinance as yf
import requests
from datetime import datetime
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

WATCHLIST = [
    "TSLA","NVDA","PLTR","GOOG","AVGO","NFLX","TEM","MU","VRT","MRVL",
    "ASX","ANET","ONDS","NVT","AMKR","CLS","FN","APH","CRDO","COHR",
    "AAOI","MOD","AXTI","C","GEV","SNDK","INTC","AMD","MSFT","AAPL",
    "GOOGL","AMZN","META","QCOM","LITE","TSM","ARM","NOW","WMT","INTU",
    "CSCO","IBM","LLY","AMAT","XOM","V","ORCL","WDC","STX","ADI",
    "LRCX","COST","UNH","CRWD","GLW","CRM","JPM","CAT","BRK-B","GS",
    "TXN","PANW","MSTR","CVX","NEE","DELL","BAC","JNJ","HD","APP",
    "KLAC","MA","COIN","HOOD","BABA","GE","BA","AKAM","TGT","ADBE",
    "TER","BKNG","UBER","D","PEP","AZO","KO","DDOG","HON","MCD",
    "CIEN","ON","ABBV","TJX","TMO","MRK","WFC","NXPI","MS","SMCI",
    "PG","SATS","RCL","REGN","ETN","MPWR","ISRG","VZ","F","PWR",
    "LIN","SYK"
]

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Telegram error: {e}")

def get_market_status():
    try:
        qqq = yf.download("QQQ", period="1y", interval="1d", progress=False)
        if len(qqq) < 200:
            return "unknown", {}
        close = qqq["Close"].squeeze()
        ma50  = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        p    = float(close.iloc[-1])
        m50  = float(ma50.iloc[-1])
        m200 = float(ma200.iloc[-1])
        if p > m50 and p > m200:
            status = "green"
        elif p > m50 and p <= m200:
            status = "yellow"
        elif p <= m50 and p > m200:
            status = "orange"
        else:
            status = "red"
        return status, {"price": round(p,2), "ma50": round(m50,2), "ma200": round(m200,2)}
    except Exception as e:
        print(f"Market status error: {e}")
        return "unknown", {}

def check_sell_signals(holdings_file="holdings.txt"):
    sells = []
    if not os.path.exists(holdings_file):
        return sells
    with open(holdings_file) as f:
        for line in f:
            line = line.strip()
            if not line or "," not in line:
                continue
            parts = line.split(",")
            ticker = parts[0].strip()
            stop   = float(parts[1].strip())
            try:
                df   = yf.download(ticker, period="10d", interval="1d", progress=False)
                curr = float(df["Close"].iloc[-1].squeeze())
                if curr < stop:
                    sells.append((ticker, curr, stop))
            except:
                pass
    return sells

def check_buy_signal(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 200:
            return False, {}
        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze()
        ma50   = close.rolling(50).mean()
        ma150  = close.rolling(150).mean()
        ma200  = close.rolling(200).mean()
        vol50  = volume.rolling(50).mean()

        stage2 = (float(close.iloc[-1]) > float(ma50.iloc[-1]) and
                  float(ma50.iloc[-1])  > float(ma150.iloc[-1]) and
                  float(ma150.iloc[-1]) > float(ma200.iloc[-1]))
        if not stage2:
            return False, {}

        if not (float(ma200.iloc[-1]) > float(ma200.iloc[-30])):
            return False, {}

        vol_ratio = float(volume.iloc[-1]) / float(vol50.iloc[-1])
        if vol_ratio < 1.4:
            return False, {}

        pivot = float(df["High"].iloc[-21:-1].max().squeeze())
        if float(close.iloc[-1]) <= pivot:
            return False, {}

        highs = df["High"].squeeze()
        lows  = df["Low"].squeeze()
        recent_range = float(highs.iloc[-60:-1].max()) - float(lows.iloc[-60:-1].min())
        tight_range  = float(highs.iloc[-10:-1].max()) - float(lows.iloc[-10:-1].min())
        vcp_ok = tight_range < recent_range * 0.5

        stop_loss = round(float(close.iloc[-1]) * 0.93, 2)
        return True, {
            "price":     round(float(close.iloc[-1]), 2),
            "vol_ratio": round(vol_ratio, 2),
            "pivot":     round(pivot, 2),
            "stop":      stop_loss,
            "vcp":       vcp_ok
        }
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return False, {}

def run_scan():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"Scan started {today}")

    market_status, mkt = get_market_status()
    status_map = {
        "green":   ("\U0001f7e2", "Market OK - Normal trading"),
        "yellow":  ("\U0001f7e1", "Market mixed - Small positions only"),
        "orange":  ("\U0001f7e0", "Market weak - Stop new positions"),
        "red":     ("\U0001f534", "Bear market - Full defence"),
        "unknown": ("âšª",     "Market status unknown"),
    }
    mkt_emoji, mkt_text = status_map.get(market_status, ("âšª", "Unknown"))

    # Check sell/stop-loss signals first
    sell_signals = check_sell_signals()
    for ticker, curr, stop in sell_signals:
        msg = (f"\U0001f534 STOP-LOSS ALERT\n"
               f"Stock: {ticker}\n"
               f"Price: ${curr}\n"
               f"Stop: ${stop}\n"
               f"Action: Exit position now")
        send_telegram(msg)

    # If market is bad, skip buy scan
    if market_status in ["orange", "red"]:
        msg = (f"\U0001f4ca Daily Scan {today}\n\n"
               f"{mkt_emoji} {mkt_text}\n"
               f"QQQ: ${mkt.get('price','-')} | 50MA: ${mkt.get('ma50','-')} | 200MA: ${mkt.get('ma200','-')}\n\n"
               f"Market unfavourable - no new positions")
        send_telegram(msg)
        return

    # Scan for buy signals
    buy_results = []
    for ticker in WATCHLIST:
        signal, info = check_buy_signal(ticker)
        if signal:
            buy_results.append((ticker, info))
        print(f"  {ticker}: {'BUY' if signal else '-'}")

    if buy_results:
        msg = f"\U0001f4ca Daily Scan {today}\n\n"
        msg += f"{mkt_emoji} {mkt_text}\n"
        msg += f"QQQ: ${mkt.get('price','-')} | 50MA: ${mkt.get('ma50','-')} | 200MA: ${mkt.get('ma200','-')}\n\n"
        msg += f"âœ… Buy signals today: {len(buy_results)}\n\n"
        for ticker, info in buy_results:
            vcp_tag = "[VCP]" if info.get("vcp") else ""
            msg += (f"<b>{ticker}</b> ${info['price']} {vcp_tag}\n"
                    f"  Pivot: ${info['pivot']} | Vol: x{info['vol_ratio']}\n"
                    f"  Stop-loss: ${info['stop']}\n\n")
        send_telegram(msg)
    else:
        msg = (f"\U0001f4ca Daily Scan {today}\n\n"
               f"{mkt_emoji} {mkt_text}\n"
               f"No buy signals today")
        send_telegram(msg)

if __name__ == "__main__":
    run_scan()
