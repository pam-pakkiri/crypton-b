from execution.binance_client import BinanceClient
import json

def test():
    client = BinanceClient(testnet=True)
    
    print("--- Testing Balance (Private) ---")
    bal = client.get_balance()
    if bal:
        print(f"Success: Balance total USDT: {bal['total'].get('USDT', 0)}")
    else:
        print("Failed to fetch balance.")
        
    print("\n--- Testing Order Book (Public/Auth) ---")
    symbol = "BTC/USDT"
    book = client.get_order_book(symbol, limit=5)
    if book:
        print(f"Success: Fetched {len(book.get('bids', []))} bids.")
        # print(json.dumps(book, indent=2))
    else:
        print(f"Failed to fetch order book for {symbol}.")

    symbol2 = "ETH/USDT"
    book2 = client.get_order_book(symbol2, limit=5)
    if book2:
        print(f"Success: Fetched {len(book2.get('bids', []))} bids for {symbol2}.")
    else:
        print(f"Failed to fetch order book for {symbol2}.")

if __name__ == "__main__":
    test()
