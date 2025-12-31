from execution.binance_client import BinanceClient
import time

def verify_trade():
    print("Verifying Trade Execution with Dynamic Settings...")
    client = BinanceClient(testnet=True)
    symbol = "BTC/USDT"
    leverage = 5
    margin_mode = "isolated"
    
    try:
        # 1. Set settings
        print(f"Setting leverage to {leverage} and margin to {margin_mode}...")
        client.set_margin_mode(symbol, margin_mode)
        client.set_leverage(symbol, leverage)
        
        # 2. Try to fetch order book (public check)
        ticker = client.get_ticker(symbol)
        price = ticker['last']
        print(f"Current Price: {price}")
        
        # 0.002 BTC is ~170 USDT, which passes the 100 USDT min notional on testnet
        print(f"Creating test BUY order for 0.002 {symbol}...")
        order = client.create_order(symbol, 'market', 'buy', 0.002)
        
        if order:
            print(f"Order Success! ID: {order['orderId']}")
            # Immediately close?
            time.sleep(2)
            print("Closing test order...")
            client.create_order(symbol, 'market', 'sell', 0.002)
            print("Order Closed.")
        else:
            print("Order Failed.")
            
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    verify_trade()
