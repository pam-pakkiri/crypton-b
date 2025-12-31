from execution.binance_client import BinanceClient
from strategies.smart_futures_strategy import SmartFuturesStrategy
from execution.risk_manager import RiskManager
from execution.trader import LiveTrader
from config import SYMBOL, TIMEFRAME

def main():
    print("--- 🚀 Initializing AI Futures Bot ---")
    
    # 1. Initialize Client (Futures Mode)
    client = BinanceClient() 
    
    # Check connection
    # balance = client.get_balance()
    # if balance: print("Connection Successful.")
    
    # 2. Initialize Risk Manager
    # Risk 1% per trade, Account size dynamic or hardcoded for safety
    rm = RiskManager(account_size=100, risk_per_trade=0.01) # Set your account size approx for sizing logic
    
    # 3. Initialize Strategy
    strategy = SmartFuturesStrategy(risk_manager=rm)
    
    # 4. Initialize Trader
    trader = LiveTrader(client, strategy, risk_manager=rm, symbol=SYMBOL, timeframe=TIMEFRAME)
    
    # 5. Start Loop
    trader.start(interval=60)

if __name__ == "__main__":
    main()
