# Общий таймфрейм для всех модулей
TIMEFRAME = "1h"

# Периоды для трёх TEMA линий (можно менять)
TEMA_PERIODS = [8, 14, 21]

# Периоды для ADX
ADX_PERIOD = 14

# Периоды для Chande Momentum Oscillator (CMO)
CMO_PERIOD = 14





# СТРАТЕГИИ

TEMA_ADX_CMO_ENABLED = True

TEMA_ADX_THRESHOLD_LONG = 25   # Пример: ADX >= 25 для лонга
TEMA_ADX_THRESHOLD_SHORT = 25  # Пример: ADX <= 25 для шорта

TEMA_CMO_THRESHOLD_LONG = 0   # Пример: CMO > 20 для лонга
TEMA_CMO_THRESHOLD_SHORT = 0 # Пример: CMO < -20 для шорта
