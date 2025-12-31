import pandas as pd
from strategies.base_strategy import BaseStrategy

class Backtester:
    def __init__(self, initial_capital=10000.0, commission=0.0004): # Futures commission 0.04% taker usually
        self.initial_capital = initial_capital
        self.commission = commission

    def run(self, strategy: BaseStrategy, data: pd.DataFrame):
        if data is None or data.empty:
            print("No data to backtest.")
            return None

        balance = self.initial_capital
        position_size = 0.0 # Positive for Long, Negative for Short
        entry_price = 0.0
        
        trades = []
        equity_curve = []
        
        # Metrics for visualization
        trade_markers = [] # Buy/Sell actions for plotting

        print(f"Starting Futures backtest for {strategy.name} with ${self.initial_capital}...")
        
        long_window = 200 # Need data for EMAs
        if len(data) < long_window:
            print("Not enough data.")
            return None

        for i in range(long_window, len(data)):
            window_data = data.iloc[:i+1].copy()
            timestamp = window_data.iloc[-1]['timestamp']
            current_price = window_data.iloc[-1]['close']
            
            # Generate Signal
            signal_dict = strategy.generate_signal(window_data)
            signal = signal_dict['type']
            
            # Manage Open Positions (TP/SL) - Simplified "Check within candle" simulation
            # Note: signal generation is on CLOSE. So we trade at CLOSE price of 'i' (approx next open)
            
            # Execution Logic
            if signal == 'BUY':
                # 1. Close Short if any
                if position_size < 0:
                    # Closing Short (Buying back)
                    pnl = (entry_price - current_price) * abs(position_size)
                    fee = abs(position_size) * current_price * self.commission
                    balance += pnl - fee
                    
                    trades.append({
                        'type': 'CLOSE_SHORT', 'time': timestamp, 'price': current_price, 
                        'pnl': pnl, 'balance': balance
                    })
                    position_size = 0
                    
                # 2. Open Long (if flat)
                if position_size == 0 and balance > 0:
                    # Risk control is in strategy, but let's assume valid size or max balance
                    # Use 100% of balance for simple compounding test, or risk based
                    # If strategy gave 'Stop Loss', we could size properly. 
                    # For now: Use 95% of balance to avoid rounding errors
                    alloc = balance * 0.95
                    quantity = alloc / current_price
                    fee = quantity * current_price * self.commission
                    
                    # In futures, balance is margin. We don't 'spend' it, we use it as collateral.
                    # But PnL adds/subtracts from it.
                    # Simpler model: Cost = Value / Leverage.
                    # Let's assume 1x leverage for basic backtest validity.
                    
                    entry_price = current_price
                    position_size = quantity
                    
                    # Deduct fee from balance
                    balance -= fee
                    
                    trades.append({
                        'type': 'LONG', 'time': timestamp, 'price': current_price, 
                        'size': quantity, 'balance': balance
                    })

            elif signal == 'SELL':
                # 1. Close Long if any
                if position_size > 0:
                    # Closing Long (Selling)
                    pnl = (current_price - entry_price) * position_size
                    fee = position_size * current_price * self.commission
                    balance += pnl - fee
                    
                    trades.append({
                        'type': 'CLOSE_LONG', 'time': timestamp, 'price': current_price, 
                        'pnl': pnl, 'balance': balance
                    })
                    position_size = 0
                    
                # 2. Open Short (if flat)
                if position_size == 0 and balance > 0:
                    alloc = balance * 0.95
                    quantity = alloc / current_price
                    fee = quantity * current_price * self.commission
                    
                    entry_price = current_price
                    position_size = -quantity # Negative for short
                    
                    balance -= fee
                    trades.append({
                        'type': 'SHORT', 'time': timestamp, 'price': current_price,
                        'size': quantity, 'balance': balance
                    })

            # Calculate Unrealized Equity
            unrealized_pnl = 0
            if position_size != 0:
                if position_size > 0:
                    unrealized_pnl = (current_price - entry_price) * abs(position_size)
                else:
                    unrealized_pnl = (entry_price - current_price) * abs(position_size)
            
            equity = balance + unrealized_pnl
            equity_curve.append(equity)

        # Final Close
        final_price = data.iloc[-1]['close']
        if position_size != 0:
            if position_size > 0:
                pnl = (final_price - entry_price) * abs(position_size)
            else:
                pnl = (entry_price - final_price) * abs(position_size)
            balance += pnl
            
        final_equity = balance
        roi = ((final_equity - self.initial_capital) / self.initial_capital) * 100
        
        print(f"Backtest Complete.")
        print(f"Final Equity: ${final_equity:.2f}")
        print(f"Total Return: {roi:.2f}%")
        print(f"Total Trades: {len(trades)}")
        
        return {
            'final_equity': final_equity,
            'roi': roi,
            'trades': trades,
            'equity_curve': equity_curve,
            'data': data
        }
