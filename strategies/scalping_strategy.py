import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy
from analysis.indicators import calculate_ema, calculate_rsi, calculate_atr, calculate_sma
from execution.risk_manager import RiskManager

class ScalpingStrategy(BaseStrategy):
    """
    High-frequency Scalping Strategy (M1/M5).
    Uses 5/8/13 EMA stack + RSI pullbacks + Volume Exhaustion.
    """
    def __init__(self, risk_manager: RiskManager, config: dict = None):
        super().__init__("ScalpingStrategy")
        self.rm = risk_manager
        
        # Default Scalping Config
        self.config = {
            'ema_fast': 5,
            'ema_mid': 8,
            'ema_slow': 13,
            'rsi_period': 7,  # Shorter for scalping
            'rsi_buy_level': 35,
            'rsi_sell_level': 65,
            'vol_sma_period': 20,
            'vol_multiplier': 1.8,
            'rr_ratio': 1.5  # Target 1.5x risk
        }
        if config:
            self.config.update(config)

    def generate_signal(self, data: pd.DataFrame) -> dict:
        if len(data) < 30:
            return {'type': 'HOLD', 'price': 0, 'atr': 0, 'rsi': 0, 'reason': 'Not enough data for scalp.'}
        
        close = data['close']
        high = data['high']
        low = data['low']
        volume = data['volume']
        
        # 1. EMAs for Trend
        e5 = calculate_ema(close, self.config['ema_fast'])
        e8 = calculate_ema(close, self.config['ema_mid'])
        e13 = calculate_ema(close, self.config['ema_slow'])
        
        # 2. RSI for Momentum/Pullback
        rsi = calculate_rsi(close, self.config['rsi_period'])
        
        # 3. Volume SMA for Exhaustion
        vol_sma = calculate_sma(volume, self.config['vol_sma_period'])
        
        i = len(data) - 1
        c_price = close.iloc[i]
        c_rsi = rsi.iloc[i]
        c_vol = volume.iloc[i]
        c_vol_avg = vol_sma.iloc[i]
        
        # Conditions
        is_bullish_aligned = e5.iloc[i] > e8.iloc[i] > e13.iloc[i]
        is_bearish_aligned = e5.iloc[i] < e8.iloc[i] < e13.iloc[i]
        
        # Pullback check (RSI dipped then recovered slightly)
        bullish_pullback = rsi.iloc[i-1] < self.config['rsi_buy_level'] and c_rsi > rsi.iloc[i-1]
        bearish_pullback = rsi.iloc[i-1] > self.config['rsi_sell_level'] and c_rsi < rsi.iloc[i-1]
        
        # Volume Spike (Potential reversal or strong continuation)
        vol_spike = c_vol > (c_vol_avg * self.config['vol_multiplier'])
        
        signal = 'HOLD'
        reason = []
        
        if is_bullish_aligned and bullish_pullback:
            signal = 'BUY'
            reason.append("Scalp BUY: Bullish EMA alignment + RSI Pullback bounce.")
        elif is_bearish_aligned and bearish_pullback:
            signal = 'SELL'
            reason.append("Scalp SELL: Bearish EMA alignment + RSI Pullback fade.")
        
        if signal != 'HOLD' and vol_spike:
            reason.append("Volume confirmation: Strong flow spike.")
        
        # Risk Management
        atr_series = calculate_atr(high, low, close, 14)
        c_atr = atr_series.iloc[i]
        
        if signal != 'HOLD':
            # Tight scalping stops
            stops = self.rm.get_stop_targets(
                entry_price=c_price,
                atr=c_atr,
                side='long' if signal == 'BUY' else 'short',
                tp_multipliers=[self.config['rr_ratio'], 2.5],
                sl_multiplier=1.2 # Tight stop for scalps
            )
            
            return {
                'type': signal,
                'price': c_price,
                'sl': stops.get('sl'),
                'tp1': stops.get('tp1'),
                'tp2': stops.get('tp2'),
                'atr': c_atr,
                'rsi': c_rsi,
                'reason': " | ".join(reason)
            }
            
        return {
            'type': 'HOLD',
            'price': c_price,
            'atr': c_atr,
            'rsi': c_rsi,
            'reason': "Waiting for scalp setup..." if not reason else " | ".join(reason)
        }
