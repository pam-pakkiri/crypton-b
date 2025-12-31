from execution.binance_client import BinanceClient
import pandas as pd

def test_client():
    print("Testing BinanceClient with Testnet...")
    client = BinanceClient(testnet=True)
    # client.exchange.verbose = True # DEBUG
    
    # Test balance
    try:
        balance = client.get_balance()
        if balance and 'total' in balance:
            print(f"Balance fetched! USDT: {balance['total'].get('USDT', 0)}")
        else:
            print("Could not fetch balance.")
    except Exception as e:
        print(f"Error fetching balance: {e}")

    # Test OHLCV
    try:
        df = client.fetch_ohlcv('BTC/USDT', '1h', limit=5)
        if df is not None:
            print("OHLCV data fetched!")
            print(df.tail(2))
        else:
            print("Could not fetch OHLCV.")
    except Exception as e:
        print(f"Error fetching OHLCV: {e}")

if __name__ == "__main__":
    test_client()
