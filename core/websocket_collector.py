import os
import json
import csv
import asyncio
import websockets
from multiprocessing import Process, Event

KLINE_CSV_PATH = "/root/my_emacross_bot/bybit_futures_data_multi_tf/klines"
TICKER_CSV_PATH = "/root/my_emacross_bot/bybit_futures_data_multi_tf/tickers"
TRADE_CSV_PATH = "/root/my_emacross_bot/bybit_futures_data_multi_tf/trades"
ORDERBOOK_CSV_PATH = "/root/my_emacross_bot/bybit_futures_data_multi_tf/orderbook"
os.makedirs(KLINE_CSV_PATH, exist_ok=True)
os.makedirs(TICKER_CSV_PATH, exist_ok=True)
os.makedirs(TRADE_CSV_PATH, exist_ok=True)
os.makedirs(ORDERBOOK_CSV_PATH, exist_ok=True)

klines_buffer = {}
tickers_buffer = {}
trades_buffer = {}
orderbook_buffer = {}
last_ticker_state = {}

def timeframe_to_ws_interval(tf):
    tf_map = {
        "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
        "1d": "D", "1w": "W", "1M": "M"
    }
    normalized = str(tf).lower().replace(" ", "")
    return tf_map.get(normalized, normalized)

def save_kline_snapshot(symbol, kline):
    filename = os.path.join(KLINE_CSV_PATH, f"{symbol}_kline.csv")
    header = not os.path.exists(filename)
    row = {
        "timestamp": int(kline["start"]) // 1000,
        "open": float(kline["open"]),
        "high": float(kline["high"]),
        "low": float(kline["low"]),
        "close": float(kline["close"]),
        "volume": float(kline["volume"]),
        "turnover": float(kline["turnover"]),
    }
    try:
        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if header:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"[WS] Ошибка записи свечи в файл для {symbol}: {e}")

    if symbol not in klines_buffer:
        klines_buffer[symbol] = []
    klines_buffer[symbol].append(row)
    if len(klines_buffer[symbol]) > 1000:
        klines_buffer[symbol] = klines_buffer[symbol][-1000:]

def save_ticker_snapshot(symbol, ticker):
    filename = os.path.join(TICKER_CSV_PATH, f"{symbol}_ticker.csv")
    header = not os.path.exists(filename)
    row = {
        "timestamp": int(ticker.get("ts", 0)) // 1000 if "ts" in ticker else 0,
        "symbol": ticker.get("symbol", ""),
        "tickDirection": ticker.get("tickDirection", ""),
        "price24hPcnt": ticker.get("price24hPcnt", ""),
        "lastPrice": float(ticker.get("lastPrice", 0)) if ticker.get("lastPrice") not in (None, "") else 0.0,
        "prevPrice24h": float(ticker.get("prevPrice24h", 0)) if ticker.get("prevPrice24h") not in (None, "") else 0.0,
        "highPrice24h": float(ticker.get("highPrice24h", 0)) if ticker.get("highPrice24h") not in (None, "") else 0.0,
        "lowPrice24h": float(ticker.get("lowPrice24h", 0)) if ticker.get("lowPrice24h") not in (None, "") else 0.0,
        "prevPrice1h": float(ticker.get("prevPrice1h", 0)) if ticker.get("prevPrice1h") not in (None, "") else 0.0,
        "markPrice": float(ticker.get("markPrice", 0)) if ticker.get("markPrice") not in (None, "") else 0.0,
        "indexPrice": float(ticker.get("indexPrice", 0)) if ticker.get("indexPrice") not in (None, "") else 0.0,
        "openInterest": float(ticker.get("openInterest", 0)) if ticker.get("openInterest") not in (None, "") else 0.0,
        "openInterestValue": float(ticker.get("openInterestValue", 0)) if ticker.get("openInterestValue") not in (None, "") else 0.0,
        "turnover24h": float(ticker.get("turnover24h", 0)) if ticker.get("turnover24h") not in (None, "") else 0.0,
        "volume24h": float(ticker.get("volume24h", 0)) if ticker.get("volume24h") not in (None, "") else 0.0,
        "nextFundingTime": int(ticker.get("nextFundingTime", 0)) if ticker.get("nextFundingTime") not in (None, "") else 0,
        "fundingRate": float(ticker.get("fundingRate", 0)) if ticker.get("fundingRate") not in (None, "") else 0.0,
        "bid1Price": float(ticker.get("bid1Price", 0)) if ticker.get("bid1Price") not in (None, "") else 0.0,
        "bid1Size": float(ticker.get("bid1Size", 0)) if ticker.get("bid1Size") not in (None, "") else 0.0,
        "ask1Price": float(ticker.get("ask1Price", 0)) if ticker.get("ask1Price") not in (None, "") else 0.0,
        "ask1Size": float(ticker.get("ask1Size", 0)) if ticker.get("ask1Size") not in (None, "") else 0.0,
        "preOpenPrice": ticker.get("preOpenPrice", ""),
        "preQty": ticker.get("preQty", ""),
        "curPreListingPhase": ticker.get("curPreListingPhase", ""),
    }
    try:
        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if header:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"[WS] Ошибка записи тикера в файл для {symbol}: {e}")

    if symbol not in tickers_buffer:
        tickers_buffer[symbol] = []
    tickers_buffer[symbol].append(row)
    if len(tickers_buffer[symbol]) > 1000:
        tickers_buffer[symbol] = tickers_buffer[symbol][-1000:]

