from execution.binance_client import BinanceClient
from analysis.data_loader import DataLoader
from strategies.smart_futures_strategy import SmartFuturesStrategy
from execution.risk_manager import RiskManager
from analysis.backtester import Backtester
from analysis.visualizer import Visualizer

def main():
    print("--- Smart Futures Bot Strategy Backtest ---")
    
    # 1. Fetch Data
    client = BinanceClient() # uses defaultType='future' now
    loader = DataLoader(client)
    symbol = 'BTC/USDT'
    timeframe = '1h'
    print(f"Fetching 1000 candles for {symbol}...")
    data = loader.get_historical_data(symbol, timeframe, limit=1000)
    # data = loader.get_historical_data(symbol, timeframe, limit=100) # Quick test

    if data is None:
        return

    # 2. Strategy
    rm = RiskManager(account_size=10000)
    strategy = SmartFuturesStrategy(rm)

    # 3. Backtest
    backtester = Backtester(initial_capital=10000)
    results = backtester.run(strategy, data)
    
    if results:
        print("\n--- Trade Sample ---")
        for t in results['trades'][:10]:
            print(t)
            
        # Visualize
        viz = Visualizer(results['data'], results['trades'])
        viz.plot()

if __name__ == "__main__":
    main()
