import os
import pandas as pd
import time
import threading

from core.bybit_trader import BybitTrader
from core.ws_candles import CandlesWS
from strategies.tema_adx_cmo import check_signal
from config import DEPOSIT, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TIMEFRAME
from core.telegram_notify import send_telegram_message

# --- Добавлено для работы IndicatorCache и BybitRestClient ---
from core.bybit_rest import BybitRestClient
from core.indicator_cache import IndicatorCache
# -------------------------------------------------------------

def get_all_bybit_futures_symbols(trader):
    """
    Получить все доступные фьючерсные пары на Bybit через bybit_trader
    """
    try:
        info = trader.session.get_instruments_info(category=trader.category)
        return [item['symbol'] for item in info['result']['list']]
    except Exception as e:
        print(f"Ошибка получения списка контрактов: {e}")
        return []

def process_symbol(symbol, ws_candles, indicator_cache, trader, logs, logs_lock):
    try:
        candles = ws_candles.get_latest_candles(symbol, n=100)
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        if not candles:
            with logs_lock:
                logs.append(f"[{now}] Нет данных по {symbol} (WebSocket, вероятно, закрыт или не подписан)")
            return
        if len(candles) < 50:
            with logs_lock:
                logs.append(f"[{now}] Мало данных по {symbol}: {len(candles)} свечей")
            return

        df = pd.DataFrame(candles)
        if not all(col in df for col in ['close', 'high', 'low']):
            with logs_lock:
                logs.append(f"[{now}] Нет нужных столбцов для {symbol}")
            return

        # --- Обновление кэша индикаторов при приходе новой свечи ---
        indicator_cache.update(symbol, df.iloc[-1])
        with logs_lock:
            logs.append(f"[{now}] Обновлены данные по {symbol}, close: {df['close'].iloc[-1]}")

        signal = check_signal(df)
        if signal in ["long", "short"]:
            side = "buy" if signal == "long" else "sell"
            entry_price = float(df['close'].iloc[-1])
            amount = trader.deposit  # или любая желаемая логика расчёта объёма

            with logs_lock:
                logs.append(f"[{now}] Сигнал {signal.upper()} для {symbol} по цене {entry_price}")

            # --- Открытие сделки ---
            trade = trader.open_trade(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                amount=amount,
                leverage=1,   # Можно вынести в конфиг
                tp_levels=[], # Заполнить если требуется
                tp_percents=[],
                sl_percent=1, # Заполнить из конфига при необходимости
                trailing_stop=False,
                trailing_percent=0
            )

            # --- Telegram оповещение ---
            if trade:
                msg = f"Открыта сделка: {side.upper()} {symbol} по цене {entry_price}"
                send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
                with logs_lock:
                    logs.append(f"[{now}] {msg}")
            else:
                msg = f"Ошибка при открытии сделки: {side.upper()} {symbol}"
                send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
                with logs_lock:
                    logs.append(f"[{now}] {msg}")
    except Exception as e:
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        error_text = str(e)
        with logs_lock:
            logs.append(f"[{now}] Ошибка для символа {symbol}: {e}")
        if "Connection is already closed" in error_text:
            with logs_lock:
                logs.append(f"[{now}] WebSocket закрыт. Попробуйте перезапустить бота или отфильтровать неподдерживаемые пары.")
            # break  # Можно раскомментировать для аварийного выхода из цикла

def main():
    # Инициализация трейдера
    trader = BybitTrader(deposit=DEPOSIT)

    # Получение всех доступных фьючерсных пар с биржи
    symbols = get_all_bybit_futures_symbols(trader)
    if not symbols:
        print("Не удалось получить список торговых пар. Завершение работы.")
        return

    print(f"Список символов для подписки ({len(symbols)}): {symbols}")

    # --- Инициализация BybitRestClient и IndicatorCache ---
    rest_client = BybitRestClient(trader.session)
    indicator_cache = IndicatorCache(symbols, rest_client, TIMEFRAME)
    indicator_cache.initialize()
    # ------------------------------------------------------

    # Запуск WebSocket клиента для свечей по всем парам
    ws_candles = CandlesWS(symbols, interval=TIMEFRAME)

    print("Бот запущен. Следит за всеми фьючерсными парами на Bybit.")

    logs_counter = 0
    logs_interval = 10  # каждые 10 итераций будет отдельный лог

    # Для потоковой записи логов
    logs = []
    logs_lock = threading.Lock()
    max_threads = 8  # Можно увеличить, если сервер позволяет

    while True:
        logs_counter += 1
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{now}] Новый цикл опроса свечей")

        threads = []
        for symbol in symbols:
            t = threading.Thread(target=process_symbol, args=(symbol, ws_candles, indicator_cache, trader, logs, logs_lock))
            threads.append(t)
            t.start()
            # Ограничение количества одновременно работающих потоков
            while threading.active_count() > max_threads:
                time.sleep(0.01)

        # Дождаться завершения всех потоков
        for t in threads:
            t.join()

        # Вывод логов за цикл
        with logs_lock:
            for log in logs:
                print(log)
            logs.clear()

        if logs_counter % logs_interval == 0:
            print(f"[{now}] Бот активен. Всего пар: {len(symbols)}. Последний цикл завершён.")

        time.sleep(5)

if __name__ == "__main__":
    main()