import os
import json
import csv
import asyncio
import websockets
from multiprocessing import Process, Event

KLINE_CSV_PATH = "/root/my_emacross_bot/bybit_futures_data_multi_tf/klines"
os.makedirs(KLINE_CSV_PATH, exist_ok=True)

def save_kline_snapshot(symbol, kline):
    filename = os.path.join(KLINE_CSV_PATH, f"{symbol}_kline.csv")
    header = not os.path.exists(filename)
    row = {
        "timestamp": int(kline[0]) // 1000,
        "open": float(kline[1]),
        "high": float(kline[2]),
        "low": float(kline[3]),
        "close": float(kline[4]),
        "volume": float(kline[5]),
        "turnover": float(kline[6]),
    }
    try:
        with open(filename, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if header:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"[WS] Ошибка записи свечи в файл для {symbol}: {e}")

async def kline_ws_worker_multi_async(symbols, interval="15", stop_event=None):
    ws_url = "wss://stream.bybit.com/v5/public/linear"
    blacklist = set()
    while not (stop_event and stop_event.is_set()):
        sub_symbols = [s for s in symbols if s not in blacklist]
        if not sub_symbols:
            print("[WS] Нет валидных пар для подписки, поток остановлен.")
            break
        try:
            async with websockets.connect(ws_url, ping_interval=10, ping_timeout=5) as ws:
                args = [f"kline.{interval}.{s}" for s in sub_symbols]
                sub_msg = json.dumps({"op": "subscribe", "args": args})
                await ws.send(sub_msg)
                print(f"[WS] Подключён к kline пар: {sub_symbols}")

                while not (stop_event and stop_event.is_set()):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=15)
                        data = json.loads(msg)
                        # Обработка ошибок подписки
                        if "error" in data and "topic" in data:
                            bad_topic = data["topic"]
                            print(f"[WS] Ошибка подписки: {bad_topic} — в черный список!")
                            bad_symbol = bad_topic.split(".")[-1]
                            blacklist.add(bad_symbol)
                            break
                        # Получение свечей
                        if "topic" in data and data["topic"].startswith("kline"):
                            topic = data["topic"]
                            symbol = topic.split(".")[-1]
                            kline_data = data.get("data", {})
                            if isinstance(kline_data, dict) and "kline" in kline_data:
                                kline = kline_data["kline"]
                                save_kline_snapshot(symbol, [
                                    kline.get("start"),
                                    kline.get("open"),
                                    kline.get("high"),
                                    kline.get("low"),
                                    kline.get("close"),
                                    kline.get("volume"),
                                    kline.get("turnover"),
                                ])
                                print(f"[WS] KLINE {symbol}: {[kline.get('start'), kline.get('open'), kline.get('high'), kline.get('low'), kline.get('close'), kline.get('volume'), kline.get('turnover')]}")
                    except asyncio.TimeoutError:
                        print("[WS] Timeout ожидания сообщения, переподключение...")
                        break
                    except Exception as e:
                        print(f"[WS] WebSocket message error: {e}")
                        break
        except Exception as e:
            print(f"[WS] Ошибка подключения: {e}")
        if stop_event and stop_event.is_set():
            break
        await asyncio.sleep(1)

def websocket_collector_process(symbols, interval="15", stop_event=None):
    # Для совместимости с multiprocessing запускать event loop здесь
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(kline_ws_worker_multi_async(symbols, interval, stop_event))
    finally:
        loop.close()

def start_websocket_collector_proc(symbols, interval="15"):
    stop_event = Event()
    p = Process(target=websocket_collector_process, args=(symbols, interval, stop_event))
    p.start()
    print(f"[WS-PROC] Процесс WebSocket collector запущен с pid={p.pid}")
    return p, stop_event
