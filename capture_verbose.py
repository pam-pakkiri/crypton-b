import ccxt
from config import BINANCE_API_KEY, BINANCE_API_SECRET

def test():
    exchange = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_API_SECRET,
        'enableRateLimit': True,
        'verbose': True,
        'options': {'defaultType': 'future'}
    })
    # Manual URL
    exchange.urls['api']['fapi'] = 'https://demo-fapi.binance.com/fapi/v1'
    exchange.urls['api']['private'] = 'https://demo-fapi.binance.com/fapi/v1'
    
    try:
        exchange.fetch_balance({'type': 'future'})
    except Exception as e:
        print(f"\nCaught Error: {e}")

if __name__ == "__main__":
    test()
