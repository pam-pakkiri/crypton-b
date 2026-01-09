import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy
from analysis.indicators import calculate_ema, calculate_atr
import datetime

class CryptoMAFixedStrategy(BaseStrategy):
    """
    Python implementation of CryptoMAATRProBot.mq5
    Logic: 7/25/99 EMA Crossover + Fixed % SL/TP
    """
    def __init__(self, risk_manager, 
                 fast_period=7, med_period=25, slow_period=99,
                 risk_percent=1.0, profit_percent=0.5,
                 max_positions=3):
        super().__init__("MQ5CryptoMA")
        self.rm = risk_manager
        self.fast_period = fast_period
        self.med_period = med_period
        self.slow_period = slow_period
        
        # Fixed % Settings from MQ5
        self.risk_percent = risk_percent   # 1.0% SL
        self.profit_percent = profit_percent # 0.5% TP
        
        self.max_positions = max_positions
        self.allow_multiple_entries = True # As per your MQ5 config
        
    def generate_signal(self, data: pd.DataFrame) -> dict:
        if len(data) < self.slow_period + 10:
            return {'type': 'HOLD', 'price': 0, 'reason': 'Loading indicators...'}

        close = data['close']
        
        # 1. Calculate EMAs
        ema_fast = calculate_ema(close, self.fast_period)
        ema_med = calculate_ema(close, self.med_period)
        ema_slow = calculate_ema(close, self.slow_period)
        
        i = len(data) - 1
        c_price = close.iloc[i]
        
        # Current values
        f0, m0, s0 = ema_fast.iloc[i], ema_med.iloc[i], ema_slow.iloc[i]
        # Previous values (for crossover check)
        f1, m1 = ema_fast.iloc[i-1], ema_med.iloc[i-1]
        
        # 2. MQ5 Logic
        # Golden/Death Cross
        golden_cross = (f0 > m0 and f1 <= m1)
        death_cross = (f0 < m0 and f1 >= m1)
        
        # Trend Alignment (Fast > Med > Slow)
        bullish_trend = (f0 > m0 and m0 > s0)
        bearish_trend = (f0 < m0 and m0 < s0)
        
        # Price Filter
        price_above_med = c_price > m0
        price_below_med = c_price < m0

        signal = 'HOLD'
        reason = []

        # --- BUY SIGNAL ---
        if (golden_cross or (f0 > m0)) and bullish_trend and price_above_med:
            signal = 'BUY'
            reason.append("MQ5 BUY: EMA Crossover + Trend Aligned + Price Above Med")
            
        # --- SELL SIGNAL ---
        elif (death_cross or (f0 < m0)) and bearish_trend and price_below_med:
            signal = 'SELL'
            reason.append("MQ5 SELL: EMA Crossover + Trend Aligned + Price Below Med")

        if signal != 'HOLD':
            # Calculate SL/TP based on Fixed Percentages from Entry Price
            # SL = 1.0%, TP = 0.5%
            if signal == 'BUY':
                sl = c_price * (1 - (self.risk_percent / 100))
                tp = c_price * (1 + (self.profit_percent / 100))
            else:
                sl = c_price * (1 + (self.risk_percent / 100))
                tp = c_price * (1 - (self.profit_percent / 100))
                
            return {
                'type': signal,
                'price': c_price,
                'sl': sl,
                'tp1': tp,
                'atr': calculate_atr(data['high'], data['low'], close, 14).iloc[i],
                'reason': " | ".join(reason)
            }

        return {
            'type': 'HOLD',
            'price': c_price,
            'reason': "Waiting for MQ5 setup..."
        }
