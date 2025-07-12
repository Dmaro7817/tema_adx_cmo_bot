import os
from time import sleep
from multiprocessing import Process, Event
from pybit.unified_trading import WebSocket
from dotenv import load_dotenv

def handle_private_message(msg):
    # Флаг для однократного вывода сообщения о получении первого приватного сообщения
    if not hasattr(handle_private_message, "shown_connected_msg"):
        handle_private_message.shown_connected_msg = True
        print("[WS-PRIVATE] Получено первое приватное сообщение от Bybit!", flush=True)

    # Показываем баланс, если пришло сообщение wallet (USDT)
    if msg.get("topic", "").startswith("wallet"):
        try:
            balances = msg["data"]["wallet"]["balance"]
            usdt_info = balances.get("USDT", {})
            usdt_balance = usdt_info.get("walletBalance") or usdt_info.get("equity")
            print(f"[WS-PRIVATE] Баланс USDT: {usdt_balance}", flush=True)
        except Exception:
            pass

    # Показываем открытые позиции
    if msg.get("topic", "").startswith("position"):
        try:
            positions = msg["data"]["position"]
            open_positions = [p for p in positions if float(p.get("size", 0)) != 0]
            print(f"[WS-PRIVATE] Открытых позиций: {len(open_positions)}", flush=True)
            if open_positions:
                pairs = [p.get("symbol") for p in open_positions]
                print(f"[WS-PRIVATE] Пары с открытыми позициями: {pairs}", flush=True)
        except Exception:
            pass

def websocket_private_process(api_key, api_secret, stop_event=None):
    print("[WS-PRIVATE] Приватный процесс стартовал", flush=True)
    print(f"[WS-PRIVATE] api_key: {api_key}, api_secret: {'*' * len(api_secret) if api_secret else None}", flush=True)
    ws_private = WebSocket(
        testnet=False,
        channel_type="private",
        api_key=api_key,
        api_secret=api_secret,
        callback_function=handle_private_message
    )
    print("[WS-PRIVATE] Бот подключен к кабинету (Bybit Private WebSocket) — соединение установлено", flush=True)
    ws_private.position_stream(callback=handle_private_message)
    ws_private.order_stream(callback=handle_private_message)
    ws_private.wallet_stream(callback=handle_private_message)
    try:
        while not (stop_event and stop_event.is_set()):
            sleep(1)
    except KeyboardInterrupt:
        pass

def start_websocket_private_proc(api_key=None, api_secret=None):
    if not api_key:
        api_key = os.getenv("BYBIT_API_KEY")
    if not api_secret:
        api_secret = os.getenv("BYBIT_API_SECRET")
    stop_event = Event()
    p = Process(target=websocket_private_process, args=(api_key, api_secret, stop_event))
    p.start()
    print(f"[WS-PRIVATE-PROC] Приватный WebSocket процесс запущен, pid={p.pid}", flush=True)
    return p, stop_event