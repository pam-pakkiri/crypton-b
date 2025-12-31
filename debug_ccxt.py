import ccxt
import json

exchange = ccxt.binance({'options': {'defaultType': 'future'}})
try:
    tickers = exchange.fetch_tickers(["BTC/USDT", "ETH/USDT"])
    print(f"Keys format: {list(tickers.keys())}")
    print(f"BTC/USDT Data Sample: {tickers.get('BTC/USDT', 'Not found').get('last')}")
except Exception as e:
    print(f"Error: {e}")
