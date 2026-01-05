from execution.binance_client import BinanceClient
import json

def check_status():
    client = BinanceClient(testnet=True)
    print("Fetching positions...")
    positions = client.get_positions()
    
    for pos in positions:
        symbol = pos['symbol']
        print(f"\n--- {symbol} ---")
        print(f"Side: {'LONG' if float(pos['size']) > 0 else 'SHORT'}, Size: {pos['size']}")
        print(f"Entry: {pos['entryPrice']}, Mark: {pos['markPrice']}")
        
        print("Fetching open orders...")
        orders = client.get_open_orders(symbol)
        sl_orders = [o for o in orders if o.get('type') in ['STOP_MARKET', 'STOP']]
        tp_orders = [o for o in orders if o.get('type') in ['LIMIT']]
        
        print(f"SL Orders: {len(sl_orders)}")
        for o in sl_orders:
            print(f"  ID: {o['orderId']}, Price: {o.get('stopPrice') or o.get('price')}")
            
        print(f"TP Orders: {len(tp_orders)}")
        for o in tp_orders:
            print(f"  ID: {o['orderId']}, Price: {o.get('price')}, Qty: {o.get('origQty')}, reduceOnly: {o.get('reduceOnly')}")

if __name__ == "__main__":
    check_status()
