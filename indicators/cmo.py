import pandas as pd
from configs.config import CMO_PERIOD, TIMEFRAME

def calculate_cmo(close: pd.Series) -> pd.Series:
    """
    Рассчитывает Chande Momentum Oscillator (CMO) для переданного ряда закрытий.
    close: pd.Series с ценами закрытия
    Период берётся из CMO_PERIOD (config)
    Возвращает pd.Series с CMO
    """
    period = CMO_PERIOD

    diff = close.diff()
    up = diff.where(diff > 0, 0).abs()
    down = diff.where(diff < 0, 0).abs()

    sum_up = up.rolling(window=period, min_periods=period).sum()
    sum_down = down.rolling(window=period, min_periods=period).sum()

    cmo = 100 * (sum_up - sum_down) / (sum_up + sum_down)
    return cmo
