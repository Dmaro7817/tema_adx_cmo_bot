import os
import pandas as pd
import time

from core.bybit_trader import BybitTrader
from core.ws_candles import CandlesWS
from strategies.tema_adx_cmo import check_signal
from configs.config import DEPOSIT, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TIMEFRAME
from core.telegram_notify import send_telegram_message

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

def main():
    # Инициализация трейдера
    trader = BybitTrader(deposit=DEPOSIT)

    # Получение всех доступных фьючерсных пар с биржи
    symbols = get_all_bybit_futures_symbols(trader)
    if not symbols:
        print("Не удалось получить список торговых пар. Завершение работы.")
        return

    # Запуск WebSocket клиента для свечей по всем парам
    ws_candles = CandlesWS(symbols, interval=TIMEFRAME)

    print("Бот запущен. Следит за всеми фьючерсными парами на Bybit.")

    while True:
        for symbol in symbols:
            candles = ws_candles.get_latest_candles(symbol, n=100)
            if len(candles) < 50:
                continue  # Не хватает данных для индикаторов

            df = pd.DataFrame(candles)
            if not all(col in df for col in ['close', 'high', 'low']):
                continue

            signal = check_signal(df)
            if signal in ["long", "short"]:
                side = "buy" if signal == "long" else "sell"
                entry_price = float(df['close'].iloc[-1])
                amount = trader.deposit  # или любая желаемая логика расчёта объёма

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
                else:
                    msg = f"Ошибка при открытии сделки: {side.upper()} {symbol}"
                    send_telegram_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

        time.sleep(5)

if __name__ == "__main__":
    main()