def save_trade_snapshot(symbol, trade):
    filename = os.path.join(TRADE_CSV_PATH, f"{symbol}_trades.csv")
    header = not os.path.exists(filename)
    row = {
        "timestamp": int(trade.get("T", 0)) // 1000 if "T" in trade else 0,
        "price": float(trade.get("price", 0)) if trade.get("price") not in (None, "") else 0.0,
        "size": float(trade.get("size", 0)) if trade.get("size") not in (None, "") else 0.0,
        "side": trade.get("side", ""),
        "tradeId": trade.get("tradeId", ""),
    }
    try:
        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if header:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"[WS] Ошибка записи трейда в файл для {symbol}: {e}")

    if symbol not in trades_buffer:
        trades_buffer[symbol] = []
    trades_buffer[symbol].append(row)
    if len(trades_buffer[symbol]) > 1000:
        trades_buffer[symbol] = trades_buffer[symbol][-1000:]

def save_orderbook_snapshot(symbol, orderbook):
    filename = os.path.join(ORDERBOOK_CSV_PATH, f"{symbol}_orderbook.csv")
    header = not os.path.exists(filename)
    row = {
        "timestamp": int(orderbook.get("ts", 0)) // 1000 if "ts" in orderbook else 0,
        "bids": json.dumps(orderbook.get("b", [])),
        "asks": json.dumps(orderbook.get("a", [])),
    }
    try:
        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if header:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"[WS] Ошибка записи стакана в файл для {symbol}: {e}")

    if symbol not in orderbook_buffer:
        orderbook_buffer[symbol] = []
    orderbook_buffer[symbol].append(row)
    if len(orderbook_buffer[symbol]) > 100:
        orderbook_buffer[symbol] = orderbook_buffer[symbol][-100:]

def get_dynamic_timeout(interval):
    try:
        int_interval = int(interval)
        return int_interval * 60 * 1.15
    except:
        if interval == "D":
            return 86400 * 1.15
        if interval == "W":
            return 604800 * 1.15
        return 900

