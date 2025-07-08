import pandas as pd

def calculate_tema(close: pd.Series, period: int = 9) -> pd.Series:
    """
    Рассчитывает тройную экспоненциальную скользящую среднюю (TEMA).
    :param close: pd.Series с ценами закрытия
    :param period: период расчёта TEMA
    :return: pd.Series с TEMA
    """
    ema1 = close.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    tema = 3 * (ema1 - ema2) + ema3
    return tema
