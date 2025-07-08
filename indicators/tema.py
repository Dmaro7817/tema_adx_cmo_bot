import pandas as pd
from configs.config import TEMA_PERIODS

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def tema(series: pd.Series, period: int) -> pd.Series:
    e1 = ema(series, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    return 3 * (e1 - e2) + e3

def calculate_tema_lines(close_prices: pd.Series) -> dict:
    """
    Возвращает словарь с тремя TEMA линиями по разным периодам.
    Периоды берутся из конфига: TEMA_PERIODS = [period1, period2, period3]
    """
    assert len(TEMA_PERIODS) == 3, "В config.py должен быть список из 3 периодов для TEMA_PERIODS"
    return {
        f"tema_{i+1}": tema(close_prices, period)
        for i, period in enumerate(TEMA_PERIODS)
    }
