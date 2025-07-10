import requests
import concurrent.futures

def get_all_symbols():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    return [item["symbol"] for item in data["result"]["list"] if "USDT" in item["symbol"]]

def symbol_has_kline(symbol, interval="1m"):
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit=1"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        candles = data.get("result", {}).get("list", [])
        return len(candles) > 0
    except Exception as e:
        return False

def get_symbols_with_kline(symbols, interval="1m", max_workers=15):
    working = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fut2symbol = {executor.submit(symbol_has_kline, s, interval): s for s in symbols}
        for fut in concurrent.futures.as_completed(fut2symbol):
            symbol = fut2symbol[fut]
            try:
                if fut.result():
                    working.append(symbol)
                    print(f"[KLINE:OK] {symbol}")
                else:
                    print(f"[KLINE:SKIP] {symbol}")
            except Exception as e:
                print(f"[KLINE:ERR] {symbol}: {e}")
    return working

def scan_and_save_kline_symbols(filepath="symbols_with_kline.txt", interval="1m"):
    symbols = get_all_symbols()
    good = get_symbols_with_kline(symbols, interval)
    with open(filepath, "w") as f:
        for s in good:
            f.write(s + "\n")
    print(f"Рабочих пар с kline: {len(good)}. Список сохранён в {filepath}")
    return good
