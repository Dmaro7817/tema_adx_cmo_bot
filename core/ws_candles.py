from pybit.unified_trading import WebSocket
import threading
import queue

class CandlesWS:
    def __init__(self, symbols, interval="1m"):
        self.ws = WebSocket(
            testnet=False,
            channel_type="linear"
        )
        self.symbols = symbols
        self.interval = interval
        self.queues = {symbol: queue.Queue(maxsize=500) for symbol in symbols}
        self._start()

    def _start(self):
        for symbol in self.symbols:
            self.ws.kline_stream(
                symbol=symbol,
                interval=self.interval,
                callback=lambda message, s=symbol: self._on_candle(message, s)
            )

    def _on_candle(self, message, symbol):
        data = message['data']
        if self.queues[symbol].full():
            self.queues[symbol].get()
        self.queues[symbol].put(data)

    def get_latest_candles(self, symbol, n=100):
        q = self.queues[symbol]
        return list(q.queue)[-n:]
