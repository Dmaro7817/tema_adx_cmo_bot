import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_ohlcv_pybit(session, symbol, interval, limit=200):
    try:
        data = session.get_kline(category="linear", symbol=symbol, interval=str(interval), limit=limit)
        kline_list = data.get("result", {}).get("list", [])
        if not kline_list:
            print(f"[PYBIT] Нет свечей для {symbol}")
            return pd.DataFrame()
        df = pd.DataFrame(
            kline_list,
            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
        )
        df["timestamp"] = (df["timestamp"].astype("int64") // 1000).astype(int)
        for col in ["open", "high", "low", "close", "volume", "turnover"]:
            df[col] = df[col].astype(float)
        df = df.sort_values("timestamp")
        return df
    except Exception as e:
        print(f"[PYBIT] Ошибка загрузки свечей для {symbol}: {e}")
        return pd.DataFrame()

def load_initial_history_pybit(session, symbols, interval, limit, max_workers):
    candles_cache = {}

    def worker(symbol):
        df = fetch_ohlcv_pybit(session, symbol, interval, limit)
        if not df.empty:
            print(f"[HISTORY] {symbol}: загружено {len(df)} свечей")
        else:
            print(f"[HISTORY] {symbol}: свечи не получены!")
        return symbol, df

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, symbol): symbol for symbol in symbols}
        for fut in as_completed(futures):
            symbol, df = fut.result()
            if not df.empty:
                candles_cache[symbol] = df

    return candles_cache
