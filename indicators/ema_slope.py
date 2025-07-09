import numpy as np
from sklearn.linear_model import LinearRegression
import pandas as pd
from config import EMA_WINDOW, SLOPE_PERIOD, EMA_LIGHT, TIMEFRAME

def calculate_ema_slope(
    prices: pd.Series,
    ema_window: int = EMA_WINDOW,
    slope_period: int = SLOPE_PERIOD,
    ema_light: int = EMA_LIGHT
):
    """
    Вычисляет наклон линии EMA за последние slope_period.

    :param prices: pd.Series исторических цен (например, закрытия)
    :param ema_window: окно EMA
    :param slope_period: период для расчёта наклона
    :param ema_light: окно для дополнительной "лёгкой" EMA
    :return: (slope, ema_series, ema_light_series)
    """
    if len(prices) < max(ema_window, ema_light) + slope_period:
        raise ValueError(f"Need at least {max(ema_window, ema_light) + slope_period} data points")

    ema_series = prices.ewm(span=ema_window, adjust=False).mean()
    ema_light_series = prices.ewm(span=ema_light, adjust=False).mean()

    ema_values = ema_series.dropna().iloc[-slope_period:].values
    X = np.arange(slope_period).reshape(-1, 1)

    model = LinearRegression()
    model.fit(X, ema_values)
    slope = model.coef_[0]

    return slope, ema_series, ema_light_series
