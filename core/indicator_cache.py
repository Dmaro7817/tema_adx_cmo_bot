from indicators.tema import calculate_tema_lines
from indicators.adx import calculate_adx
from indicators.cmo import calculate_cmo
from indicators.ema_slope import calculate_ema_slope
from core.bybit_rest import BybitRestClient

class IndicatorCache:
    def __init__(self, symbols, rest_client, timeframe):
        self.cache = {}  # { symbol: {"df": df, "tema": ..., "adx": ..., "cmo": ..., "ema_slope": ..., "ema": ...} }
        self.symbols = symbols
        self.rest_client = rest_client
        self.timeframe = timeframe

    def initialize(self):
        for symbol in self.symbols:
            df = self.rest_client.get_historical_candles(symbol, self.timeframe, limit=100)
            if df is not None and len(df) > 0:
                tema = calculate_tema_lines(df['close'])
                adx = calculate_adx(df)
                cmo = calculate_cmo(df['close'])
                # --- EMA slope ---
                try:
                    ema_slope, ema = calculate_ema_slope(df['close'])
                except Exception:
                    ema_slope, ema = None, None
                self.cache[symbol] = {
                    "df": df,
                    "tema": tema,
                    "adx": adx,
                    "cmo": cmo,
                    "ema_slope": ema_slope,
                    "ema": ema
                }

    def update(self, symbol, new_candle):
        if symbol in self.cache:
            df = self.cache[symbol]["df"]
            df = df.append(new_candle, ignore_index=True)
            tema = calculate_tema_lines(df['close'])
            adx = calculate_adx(df)
            cmo = calculate_cmo(df['close'])
            # --- EMA slope ---
            try:
                ema_slope, ema = calculate_ema_slope(df['close'])
            except Exception:
                ema_slope, ema = None, None
            self.cache[symbol] = {
                "df": df,
                "tema": tema,
                "adx": adx,
                "cmo": cmo,
                "ema_slope": ema_slope,
                "ema": ema
            }