async def kline_ws_worker_multi_async(symbols, timeframe="15m", stop_event=None):
    interval = timeframe_to_ws_interval(timeframe)
    ws_url = "wss://stream.bybit.com/v5/public/linear"
    blacklist = set()
    timeout = get_dynamic_timeout(interval)
    while not (stop_event and stop_event.is_set()):
        sub_symbols = [s for s in symbols if s not in blacklist]
        if not sub_symbols:
            print("[WS] Нет валидных пар для подписки, поток остановлен.")
            break
        try:
            async with websockets.connect(ws_url, ping_interval=10, ping_timeout=5) as ws:
                args = []
                args += [f"kline.{interval}.{s}" for s in sub_symbols]
                args += [f"tickers.{s}" for s in sub_symbols]
                args += [f"publicTrade.{s}" for s in sub_symbols]
                args += [f"orderbook.1.{s}" for s in sub_symbols]
                sub_msg = json.dumps({"op": "subscribe", "args": args})
                await ws.send(sub_msg)
                print(f"[WS] Подключён к каналам: {args}")

                while not (stop_event and stop_event.is_set()):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        data = json.loads(msg)
                        print(f"[WS] Raw message: {data}")
                        # Ошибки подписки
                        if "error" in data and "topic" in data:
                            bad_topic = data["topic"]
                            print(f"[WS] Ошибка подписки: {bad_topic} — в черный список!")
                            bad_symbol = bad_topic.split(".")[-1]
                            blacklist.add(bad_symbol)
                            break
                        if "success" in data and not data["success"]:
                            bad_topic = data.get("ret_msg", "")
                            print(f"[WS] Ошибка подписки: {bad_topic}")
                            if "topic:" in bad_topic:
                                bad_symbol = bad_topic.split("topic:")[-1].split(".")[-1]
                                blacklist.add(bad_symbol)
                            continue
                        # KLINES
                        if "topic" in data and data["topic"].startswith("kline"):
                            topic = data["topic"]
                            symbol = topic.split(".")[-1]
                            kline_list = data.get("data", [])
                            for kline in kline_list:
                                save_kline_snapshot(symbol, kline)
                                print(f"[WS] KLINE {symbol}: {kline}")
                        # TICKERS (Bybit v5: "snapshot" и "delta" имеют разный набор полей)
                        elif "topic" in data and data["topic"].startswith("tickers"):
                            topic = data["topic"]
                            symbol = topic.split(".")[-1]
                            # snapshot/делта для v5
                            if data.get("type") == "snapshot":
                                ticker = data.get("data", {})
                                if isinstance(ticker, list) and len(ticker) > 0:
                                    # На некоторых рынках Bybit присылает list из 1 dict
                                    ticker = ticker[0]
                                last_ticker_state[symbol] = ticker.copy()
                                save_ticker_snapshot(symbol, ticker)
                                print(f"[WS] TICKER {symbol}: {ticker}")
                            elif data.get("type") == "delta":
                                delta = data.get("data", {})
                                if symbol in last_ticker_state:
                                    last_ticker_state[symbol].update(delta)
                                    save_ticker_snapshot(symbol, last_ticker_state[symbol])
                                    print(f"[WS] TICKER {symbol}: {last_ticker_state[symbol]}")
                                else:
                                    print(f"[WS] Delta до snapshot для {symbol}: {delta}")
                        # TRADES
                        elif "topic" in data and data["topic"].startswith("publicTrade"):
                            topic = data["topic"]
                            symbol = topic.split(".")[-1]
                            trades = data.get("data", [])
                            for trade in trades:
                                save_trade_snapshot(symbol, trade)
                                print(f"[WS] TRADE {symbol}: {trade}")
                        # ORDERBOOK
                        elif "topic" in data and data["topic"].startswith("orderbook"):
                            topic = data["topic"]
                            symbol = topic.split(".")[-1]
                            orderbook = data.get("data", {})
                            save_orderbook_snapshot(symbol, orderbook)
                            print(f"[WS] ORDERBOOK {symbol}: {orderbook}")
                    except asyncio.TimeoutError:
                        print(f"[WS] Timeout ожидания сообщения ({timeout} сек), переподключение...")
                        break
                    except Exception as e:
                        print(f"[WS] WebSocket message error: {e}")
                        break
        except Exception as e:
            print(f"[WS] Ошибка подключения: {e}")
        if stop_event and stop_event.is_set():
            break
        await asyncio.sleep(1)

def websocket_collector_process(symbols, timeframe="15m", stop_event=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(kline_ws_worker_multi_async(symbols, timeframe, stop_event))
    finally:
        loop.close()

def start_websocket_collector_proc(symbols, timeframe="15m"):
    stop_event = Event()
    p = Process(target=websocket_collector_process, args=(symbols, timeframe, stop_event))
    p.start()
    print(f"[WS-PROC] Процесс WebSocket collector запущен с pid={p.pid}")
    return p, stop_event

def get_last_n_klines(symbol, n=100):
    if symbol in klines_buffer:
        return klines_buffer[symbol][-n:]
    return []

def get_last_n_tickers(symbol, n=100):
    if symbol in tickers_buffer:
        return tickers_buffer[symbol][-n:]
    return []

def get_last_n_trades(symbol, n=100):
    if symbol in trades_buffer:
        return trades_buffer[symbol][-n:]
    return []

def get_last_n_orderbooks(symbol, n=10):
    if symbol in orderbook_buffer:
        return orderbook_buffer[symbol][-n:]
    return []