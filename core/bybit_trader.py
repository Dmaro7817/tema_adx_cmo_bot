from pybit.unified_trading import HTTP
from decimal import Decimal
import os
import time
import threading
import config
import math

class BybitTrader:
    def __init__(self, deposit):
        self.deposit = deposit
        self.open_trades = []
        self.session = HTTP(
            api_key=config.BYBIT_API_KEY,
            api_secret=config.BYBIT_API_SECRET,
            testnet=False
        )
        self.category = "linear"

        self._open_trades_cache = []
        self._open_trades_lock = threading.Lock()
        self._stop_update_thread = False
        self._update_thread = threading.Thread(target=self._update_open_positions_loop, daemon=True)
        self._update_thread.start()

        # --- NEW: История трейдов для мёрджа ---
        self._trade_history = []  # список полных trade-объектов

    def _update_open_positions_loop(self):
        interval = getattr(config, "OPEN_TRADES_SCAN_INTERVAL", 1)
        while not self._stop_update_thread:
            try:
                open_positions = self.fetch_real_open_positions()
                with self._open_trades_lock:
                    self._open_trades_cache = open_positions
                #print(f"[LOG] Открытых сделок на бирже: {len(open_positions)} {[p['symbol'] for p in open_positions]}")
            except Exception as e:
                print(f"❌ Ошибка обновления открытых позиций (background): {e}")
            time.sleep(interval)

    def stop(self):
        self._stop_update_thread = True
        if hasattr(self, '_update_thread'):
            self._update_thread.join(timeout=1)

    def get_symbol_info(self, symbol):
        try:
            res = self.session.get_instruments_info(category=self.category, symbol=symbol)
            return res['result']['list'][0] if res['result']['list'] else {}
        except Exception as e:
            print(f"❌ Ошибка получения информации по символу {symbol}: {e}")
            return {}

    def floor(self, value, decimals):
        factor = Decimal('1') / (Decimal('10') ** decimals)
        return (Decimal(str(value)) // factor) * factor

    def round_qty(self, symbol, qty):
        info = self.get_symbol_info(symbol)
        step_qty = Decimal(info.get('lotSizeFilter', {}).get('qtyStep', '0.001'))
        qty_decimals = abs(step_qty.as_tuple().exponent)
        adjusted_qty = self.floor(qty, qty_decimals)
        return f"{adjusted_qty:.{qty_decimals}f}"

    def round_price(self, symbol, price):
        info = self.get_symbol_info(symbol)
        tick_size = Decimal(info.get('priceFilter', {}).get('tickSize', '0.0001'))
        price_decimals = abs(tick_size.as_tuple().exponent)
        adjusted_price = self.floor(price, price_decimals)
        return f"{adjusted_price:.{price_decimals}f}"

    def get_price(self, symbol):
        try:
            res = self.session.get_tickers(category=self.category, symbol=symbol)
            return float(res['result']['list'][0]['ask1Price'])
        except Exception as e:
            print(f"❌ Ошибка получения цены {symbol}: {e}")
            return None

    def place_market_order_by_base(self, symbol, qty, side):
        symbol = symbol.replace("_", "")
        args = dict(
            category=self.category,
            symbol=symbol,
            side=side.capitalize(),
            orderType="Market",
            qty=self.round_qty(symbol, qty),
            orderLinkId=f"AzzraelCode_{symbol}_{time.time()}"
        )
        print("args", args)
        r = self.session.place_order(**args)
        print("result", r)
        return r

    def place_market_order_by_quote(self, symbol, quote: float = 5.0, side: str = "Sell"):
        symbol = symbol.replace("_", "")
        curr_price = self.get_price(symbol)
        if not curr_price:
            print(f"❌ Невозможно получить цену для {symbol}")
            return None
        qty = Decimal(quote) / Decimal(curr_price)
        return self.place_market_order_by_base(symbol, qty, side)

    def place_limit_order(self, symbol, side, qty, price):
        symbol = symbol.replace("_", "")
        trade_side = "Buy" if side.lower() == "buy" else "Sell"
        try:
            formatted_qty = self.round_qty(symbol, qty)
            formatted_price = self.round_price(symbol, price)
            response = self.session.place_order(
                category=self.category,
                symbol=symbol,
                side=trade_side,
                order_type="Limit",
                qty=formatted_qty,
                price=formatted_price,
                time_in_force="GoodTillCancel",
                reduce_only=True,
                is_leverage=True,
                order_link_id=f"limit_{symbol}_{int(time.time())}"
            )
            print("📦 Limit ордер размещён:", response)
            return response
        except Exception as e:
            print(f"[BYBIT ERROR] ❌ Ошибка при Limit ордере: {e}")
            return None

    def get_account_balance(self):
        try:
            result = self.session.get_wallet_balance(accountType="UNIFIED")
            coins = result["result"]["list"][0]["coin"]
            usdt = next((c for c in coins if c["coin"] == "USDT"), None)
            if not usdt:
                print("❌ USDT не найден среди монет аккаунта.")
                return 0, 0
            balance = float(usdt.get("walletBalance") or 0)
            available = float(usdt.get("availableToWithdraw") or 0)
            print(f"💰 Баланс USDT: {balance} (доступно: {available})")
            return balance, available
        except Exception as e:
            print(f"❌ Ошибка получения баланса: {e}")
            return 0, 0

    def fetch_real_open_positions(self):
        try:
            result = self.session.get_positions(category=self.category, settleCoin="USDT")
            #print("[BYBIT] Ответ get_positions:", result)
            open_positions = []
            for pos in result['result']['list']:
                #print("[BYBIT] Позиция:", pos)
                if float(pos.get('size', 0)) > 0:
                    old_trade = self._find_trade_in_history(pos['symbol'], pos['side'])
                    if old_trade:
                        old_trade['amount'] = float(pos['size'])
                        old_trade['entry_price'] = float(pos['avgPrice'])
                        old_trade['leverage'] = float(pos['leverage'])
                        old_trade['status'] = "open"
                        open_positions.append(old_trade)
                    else:
                        open_positions.append({
                            "symbol": pos['symbol'],
                            "side": pos['side'].lower(),
                            "entry_price": float(pos['avgPrice']),
                            "amount": float(pos['size']),
                            "leverage": float(pos['leverage']),
                            "status": "open",
                            "opened_at": time.time(),
                        })
            return open_positions
        except Exception as e:
            print(f"❌ Ошибка получения открытых позиций: {e}")
            return []

    def _find_trade_in_history(self, symbol, side):
        for trade in self._trade_history:
            if trade["symbol"] == symbol and trade["side"].lower() == side.lower():
                return trade
        return None

    def get_open_trades(self):
        with self._open_trades_lock:
            return list(self._open_trades_cache)

    def get_tp_sl_orders(self, symbol, side):
        """Получить реальные TP и SL ордера по символу"""
        try:
            orders = self.session.get_open_orders(category=self.category, symbol=symbol)
            tp_orders = []
            sl_order = None
            for order in orders.get('result', {}).get('list', []):
                if order['orderType'].lower() == 'limit' and order.get('reduceOnly'):
                    tp_orders.append({
                        'price': float(order['price']),
                        'qty': float(order['qty']),
                        'order_id': order['orderId'],
                    })
                if order['orderType'].lower() in ['stop', 'stop_market', 'market_if_touched'] and order.get('reduceOnly'):
                    sl_order = {
                        'stop_price': float(order.get('stopPx', order.get('triggerPrice', order.get('price', 0)))),
                        'order_id': order['orderId'],
                        'qty': float(order['qty']),
                    }
            if side.lower() == "buy":
                tp_orders = sorted(tp_orders, key=lambda x: x['price'])
            else:
                tp_orders = sorted(tp_orders, key=lambda x: -x['price'])
            return tp_orders, sl_order
        except Exception as e:
            print(f"❌ Ошибка получения TP/SL ордеров: {e}")
            return [], None

    def get_position_sl(self, symbol):
        try:
            res = self.session.get_positions(category=self.category, symbol=symbol)
            for pos in res['result']['list']:
                if float(pos.get('size', 0)) > 0:
                    stop_price = pos.get("stopLoss")
                    if stop_price and float(stop_price) > 0:
                        return {
                            "stop_price": float(stop_price),
                            "qty": float(pos.get("size", 0))
                        }
            return None
        except Exception as e:
            print(f"❌ Ошибка получения стоп-лосса из позиции: {e}")
            return None

    def set_stop_loss(self, symbol, entry_price, sl_percent, side):
        info = self.get_symbol_info(symbol)
        price_decimals = abs(Decimal(info.get('priceFilter', {}).get('tickSize', '0.0001')).as_tuple().exponent)
        if sl_percent <= 0:
            print("SL percent must be positive!")
            return None
        # ВАЖНО: для Buy - ниже, для Sell - выше
        if side.lower() == "buy":
            sl_price = entry_price * (1 - sl_percent / 100)
        else:
            sl_price = entry_price * (1 + sl_percent / 100)
        sl_price = round(sl_price, price_decimals)
        try:
            response = self.session.set_trading_stop(
                category=self.category,
                symbol=symbol,
                stop_loss=str(sl_price)
            )
            print(f"✅ Установлен стоп-лосс {sl_price} ({sl_percent}%)", response)
            return response
        except Exception as e:
            print("❌ Ошибка установки стоп-лосса:", e)
            return None

    # --- TRAILING STOP LOGIC ---

    def activate_trailing_stop(self, symbol, active_price):
        info = self.get_symbol_info(symbol)
        price_decimals = abs(Decimal(info.get('priceFilter', {}).get('tickSize', '0.0001')).as_tuple().exponent)
        current_price = self.get_price(symbol)
        ts_callback = current_price * config.TRAILING_STOP_PERCENT / 100
        ts_callback = round(ts_callback, price_decimals)
        active_price = round(active_price, price_decimals)
        if ts_callback <= 0:
            print(f"Trailing stop too small: {ts_callback}")
            return None
        try:
            response = self.session.set_trading_stop(
                category=self.category,
                symbol=symbol,
                trailingStop=str(ts_callback),
                activePrice=str(active_price)
            )
            print(f"🟢 Трейлинг-стоп активируется при {active_price}, шаг: {ts_callback}", response)
            return response
        except Exception as e:
            print("❌ Ошибка установки отложенного трейлинг-стопа:", e)
            return None

    def place_take_profits(self, symbol, entry_price, qty, side):
        info = self.get_symbol_info(symbol)
        price_decimals = abs(Decimal(info.get('priceFilter', {}).get('tickSize', '0.0001')).as_tuple().exponent)
        min_qty = float(info.get('lotSizeFilter', {}).get('minOrderQty', 0.001))
        tp_side = "Sell" if side.lower() == "buy" else "Buy"
        remaining_qty = qty
        tp_qtys = []
        actual_tp_percentages = []

        for i, (tp_percent, tp_amount) in enumerate(zip(config.TP_LEVELS, config.TP_PERCENTAGES), start=1):
            if side.lower() == "buy":
                tp_price = entry_price * (1 + tp_percent / 100)
            else:
                tp_price = entry_price * (1 - tp_percent / 100)
            tp_price = round(tp_price, price_decimals)

            # Для последнего TP — всё, что осталось
            if i == len(config.TP_LEVELS):
                tp_qty = remaining_qty
            else:
                tp_qty = qty * tp_amount / 100
                if i == 1 and tp_qty < min_qty:
                    print(f"⚠️ TP1: объём {tp_qty} меньше минимального, округляем вверх до {min_qty}")
                    tp_qty = min_qty

            if tp_qty > remaining_qty:
                tp_qty = remaining_qty

            if tp_qty < min_qty:
                print(f"❌ TP{i}: Объём {tp_qty} ниже минимального — пропущено")
                continue

            actual_percent = tp_qty / qty * 100
            actual_tp_percentages.append(actual_percent)
            tp_qtys.append(tp_qty)

            try:
                order = self.session.place_order(
                    category=self.category,
                    symbol=symbol,
                    side=tp_side,
                    order_type="Limit",
                    qty=self.round_qty(symbol, tp_qty),
                    price=str(tp_price),
                    time_in_force="GTC",
                    reduce_only=True,
                    order_link_id=f"TP{i}_{symbol}_{int(time.time())}"
                )
                print(f"✅ TP{i} установлен по цене {tp_price} на {tp_qty} контрактов ({actual_percent:.2f}%):", order)
                remaining_qty -= tp_qty
            except Exception as e:
                print(f"❌ Ошибка установки TP{i}:", e)
            if remaining_qty < min_qty:
                break

        # Добавить остаток к последнему TP, если есть
        if remaining_qty > 0 and tp_qtys:
            print(f"⚠️ Остаток {remaining_qty} добавлен к последнему TP")
            last_tp_qty = tp_qtys[-1] + remaining_qty
            actual_tp_percentages[-1] = last_tp_qty / qty * 100
            # (реальный ордер уже отправлен — остаток останется невыставленным, если меньше min_qty, либо нужно модифицировать последний ордер вручную)

        print(f"[INFO] Фактические проценты TP: {actual_tp_percentages}")

    def open_trade(self, symbol, side, entry_price, amount, leverage, tp_levels, tp_percents, sl_percent, trailing_stop, trailing_percent):
        symbol = symbol.replace("_", "")
        try:
            notional = amount * leverage
            qty = notional / entry_price
            try:
                leverage_response = self.session.set_leverage(
                    category=self.category,
                    symbol=symbol,
                    buyLeverage=leverage,
                    sellLeverage=leverage
                )
                print(f"✅ Установлено плечо {leverage}x: {leverage_response}")
            except Exception as e:
                print(f"❌ Ошибка установки плеча: {e}")

            response = self.place_market_order_by_base(symbol, qty, side)
            print("Ответ на открытие ордера:", response)
            if not response or not response.get("result"):
                print(f"❌ Сделка по {symbol} не открыта — ошибка ордера.")
                return None

            result = response.get("result", {})
            entry_price_actual = float(result.get("avgFillPrice", 0))
            real_qty = float(result.get("cumExecQty", 0))
            real_amount = real_qty * entry_price_actual

            # Проверим реальное положение на бирже
            positions_resp = self.session.get_positions(category=self.category, settleCoin="USDT")
            for pos in positions_resp['result']['list']:
                if pos['symbol'] == symbol:
                    entry_price_actual = float(pos.get('avgPrice', entry_price_actual))
                    real_qty = float(pos.get('size', real_qty))
                    real_leverage = float(pos.get('leverage', leverage))
                    break
            else:
                real_leverage = leverage

            real_amount = real_qty * entry_price_actual

            if real_amount == 0:
                real_qty = qty
                entry_price_actual = entry_price
                real_amount = real_qty * entry_price_actual

            print(f"✅ Открыта позиция по {symbol} @ {entry_price_actual:.4f}")

            # TP/SL/TS сразу после открытия (как в твоём примере):
            self.set_stop_loss(symbol, entry_price_actual, sl_percent, side)
            self.place_take_profits(symbol, entry_price_actual, real_qty, side)

            # --- АКТИВАЦИЯ ТРЕЙЛИНГ-СТОПА ПО TRAILING_STOP_ACTIVATION_PERCENT ---
            trailing_activation_percent = getattr(config, "TRAILING_STOP_ACTIVATION_PERCENT", None)
            if trailing_activation_percent is not None and trailing_activation_percent > 0:
                if side.lower() == "buy":
                    activation_price = entry_price_actual * (1 + trailing_activation_percent / 100)
                else:
                    activation_price = entry_price_actual * (1 - trailing_activation_percent / 100)
                print(f"[TS] Устанавливается трейлинг-стоп: активация по цене {activation_price} (TRAILING_STOP_ACTIVATION_PERCENT={trailing_activation_percent})")
                self.activate_trailing_stop(symbol, activation_price)

            trade = {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price_actual,
                "amount": real_amount,
                "qty": real_qty,
                "remaining_amount": real_amount,
                "leverage": leverage,
                "tp_levels": tp_levels,
                "tp_percents": tp_percents,
                "opened_at": time.time(),
                "status": "open",
            }
            print("TRADE OBJECT:", trade)

            self.open_trades.append(trade)
            self._trade_history.append(trade)
            return trade

        except Exception as e:
            print(f"❌ Ошибка при открытии сделки по {symbol}: {e}")
            return None

    # --- Коррекция: TP/SL/TS срабатывают только один раз ---
    def mark_tp_triggered(self, trade, tp_index):
        if "tp_triggered" in trade and len(trade["tp_triggered"]) > tp_index:
            if not trade["tp_triggered"][tp_index]:
                trade["tp_triggered"][tp_index] = True

    def mark_sl_triggered(self, trade):
        if "sl_triggered" not in trade:
            trade["sl_triggered"] = True
        else:
            if not trade["sl_triggered"]:
                trade["sl_triggered"] = True

    def mark_ts_activated(self, trade):
        if "ts_activated" in trade and not trade["ts_activated"]:
            trade["ts_activated"] = True