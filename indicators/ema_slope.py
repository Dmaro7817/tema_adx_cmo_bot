import numpy as np
import pandas as pd
import talib

def calculate_ema_angle(close_prices, ema_period=20, slope_period=30):
    """
    close_prices: pandas.Series или список цен закрытия
    ema_period: период скользящей средней
    slope_period: период для расчёта угла (разница между EMA сейчас и N свечей назад)
    """
    if not isinstance(close_prices, pd.Series):
        close_prices = pd.Series(close_prices)

    # Вычисляем EMA
    ema = talib.EMA(close_prices, timeperiod=ema_period)

    # Разница (slope) между текущей EMA и EMA N свечей назад
    delta = ema - ema.shift(slope_period)

    # Для нормализации по "горизонтали" используем slope_period (по оси X)
    # Угол (в радианах): arctan(ΔEMA/ΔX)
    angle_rad = np.arctan(delta / slope_period)

    # Переводим в градусы
    angle_deg = np.degrees(angle_rad)

    return angle_deg

# Пример использования:
if __name__ == "__main__":
    # Примерные цены, замените на свои данные
    closes = [100 + np.sin(x/10) for x in range(100)]
    angle = calculate_ema_angle(closes, ema_period=20, slope_period=30)
    print(angle.tail(10))  # последние 10 значений угла EMA
