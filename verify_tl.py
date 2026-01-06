from execution.binance_client import BinanceClient
import json

def verify_tl():
    client = BinanceClient(testnet=True)
    print("Verifying Trailing Stop (TL) and ATR Logic...")
    positions = client.get_positions()
    
    for pos in positions:
        symbol = pos['symbol']
        entry = float(pos['entryPrice'])
        mark = float(pos['markPrice'])
        side = 'LONG' if float(pos['size']) > 0 else 'SHORT'
        
        print(f"\n--- {symbol} ({side}) ---")
        print(f"Entry: {entry}, Mark: {mark}")
        
        # Calculate current profit %
        if side == 'LONG':
            pnl_pct = (mark - entry) / entry * 100
        else:
            pnl_pct = (entry - mark) / entry * 100
        print(f"Current Profit: {pnl_pct:.2f}%")
        
        orders = client.get_open_orders(symbol)
        sl_orders = [o for o in orders if o.get('type') in ['STOP_MARKET', 'STOP']]
        
        if sl_orders:
            for sl in sl_orders:
                sl_price = float(sl.get('stopPrice') or sl.get('price'))
                # Distance from entry
                dist = (sl_price - entry) if side == 'LONG' else (entry - sl_price)
                print(f"  SL ID: {sl['orderId']}, Price: {sl_price}")
                if dist > 0:
                    print(f"  STATUS: SL is already in PROFIT (Moved {dist:.2f} units from entry)")
                elif dist == 0:
                    print(f"  STATUS: SL is at BREAKEVEN")
                else:
                    print(f"  STATUS: SL is in LOSS ({abs(dist):.2f} units below entry)")
        else:
            print("  NO Stop Loss Order found!")

if __name__ == "__main__":
    verify_tl()
