import subprocess
import time
import asyncio
from pybit.unified_trading import HTTP
from config import (
    HISTORY_CANDLE_LIMIT, THREADPOOL_WORKERS, TIMEFRAME
)

from core.ohlcv import load_initial_history_pybit
from core.websocket_collector import start_websocket_collector_proc

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

# --- Синхронизация времени при запуске ---
try:
    subprocess.run(["sudo", "ntpdate", "pool.ntp.org"])
    subprocess.run(["sudo", "timedatectl", "set-ntp", "true"])
    print("[TIME] Системное время синхронизировано через ntpdate и timedatectl.")
except Exception as e:
    print(f"[TIME] Ошибка синхронизации времени: {e}")

def main():
    session = HTTP(api_key="", api_secret="", testnet=False, recv_window=15000)

    # Получение списка символов
    symbols = fetch_bybit_symbols_pybit(session)
    if not symbols:
        print("Не удалось получить рабочий список торговых пар. Завершение работы.")
        return

    # 1. Сбор исторических данных
    history_cache = load_initial_history_pybit(session, symbols, TIMEFRAME, HISTORY_CANDLE_LIMIT, THREADPOOL_WORKERS)
    print("[MAIN] Исторические данные по всем парам собраны.")

    # 2. Запуск отдельного процесса WebSocket collector
    ws_proc, ws_stop = start_websocket_collector_proc(symbols, TIMEFRAME)
    print("[MAIN] WebSocket collector процесс запущен.")

    try:
        # Основной цикл или инициализация торговли/стратегии здесь, если нужно
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("Остановка бота...")
        ws_stop.set()
        ws_proc.join()
        print("[MAIN] Процесс WebSocket collector остановлен.")

if __name__ == "__main__":
    main()
