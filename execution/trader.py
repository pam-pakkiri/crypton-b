import time
import pandas as pd
from execution.binance_client import BinanceClient
from strategies.base_strategy import BaseStrategy
from execution.risk_manager import RiskManager

class LiveTrader:
    def __init__(self, client: BinanceClient, strategy: BaseStrategy, risk_manager: RiskManager, symbol='BTC/USDT', timeframe='1h'):
        self.client = client
        self.strategy = strategy
        self.rm = risk_manager
        self.symbol = symbol
        self.timeframe = timeframe
        self.position = 0 # Track current position
        self.running = False 
        self.leverage = 5
        self.margin_mode = 'isolated'
        # Management Config (from MQ5)
        self.use_trailing_stop = True
        self.trailing_stop_atr_mult = 1.5 # Distance in ATR
        self.trailing_step_atr_mult = 0.5 # Step in ATR
        self.use_breakeven = True
        self.breakeven_trigger_atr_mult = 2.0 # Profit in ATR to trigger BE
        self.breakeven_trigger_atr_mult = 2.0 # Profit in ATR to trigger BE
        self.active_sl_order_id = None # Track the current SL order to replace it
        self.last_atr = 0.0

    def start(self, interval=60):
        print(f"Starting Futures Trader for {self.symbol}...")
        self.running = True
        
        while self.running:
            # Re-apply settings only if they changed or on first run
            try:
                # Optimized: We could track 'last_set_leverage' to avoid spamming the API
                # but a simple try/except handles the 'open position' restriction gracefully.
                self.client.set_margin_mode(self.symbol, self.margin_mode)
                self.client.set_leverage(self.symbol, self.leverage)
            except Exception as e:
                # Log only if it's NOT the common 'open position' leverage error
                if "-4161" not in str(e):
                    print(f"Note on leverage/margin sync: {e}")
            
            try:
                # 1. Fetch latest data (Need high limit for EMA 600)
                df = self.client.fetch_ohlcv(self.symbol, self.timeframe, limit=1000)
                if df is None:
                    print("Error fetching data. Retrying in 10s...")
                    time.sleep(10)
                    continue

                # 2. Generate Signal
                signal_dict = self.strategy.generate_signal(df)
                signal_type = signal_dict['type']
                price = signal_dict['price']
                reason = signal_dict.get('reason', 'N/A')

                print(f"[Heartbeat] {pd.Timestamp.now()} | {self.symbol} | Price: {price} | Signal: {signal_type} | Reason: {reason}")

                # 3. Manage Active Positions (Trailing Stop / BE)
                self.manage_active_positions(price, signal_dict.get('atr', 0))

                # 4. Execute Trade
                if signal_type != 'HOLD':
                    print(f"\n>> SIGNAL DETECTED: {signal_type} ({reason})")
                    self.execute_trade(signal_dict)

                # Wait loop
                time.sleep(interval)
            except KeyboardInterrupt:
                print("Stopping Trader...")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(10)
        
        print("Trader loop exited.")

    def stop(self):
        print("Stopping Trader...")
        self.running = False

    def execute_trade(self, signal_dict):
        signal = signal_dict['type']
        price = signal_dict['price']
        sl_price = signal_dict.get('sl')
        tp1_price = signal_dict.get('tp1')
        
        # 0. Fetch Real Balance for Risk Calculation
        current_balance = 0
        try:
            bal_data = self.client.get_balance()
            if bal_data and 'total' in bal_data:
                current_balance = bal_data['total'].get('USDT', 0)
        except Exception as e:
            print(f"Error fetching balance for risk calculation: {e}")
            
        if current_balance == 0:
             # Fallback to hardcoded or fail? Let's fail safe
             print("Warning: Could not fetch balance. Using default risk calculation.")
             current_balance = self.rm.account_size
        
        # 1. Calculate Position Size
        step_size = getattr(self.strategy, 'quantity_step', 0.001)
        size = self.rm.calculate_position_size(price, sl_price, custom_account_size=current_balance, step_size=step_size)
        print(f"Calculated Position Size for risk {self.rm.risk_per_trade*100}% of {current_balance} USDT: {size}")
        
        if size <= 0:
            print("Size too small. Skipping trade.")
            return

        # 2. Execute Entry
        side = 'buy' if signal == 'BUY' else 'sell'
        
        # Fetch current position from exchange to manage opposite signals
        try:
            exchange_pos = self.client.get_positions()
            symbol_nopslash = self.symbol.replace('/', '')
            current_p = next((p for p in exchange_pos if p['symbol'] == symbol_nopslash), None)
            
            if current_p and float(current_p['size']) != 0:
                current_side = 'buy' if float(current_p['size']) > 0 else 'sell'
                if current_side != side:
                    print(f"Opposite signal detected ({signal}). Closing existing {current_side.upper()} position.")
                    # Close existing position
                    close_side = 'sell' if current_side == 'buy' else 'buy'
                    self.client.create_order(self.symbol, 'market', close_side, abs(float(current_p['size'])))
                    # Cancel all open orders for this symbol
                    self.client.cancel_all_orders(self.symbol)
                else:
                    print(f"Already have a {current_side.upper()} position in {self.symbol}. Skipping entry.")
                    return
        except Exception as e:
            print(f"Note on position check: {e}")

        print(f"Executing {side.upper()} order for {size} {self.symbol}...")
        order = self.client.create_order(self.symbol, 'market', side, size)
        
        if order:
            oid = order.get('orderId') or order.get('id')
            print(f"Entry Order Filled: {oid}")
            
            # 3. Place Stop Loss (Trigger Order)
            if sl_price:
                sl_side = 'sell' if side == 'buy' else 'buy'
                params = {'stopPrice': sl_price}
                print(f"Placing initial Stop Loss at {sl_price}...")
                sl_res = self.client.create_order(self.symbol, 'stop_market', sl_side, size, params=params)
                if sl_res:
                    self.active_sl_order_id = sl_res.get('orderId') or sl_res.get('id')
                
            # 4. Place Take Profit (Limit Order)
            if tp1_price:
                tp_side = 'sell' if side == 'buy' else 'buy'
                print(f"Placing Take Profit at {tp1_price}...")
                self.client.create_order(self.symbol, 'limit', tp_side, size, price=tp1_price)
        else:
            print("Order Placement Failed.")

    def manage_active_positions(self, current_price, current_atr):
        """
        Monitors active positions and updates SL for trailing or breakeven.
        """
        self.last_atr = current_atr
        try:
            exchange_pos = self.client.get_positions()
            symbol_nopslash = self.symbol.replace('/', '')
            pos = next((p for p in exchange_pos if p['symbol'] == symbol_nopslash), None)
            
            if not pos or float(pos['size']) == 0:
                self.active_sl_order_id = None
                return

            size = abs(float(pos['size']))
            side = 'long' if float(pos['size']) > 0 else 'short'
            entry_price = float(pos['entryPrice'])
            
            # Fetch current SL order
            open_orders = self.client.get_open_orders(self.symbol)
            sl_order = next((o for o in open_orders if o.get('type') == 'STOP_MARKET'), None)
            
            # If no SL exists, create an initial one (Self-healing)
            if not sl_order:
                print(f"No active SL found for {self.symbol}. Creating initial SL protection...")
                
                # Default SL calculation
                if current_atr > 0:
                    sl_dist = current_atr * 2.0
                else:
                    # Fallback to 2% if ATR not ready
                    sl_dist = entry_price * 0.02
                    
                initial_sl = entry_price - sl_dist if side == 'long' else entry_price + sl_dist
                initial_sl = round(initial_sl, 2)
                
                print(f"Calculated Initial SL: {initial_sl} (Entry: {entry_price}, ATR: {current_atr})")
                
                sl_side = 'sell' if side == 'long' else 'buy'
                
                # IMPORTANT: Set reduceOnly to true for SL closing orders
                params = {
                    'stopPrice': initial_sl,
                    'reduceOnly': 'true'
                }
                
                res = self.client.create_order(self.symbol, 'STOP_MARKET', sl_side, size, params=params)
                if res:
                    print(f"Initial SL Order Created: {res.get('orderId')}")
                    self.active_sl_order_id = res.get('orderId')
                    sl_order = res
                    sl_order['stopPrice'] = initial_sl 
                else:
                    print("Failed to create Initial SL.")
                    return

            current_sl = float(sl_order.get('stopPrice', 0))
            self.active_sl_order_id = sl_order.get('orderId')
            
            new_sl = None

            # 1. Check Breakeven
            if self.use_breakeven:
                be_trigger = current_atr * self.breakeven_trigger_atr_mult
                be_sl = self.rm.check_breakeven(current_price, entry_price, current_sl, side, be_trigger)
                if be_sl:
                    new_sl = be_sl
                    print(f"Breakeven triggered! Moving SL to {new_sl}")

            # 2. Check Trailing Stop (Only if BE didn't just trigger or it's even better)
            if self.use_trailing_stop:
                trail_amt = current_atr * self.trailing_stop_atr_mult
                trail_step = current_atr * self.trailing_step_atr_mult
                ts_sl = self.rm.check_trailing_stop(current_price, current_sl, side, trail_amt, trail_step)
                if ts_sl:
                    if not new_sl or (side == 'long' and ts_sl > new_sl) or (side == 'short' and ts_sl < new_sl):
                        new_sl = ts_sl
                        print(f"Trailing Stop triggered! Moving SL to {new_sl}")

            # 3. Apply New SL if updated
            if new_sl:
                print(f"Updating SL order for {self.symbol} from {current_sl} to {new_sl}")
                # Cancel old SL
                self.client.cancel_order(self.symbol, self.active_sl_order_id)
                # Place new SL
                sl_side = 'sell' if side == 'long' else 'buy'
                params = {'stopPrice': new_sl}
                res = self.client.create_order(self.symbol, 'stop_market', sl_side, size, params=params)
                if res:
                    self.active_sl_order_id = res.get('orderId')
        except Exception as e:
            print(f"Error in position management: {e}")
