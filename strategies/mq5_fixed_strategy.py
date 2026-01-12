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
                 risk_percent=1.0, profit_percent=0.20,
                 atr_multiplier=1.0, max_positions=3):
        super().__init__("MQ5CryptoMA")
        self.rm = risk_manager
        self.fast_period = fast_period
        self.med_period = med_period
        self.slow_period = slow_period
        
        # Risk Settings
        self.risk_percent = risk_percent       # 1.0% SL
        self.profit_percent = profit_percent   # 0.2% Fixed Hurdle
        self.atr_multiplier = atr_multiplier   # ATR dynamic component
        
        self.max_positions = max_positions
        self.allow_multiple_entries = True 
        
    def generate_signal(self, data: pd.DataFrame) -> dict:
        if len(data) < self.slow_period + 10:
            return {'type': 'HOLD', 'price': 0, 'reason': 'Loading indicators...'}

        close = data['close']
        high = data['high']
        low = data['low']
        
        # 1. Calculate EMAs and ATR
        ema_fast = calculate_ema(close, self.fast_period)
        ema_med = calculate_ema(close, self.med_period)
        ema_slow = calculate_ema(close, self.slow_period)
        atr_series = calculate_atr(high, low, close, 14)
        
        i = len(data) - 1
        c_price = close.iloc[i]
        c_atr = atr_series.iloc[i]
        
        # Current values
        f0, m0, s0 = ema_fast.iloc[i], ema_med.iloc[i], ema_slow.iloc[i]
        # Previous values
        f1, m1 = ema_fast.iloc[i-1], ema_med.iloc[i-1]
        
        # 2. MQ5 Logic
        golden_cross = (f0 > m0 and f1 <= m1)
        death_cross = (f0 < m0 and f1 >= m1)
        bullish_trend = (f0 > m0 and m0 > s0)
        bearish_trend = (f0 < m0 and m0 < s0)
        price_above_med = c_price > m0
        price_below_med = c_price < m0

        signal = 'HOLD'
        reason = []

        if (golden_cross or (f0 > m0)) and bullish_trend and price_above_med:
            signal = 'BUY'
            reason.append("MQ5 BUY: Trend + Momentum Alignment")
        elif (death_cross or (f0 < m0)) and bearish_trend and price_below_med:
            signal = 'SELL'
            reason.append("MQ5 SELL: Trend + Momentum Alignment")

        if signal != 'HOLD':
            # 1.0% Stop Loss
            sl_dist = c_price * (self.risk_percent / 100)
            
            # Hybrid Take Profit: 0.20% Fixed + 1.0x ATR
            tp_fixed_dist = c_price * (self.profit_percent / 100)
            tp_atr_dist = c_atr * self.atr_multiplier
            total_tp_dist = tp_fixed_dist + tp_atr_dist
            
            if signal == 'BUY':
                sl = c_price - sl_dist
                tp = c_price + total_tp_dist
            else:
                sl = c_price + sl_dist
                tp = c_price - total_tp_dist
                
            return {
                'type': signal,
                'price': c_price,
                'sl': sl,
                'tp1': tp,
                'atr': c_atr,
                'reason': f"{reason[0]} (TP: 0.2% + {self.atr_multiplier}x ATR)"
            }

        return {
            'type': 'HOLD',
            'price': c_price,
            'reason': "Waiting for MQ5 setup..."
        }
