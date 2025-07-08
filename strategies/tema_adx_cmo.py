from indicators.tema import calculate_tema_lines
from indicators.adx import calculate_adx
from indicators.cmo import calculate_cmo
from configs.config import (
    TEMA_ADX_CMO_ENABLED,
    TEMA_ADX_THRESHOLD_LONG,
    TEMA_ADX_THRESHOLD_SHORT,
    TEMA_CMO_THRESHOLD_LONG,
    TEMA_CMO_THRESHOLD_SHORT,
)

def check_signal(df):
    """
    df: pandas.DataFrame с колонками ['close', 'high', 'low']
    Возвращает 'long', 'short' или None
    """
    if not TEMA_ADX_CMO_ENABLED:
        return None

    tema = calculate_tema_lines(df['close'])
    adx = calculate_adx(df)
    cmo = calculate_cmo(df['close'])

    # последние значения индикаторов
    t1 = tema['tema_1'].iloc[-1]
    t2 = tema['tema_2'].iloc[-1]
    t3 = tema['tema_3'].iloc[-1]
    adx_last = adx.iloc[-1]
    cmo_last = cmo.iloc[-1]

    # ЛОНГ: короткая > средняя > длинная, ADX >= порога, CMO > порога
    if (
        t1 > t2 and t2 > t3 and
        adx_last >= TEMA_ADX_THRESHOLD_LONG and
        cmo_last > TEMA_CMO_THRESHOLD_LONG
    ):
        return "long"

    # ШОРТ: короткая < средняя < длинная, ADX <= порога, CMO < порога
    if (
        t1 < t2 and t2 < t3 and
        adx_last <= TEMA_ADX_THRESHOLD_SHORT and
        cmo_last < TEMA_CMO_THRESHOLD_SHORT
    ):
        return "short"

    return None
