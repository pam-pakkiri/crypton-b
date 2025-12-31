
from execution.binance_client import BinanceClient
import time

client = BinanceClient(testnet=True)
symbol = "ETH/USDT"

# Fetch current price to place a safe SL
ticker = client.get_ticker_direct(symbol)
if not ticker:
    print("Could not fetch ticker.")
    exit()

last_price = float(ticker['last'])
print(f"Current ETH price: {last_price}")

# Assume SHORT position, so SL is ABOVE.
# Place SL at +10%
sl_price = round(last_price * 1.10, 2)
print(f"Attempting to place STOP_MARKET SL at {sl_price}...")

# Test the create_order calculation
try:
    # quantity 0.01
    # reduceOnly=True key?
    params = {
        'stopPrice': sl_price,
        'reduceOnly': 'true' # Send as string? or boolean? Requests might need conversion. 
                             # CCXT handles this. Here we are using raw requests. 
                             # Binance API expects boolean true/false or "true"/"false".
    }
    
    # We need to send side=BUY to close a SHORT
    res = client.create_order(symbol, 'STOP_MARKET', 'BUY', 0.02, params=params)
    print("Result:", res)
except Exception as e:
    print("Error:", e)
