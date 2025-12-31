
from execution.binance_client import BinanceClient
import json

client = BinanceClient(testnet=True)
symbol = "ETH/USDT"
print(f"checking open orders for {symbol} (using raw string)...")
# Try with slash
try:
    orders = client.get_open_orders(symbol)
    print(f"Orders for {symbol}: {len(orders)}")
    print(json.dumps(orders, indent=2))
except Exception as e:
    print(e)
    
symbol_raw = "ETHUSDT"
print(f"checking open orders for {symbol_raw} (raw)...")
try:
    orders_raw = client.get_open_orders(symbol_raw)
    print(f"Orders for {symbol_raw}: {len(orders_raw)}")
    if orders_raw:
        print(json.dumps(orders_raw, indent=2))
except Exception as e:
    print(e)
