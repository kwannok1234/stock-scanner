import yfinance as yf
import requests
from datetime import datetime
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

# === 美股清單 ===
US_WATCHLIST = [
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

# === 港股清單（成交量最大30隻）===
HK_WATCHLIST = [
    "0700.HK",  # 騰訊
    "9988.HK",  # 阿里巴巴
    "3690.HK",  # 美團
    "1810.HK",  # 小米
    "1211.HK",  # 比亞迪
    "1024.HK",  # 快手
    "9888.HK",  # 百度
    "9618.HK",  # 京東
    "9999.HK",  # 網易
    "0981.HK",  # 中芯國際
    "1299.HK",  # 友邦保險
    "0005.HK",  # 匯豐控股
    "0388.HK",  # 香港交易所
    "2318.HK",  # 中國平安
    "0939.HK",  # 建設銀行
    "1398.HK",  # 工商銀行
    "0941.HK",  # 中國移動
    "3968.HK",  # 招商銀行
    "0883.HK",  # 中國海洋石油
    "2269.HK",  # 藥明生物
    "0175.HK",  # 吉利汽車
    "2333.HK",  # 長城汽車
    "2020.HK",  # 安踏體育
    "2331.HK",  # 李寧
    "0728.HK",  # 中國電信
    "1928.HK",  # 金沙中國
    "0016.HK",  # 新鴻基地產
    "0001.HK",  # 長和
    "0241.HK",  # 阿里健康
    "0268.HK",  # 金蝶國際
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

def get_market_status(ticker, label):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 200:
            return "unknown", {}
        close = df["Close"].squeeze()
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
        print(f"{label} market status error: {e}")
        return "unknown", {}

def market_label(status):
    status_map = {
        "green":   ("\U0001f7e2", "Normal trading"),
        "yellow":  ("\U0001f7e1", "Small positions only"),
        "orange":  ("\U0001f7e0", "Stop new positions"),
        "red":     ("\U0001f534", "Full defence"),
        "unknown": ("⚪",         "Unknown"),
    }
    return status_map.get(status, ("⚪", "Unknown"))

def check_sell_signals(holdings_file="holdings.txt"):
    sells = []
    if not os.path.exists(holdings_file):
        return sells
    with open(holdings_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "," not in line:
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

        # Stage 2: 股價 > 50MA > 150MA > 200MA
        stage2 = (float(close.iloc[-1]) > float(ma50.iloc[-1]) and
                  float(ma50.iloc[-1])  > float(ma150.iloc[-1]) and
                  float(ma150.iloc[-1]) > float(ma200.iloc[-1]))
        if not stage2:
            return False, {}

        # 200MA 向上傾斜
        if not (float(ma200.iloc[-1]) > float(ma200.iloc[-30])):
            return False, {}

        # 成交量突破（> 50日均量 x 1.4）
        vol_ratio = float(volume.iloc[-1]) / float(vol50.iloc[-1])
        if vol_ratio < 1.4:
            return False, {}

        # 價格突破 20 日高點
        pivot = float(df["High"].iloc[-21:-1].max().squeeze())
        if float(close.iloc[-1]) <= pivot:
            return False, {}

        # VCP：近10日波幅 < 近60日波幅的50%
        highs = df["High"].squeeze()
        lows  = df["Low"].squeeze()
        recent_range = float(highs.iloc[-60:-1].max()) - float(lows.iloc[-60:-1].min())
        tight_range  = float(highs.iloc[-10:-1].max()) - float(lows.iloc[-10:-1].min())
        vcp_ok = (recent_range > 0) and (tight_range < recent_range * 0.5)

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

def scan_market(watchlist, market_status, mkt, label, currency):
    emoji, text = market_label(market_status)
    buy_results = []

    if market_status in ["orange", "red"]:
        return buy_results, emoji, text, mkt

    for ticker in watchlist:
        signal, info = check_buy_signal(ticker)
        if signal:
            buy_results.append((ticker, info))
        print(f"  [{label}] {ticker}: {'BUY' if signal else '-'}")

    return buy_results, emoji, text, mkt

def run_scan():
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"Scan started {today}")

    # 止蝕警報（優先發送）
    sell_signals = check_sell_signals()
    for ticker, curr, stop in sell_signals:
        send_telegram(
            f"\U0001f534 STOP-LOSS ALERT\n"
            f"Stock: {ticker}\n"
            f"Price: {curr}\n"
            f"Stop: {stop}\n"
            f"Action: Exit position now"
        )

    # === 美股掃描 ===
    us_status, us_mkt = get_market_status("QQQ", "US")
    us_results, us_emoji, us_text, _ = scan_market(
        US_WATCHLIST, us_status, us_mkt, "US", "$"
    )

    # === 港股掃描 ===
    hk_status, hk_mkt = get_market_status("^HSI", "HK")
    hk_results, hk_emoji, hk_text, _ = scan_market(
        HK_WATCHLIST, hk_status, hk_mkt, "HK", "HK$"
    )

    # === 發送美股報告 ===
    us_msg = f"\U0001f1fa\U0001f1f8 US Scan {today}\n"
    us_msg += f"QQQ: ${us_mkt.get('price','-')} | 50MA: ${us_mkt.get('ma50','-')} | 200MA: ${us_mkt.get('ma200','-')}\n"
    us_msg += f"{us_emoji} {us_text}\n\n"

    if us_status in ["orange", "red"]:
        us_msg += "Market unfavourable - no new US positions"
    elif us_results:
        us_msg += f"✅ Buy signals: {len(us_results)}\n\n"
        for ticker, info in us_results:
            vcp_tag = "[VCP]" if info.get("vcp") else ""
            us_msg += (f"<b>{ticker}</b> ${info['price']} {vcp_tag}\n"
                       f"  Pivot: ${info['pivot']} | Vol: x{info['vol_ratio']}\n"
                       f"  Stop: ${info['stop']}\n\n")
    else:
        us_msg += "No buy signals today"
    send_telegram(us_msg)

    # === 發送港股報告 ===
    hk_msg = f"\U0001f1ed\U0001f1f0 HK Scan {today}\n"
    hk_msg += f"HSI: {hk_mkt.get('price','-')} | 50MA: {hk_mkt.get('ma50','-')} | 200MA: {hk_mkt.get('ma200','-')}\n"
    hk_msg += f"{hk_emoji} {hk_text}\n\n"

    if hk_status in ["orange", "red"]:
        hk_msg += "Market unfavourable - no new HK positions"
    elif hk_results:
        hk_msg += f"✅ Buy signals: {len(hk_results)}\n\n"
        for ticker, info in hk_results:
            vcp_tag = "[VCP]" if info.get("vcp") else ""
            name_map = {
                "0700.HK":"騰訊","9988.HK":"阿里","3690.HK":"美團",
                "1810.HK":"小米","1211.HK":"比亞迪","1024.HK":"快手",
                "9888.HK":"百度","9618.HK":"京東","9999.HK":"網易",
                "0981.HK":"中芯","1299.HK":"友邦","0005.HK":"匯豐",
                "0388.HK":"HKEX","2318.HK":"平安","0939.HK":"建行",
                "1398.HK":"工行","0941.HK":"中移動","3968.HK":"招行",
                "0883.HK":"中海油","2269.HK":"藥明生物","0175.HK":"吉利",
                "2333.HK":"長城","2020.HK":"安踏","2331.HK":"李寧",
                "0728.HK":"電信","1928.HK":"金沙","0016.HK":"新地",
                "0001.HK":"長和","0241.HK":"阿里健康","0268.HK":"金蝶"
            }
            name = name_map.get(ticker, ticker)
            hk_msg += (f"<b>{ticker} {name}</b> HK${info['price']} {vcp_tag}\n"
                       f"  Pivot: HK${info['pivot']} | Vol: x{info['vol_ratio']}\n"
                       f"  Stop: HK${info['stop']}\n\n")
    else:
        hk_msg += "No buy signals today"
    send_telegram(hk_msg)

if __name__ == "__main__":
    run_scan()
