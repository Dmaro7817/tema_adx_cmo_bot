import os
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env, если он есть

BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")




# Общий таймфрейм для всех модулей
TIMEFRAME = "1h"

TP_LEVELS = [2.0, 2.5, 5.0]  # Take Profit уровни в %
TP_PERCENTAGES = [60, 20, 20]  # Проценты от позиции на каждом TP

SL_PERCENT = 5.0  # Stop Loss в %
USE_TRAILING_STOP = True  # Включить трейлинг стоп
TRAILING_STOP_ACTIVATION_PERCENT = 2.0  # Процент движения в прибыль для активации трейлинг-стопа
TRAILING_STOP_PERCENT = 3.5  # Шаг трейлинг-стопа в %

LEVERAGE = 1
TRADE_AMOUNT = 6.0   # сумма в $
DEPOSIT = 100

#-----ИНДИКАТОРЫ-----
# Периоды для трёх TEMA линий (можно менять)
TEMA_PERIODS = [8, 14, 21]

# Периоды для ADX
ADX_PERIOD = 14

# Периоды для Chande Momentum Oscillator (CMO)
CMO_PERIOD = 14

# Угол откланения EMA
EMA_WINDOW = 100        # окно (период) для расчёта EMA (например, 20 свечей)
SLOPE_PERIOD = 30      # период для расчёта наклона EMA (например, последние 30 точек)




#-----СТРАТЕГИИ-----

TEMA_ADX_CMO_ENABLED = True

TEMA_ADX_THRESHOLD_LONG = 25   # Пример: ADX >= 25 для лонга
TEMA_ADX_THRESHOLD_SHORT = 25  # Пример: ADX <= 25 для шорта

TEMA_CMO_THRESHOLD_LONG = 0   # Пример: CMO > 20 для лонга
TEMA_CMO_THRESHOLD_SHORT = 0 # Пример: CMO < -20 для шорта
