
from execution.binance_client import BinanceClient
import json

client = BinanceClient(testnet=True)
symbol = "ETH/USDT"
print(f"Fetching open orders for {symbol}...")
orders = client.get_open_orders(symbol)
print(f"Found {len(orders)} orders.")
for o in orders:
    print(json.dumps(o, indent=2))
