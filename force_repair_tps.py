from execution.binance_client import BinanceClient
from execution.risk_manager import RiskManager
from strategies.smart_futures_strategy import SmartFuturesStrategy
import time

def force_repair():
    client = BinanceClient(testnet=True)
    rm = RiskManager(account_size=15000, risk_per_trade=0.01)
    strategy = SmartFuturesStrategy(risk_manager=rm)
    
    # Symbols from image
    symbols = ["ETH/USDT", "BCH/USDT", "BTC/USDT"]
    
    print("Starting Force Repair for Take Profit levels...")
    
    positions = client.get_positions()
    for pos in positions:
        # Convert BTCUSDT to BTC/USDT
        raw_sym = pos['symbol']
        symbol = raw_sym
        if "USDT" in raw_sym and "/" not in raw_sym:
            symbol = raw_sym.replace("USDT", "/USDT")
            
        if symbol not in symbols:
            continue
            
        print(f"\nRepairing {symbol}...")
        side_val = float(pos['size'])
        side = 'long' if side_val > 0 else 'short'
        size = abs(side_val)
        entry_price = float(pos['entryPrice'])
        
        # 1. Fetch current ATR for the symbol
        df = client.fetch_ohlcv(symbol, '15m', limit=100)
        if df is None or df.empty:
            print(f"  Failed to fetch data for {symbol}")
            continue
            
        # Quick ATR calculation
        high = df['high']
        low = df['low']
        close = df['close']
        tr = (high - low).clip(lower=(high - close.shift(1)).abs()).clip(lower=(low - close.shift(1)).abs())
        atr = tr.rolling(14).mean().iloc[-1]
        
        print(f"  Current ATR: {atr}")
        
        # 2. Check if TP exists
        orders = client.get_open_orders(symbol)
        tp_orders = [o for o in orders if o.get('type') == 'LIMIT']
        
        if not tp_orders:
            print(f"  No TP orders found. Placing recovery TPs...")
            tp_mults = [2, 3, 4]
            stops = rm.get_stop_targets(entry_price, atr, side, tp_multipliers=tp_mults)
            
            tp_side = 'sell' if side == 'long' else 'buy'
            tp1 = stops.get('tp1')
            
            if tp1:
                print(f"  Placing Recovery TP at {tp1} for {size}...")
                res = client.create_order(
                    symbol, 'LIMIT', tp_side, size, 
                    price=tp1, 
                    params={'reduceOnly': 'true'}
                )
                if res:
                    print(f"  SUCCESS: {res.get('orderId')}")
                else:
                    print(f"  FAILED to place order.")
        else:
            print(f"  TP already exists for {symbol}.")

if __name__ == "__main__":
    force_repair()
