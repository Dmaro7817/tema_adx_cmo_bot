import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os  # <--- добавлено

# Мапа для перевода формата таймфрейма в нужный для Bybit REST API
TF_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
    "1d": "D", "1w": "W", "1M": "M"
}

def format_interval(interval):
    """Преобразует '1m', '5m', '1h' и т.д. в формат для Bybit REST API."""
    return TF_MAP.get(str(interval), str(interval))

def fetch_ohlcv_pybit(session, symbol, interval, limit=200):
    """
    Получение исторических OHLCV данных через REST API pybit по одной паре.
    """
    interval = format_interval(interval)
    try:
        data = session.get_kline(category="linear", symbol=symbol, interval=str(interval), limit=limit)
        kline_list = data.get("result", {}).get("list", [])
        print(f"[DEBUG] {symbol} RAW kline_list first 5:", kline_list[:5])  # <--- добавлено
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
        print(f"[DEBUG] {symbol} Last 5 candles MSK:\n",
              df.tail(5).assign(
                msk_time=lambda x: pd.to_datetime(x["timestamp"], unit="s") + pd.Timedelta(hours=3)
              )[["msk_time", "open", "high", "low", "close", "volume", "turnover"]])  # <--- добавлено
        return df
    except Exception as e:
        print(f"[PYBIT] Ошибка загрузки свечей для {symbol}: {e}")
        return pd.DataFrame()

def filter_ws_supported_symbols(symbols, session, interval="1"):
    """
    Фильтрация рабочих пар (для которых REST API реально отдаёт свечи).
    """
    interval = format_interval(interval)
    supported = []
    for symbol in symbols:
        try:
            data = session.get_kline(category="linear", symbol=symbol, interval=interval, limit=1)
            kline_list = data.get("result", {}).get("list", [])
            if kline_list and not ("error" in data or ("retMsg" in data and "not supported" in data["retMsg"].lower())):
                supported.append(symbol)
        except Exception as e:
            print(f"[KLINE_FILTER] {symbol} не поддерживается: {e}")
    print(f"[KLINE_FILTER] Рабочих пар для подписки: {len(supported)}")
    return supported

def chunked(iterable, n):
    """Yield successive n-sized chunks from iterable."""
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

def load_initial_history_pybit(session, symbols, interval, limit, max_workers, chunk_size=110, chunk_delay=1):
    """
    Получение исторических свечей по всем рабочим парам через ThreadPoolExecutor с обработкой чанками.
    """
    interval = format_interval(interval)
    candles_cache = {}

    def worker(symbol):
        df = fetch_ohlcv_pybit(session, symbol, interval, limit)
        if not df.empty:
            print(f"[HISTORY] {symbol}: загружено {len(df)} свечей")
        else:
            print(f"[HISTORY] {symbol}: свечи не получены!")
        return symbol, df

    for chunk in chunked(symbols, chunk_size):
        print(f"[CHUNK] Загружаем следующие пары: {chunk}")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(worker, symbol): symbol for symbol in chunk}
            for fut in as_completed(futures):
                symbol, df = fut.result()
                if not df.empty:
                    candles_cache[symbol] = df
        time.sleep(chunk_delay)  # Пауза между чанками для обхода лимита

    # === Сохранение всех данных в отдельные файлы после сбора ===
    save_dir = "history_data"
    os.makedirs(save_dir, exist_ok=True)
    for symbol, df in candles_cache.items():
        # Имя файла с подстановкой символа и таймфрейма
        filename = f"{symbol}_{interval}_history.csv"
        filepath = os.path.join(save_dir, filename)
        try:
            df.to_csv(filepath, index=False)
            print(f"[SAVE] История для {symbol} сохранена в {filepath}")
        except Exception as e:
            print(f"[SAVE] Ошибка при сохранении {symbol}: {e}")

    return candles_cache