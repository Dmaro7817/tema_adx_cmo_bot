import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from config import EMA_WINDOW, SLOPE_PERIOD

def calculate_ema_slope(
    prices: pd.Series,
    ema_window: int = EMA_WINDOW,
    slope_period: int = SLOPE_PERIOD
):
    """
    Вычисляет наклон линии EMA (экспоненциальной скользящей средней) за последние slope_period точек.

    :param prices: pd.Series исторических цен (например, закрытия)
    :param ema_window: окно EMA
    :param slope_period: период для расчёта наклона EMA
    :return: (slope, ema_series)
    """
    if len(prices) < ema_window + slope_period:
        raise ValueError(f"Need at least {ema_window + slope_period} data points")

    ema_series = prices.ewm(span=ema_window, adjust=False).mean()
    ema_values = ema_series.dropna().iloc[-slope_period:].values

    X = np.arange(slope_period).reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, ema_values)
    slope = model.coef_[0]

    return slope, ema_series
