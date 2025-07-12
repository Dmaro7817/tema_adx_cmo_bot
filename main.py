import subprocess
import time
import asyncio
from pybit.unified_trading import HTTP
from config import (
    HISTORY_CANDLE_LIMIT, THREADPOOL_WORKERS, TIMEFRAME,
    VOLUME24_FILTER_ENABLED, MIN_VOLUME24H
)

from core.ohlcv import load_initial_history_pybit
from core.websocket_collector import start_websocket_collector_proc
from core.websocket_private import start_websocket_private_proc

# === Импорт индикаторов из папки indicators ===
from indicators.adx import calculate_adx
from indicators.cmo import calculate_cmo
from indicators.ema_slope import calculate_ema_slope
from indicators.tema import calculate_tema_lines

import pandas as pd
from datetime import datetime, timedelta
import requests

# Импорт стратегии
from strategies.tema_adx_cmo import check_signal

def fetch_bybit_symbols_pybit(session):
    try:
        response = session.get_tickers(category="linear")
        symbols_data = response["result"]["list"]
        symbols = [s["symbol"] for s in symbols_data if "USDT" in s["symbol"]]
        print(f"[Bybit] ✅ Загружено {len(symbols)} пар через pybit")
        return symbols
    except Exception as e:
        print(f"[Bybit] ⚠️ Ошибка загрузки пар: {e}")
        return []

def filter_symbols_by_volume24h(symbols, min_volume24h=1_000_000):
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        tickers = data.get("result", {}).get("list", [])
        symbol_to_vol = {t["symbol"]: float(t.get("volume24h", 0)) for t in tickers}
        filtered = [s for s in symbols if symbol_to_vol.get(s, 0) >= min_volume24h]
        print(f"[FILTER] Пары после фильтра по объему 24ч >= {min_volume24h}: {filtered} (количество: {len(filtered)})")
        return filtered
    except Exception as e:
        print(f"[FILTER] Ошибка фильтрации по объему 24ч: {e}")
        return symbols  # если не получилось — возвращаем всё

# --- Синхронизация времени при запуске ---
try:
    subprocess.run(["sudo", "ntpdate", "pool.ntp.org"])
    subprocess.run(["sudo", "timedatectl", "set-ntp", "true"])
    print("[TIME] Системное время синхронизировано через ntpdate и timedatectl.")
except Exception as e:
    print(f"[TIME] Ошибка синхронизации времени: {e}")

def log_indicator(symbol, indicator_name, series):
    """Универсальный логгер для индикаторов."""
    msk_time = (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    values = pd.Series(series).dropna()[-10:].tolist()
    # print(f"[{symbol}] [{msk_time}] {indicator_name}: {values}")  # <-- закомментирован лог индикаторов

def main():
    session = HTTP(api_key="", api_secret="", testnet=False, recv_window=15000)

    # Получение списка символов
    symbols = fetch_bybit_symbols_pybit(session)
    if not symbols:
        print("Не удалось получить рабочий список торговых пар. Завершение работы.")
        return

    # -- Фильтр по объему 24ч (если включен в config) --
    if 'VOLUME24_FILTER_ENABLED' in globals() and VOLUME24_FILTER_ENABLED:
        symbols = filter_symbols_by_volume24h(symbols, MIN_VOLUME24H)

    # 1. Сбор исторических данных чанками (chunk_size и chunk_delay теперь доступны)
    history_cache = load_initial_history_pybit(
        session, symbols, TIMEFRAME, HISTORY_CANDLE_LIMIT, THREADPOOL_WORKERS, chunk_size=10, chunk_delay=1
    )
    print("[MAIN] Исторические данные по всем парам собраны.")

    # --- Логирование индикаторов по каждой паре ---
    for symbol, df in history_cache.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue

        # ADX
        try:
            adx = calculate_adx(df)
            log_indicator(symbol, "ADX", adx)
        except Exception as e:
            # print(f"[{symbol}] Ошибка расчета ADX: {e}")  # <-- закомментирован лог индикаторов
            pass

        # CMO
        try:
            cmo = calculate_cmo(df['close'])
            log_indicator(symbol, "CMO", cmo)
        except Exception as e:
            # print(f"[{symbol}] Ошибка расчета CMO: {e}")  # <-- закомментирован лог индикаторов
            pass

        # EMA и EMA SLOPE
        try:
            slope, ema_series = calculate_ema_slope(df['close'])
            log_indicator(symbol, "EMA", ema_series)
            log_indicator(symbol, "EMA_SLOPE", [slope])
        except Exception as e:
            # print(f"[{symbol}] Ошибка расчета EMA/EMA SLOPE: {e}")  # <-- закомментирован лог индикаторов
            pass

        # TEMA
        try:
            tema_lines = calculate_tema_lines(df['close'])
            for name, series in tema_lines.items():
                log_indicator(symbol, name, series)
        except Exception as e:
            # print(f"[{symbol}] Ошибка расчета TEMA: {e}")  # <-- закомментирован лог индикаторов
            pass

    # 2. Запуск отдельного процесса WebSocket collector
    ws_proc, ws_stop = start_websocket_collector_proc(symbols, TIMEFRAME)
    print("[MAIN] WebSocket collector процесс запущен.")

    # 3. Запуск приватного WebSocket процесса
    ws_private_proc, ws_private_stop = start_websocket_private_proc()
    print("[MAIN] Приватный WebSocket collector процесс запущен.")

    # === Запуск мониторинга рынка по стратегии ===
    print("[STRATEGY] Бот начал мониторинг рынка по стратегии TEMA/ADX/CMO...")

    try:
        while True:
            # Имитация получения новых данных для каждой пары (в реале - из WebSocket либо обновлять history_cache)
            for symbol, df in history_cache.items():
                if not isinstance(df, pd.DataFrame) or df.empty or len(df) < 50:
                    print(f"[STRATEGY] {symbol}: недостаточно данных для анализа.")
                    continue
                print(f"[STRATEGY] Анализирую {symbol} по индикаторам...")
                signal = check_signal(df)
                if signal is None:
                    print(f"[STRATEGY] {symbol}: сделка не открыта - нет сигнала по индикаторам.")
                elif signal == "long":
                    print(f"[STRATEGY] {symbol}: СИГНАЛ НА LONG! (сделка будет открыта/симулирована)")
                elif signal == "short":
                    print(f"[STRATEGY] {symbol}: СИГНАЛ НА SHORT! (сделка будет открыта/симулирована)")
                else:
                    print(f"[STRATEGY] {symbol}: неизвестный сигнал: {signal}")
            # Для примера - анализ раз в 30 секунд (в реальном времени - скорее по факту новой свечи)
            time.sleep(30)
    except KeyboardInterrupt:
        print("Остановка бота...")
        ws_stop.set()
        ws_proc.join()
        ws_private_stop.set()
        ws_private_proc.join()
        print("[MAIN] Все процессы остановлены.")

if __name__ == "__main__":
    main()