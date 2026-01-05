import sys
import os

# Add the current directory to path
sys.path.append(os.getcwd())

from execution.binance_client import BinanceClient
from config import SYMBOL

def check_recent_trades():
    # Detect if we should use testnet or mainnet
    is_prod = os.getenv("PRODUCTION", "0") == "1"
    client = BinanceClient(testnet=not is_prod)
    
    print(f"Checking trade history for {SYMBOL}...")
    trades = client.get_trade_history_manual(SYMBOL, limit=5)
    
    if not trades:
        print("No recent trades found in the history.")
        return

    print(f"\n--- Recent Trades for {SYMBOL} ---")
    for t in trades:
        print(f"Time: {t['datetime']} | Side: {t['side'].upper()} | Price: {t['price']} | Qty: {t['amount']} | PNL: {t['pnl']}")

if __name__ == "__main__":
    check_recent_trades()
