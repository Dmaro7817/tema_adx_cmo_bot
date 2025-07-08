import pandas as pd
from configs.config import ADX_PERIOD, TIMEFRAME

def calculate_adx(df: pd.DataFrame) -> pd.Series:
    """
    df должен содержать столбцы: 'high', 'low', 'close'
    Период ADX берется из ADX_PERIOD (config)
    Возвращает pd.Series с индексом, совпадающим с df
    """
    period = ADX_PERIOD

    high = df['high']
    low = df['low']
    close = df['close']

    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < minus_dm] = 0
    plus_dm[plus_dm < 0] = 0

    minus_dm = low.diff()
    minus_dm[minus_dm < plus_dm] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = minus_dm.abs()

    tr1 = (high - low)
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period, min_periods=period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period, min_periods=period).mean()

    return adx
