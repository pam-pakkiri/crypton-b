import pandas as pd
import numpy as np
import datetime
import logging
from enum import Enum
from strategies.base_strategy import BaseStrategy
from analysis.indicators import calculate_ema, calculate_rsi, calculate_atr, calculate_sma
from execution.risk_manager import RiskManager

# ===== ENUMERATIONS =====
class MarketRegime(Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"

class SignalType(Enum):
    NONE = "NONE"
    BUY = "BUY"
    SELL = "SELL"

class InstitutionalStrategy(BaseStrategy):
    """
    Strategy based on the Institutional Crypto EA formula.
    Features market regime detection, multi-MA crossovers, 
    and volume flow confirmation.
    """
    def __init__(self, risk_manager: RiskManager, config: dict = None):
        super().__init__("InstitutionalStrategy")
        self.rm = risk_manager
        
        # Default Config (Overridden by config if provided)
        self.config = {
            'fast_ma_period1': 7,
            'slow_ma_period1': 21,
            'rsi_period': 14,
            'adx_period': 14,
            'min_adx': 25.0,
            'volume_spike_threshold': 2.5,
            'use_rsi_momentum': True,
            'trade_with_volume_flow': True,
            'use_market_regime_detection': True
        }
        if config:
            self.config.update(config)

        self.current_regime = MarketRegime.TRENDING

    def calculate_adx(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calculate ADX (Simplified for selection)"""
        if len(data) < period * 2:
            return 0.0
        
        high = data['high']
        low = data['low']
        close = data['close']
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        # Using EMA based ATR as in the formula's intention
        tr = calculate_atr(high, low, close, period)
        
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / tr)
        minus_di = 100 * (minus_dm.abs().ewm(alpha=1/period, adjust=False).mean() / tr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0.0

    def calculate_volume_ratio(self, volume_series: pd.Series, lookback: int = 10) -> float:
        if len(volume_series) < lookback:
            return 1.0
        current_volume = volume_series.iloc[-1]
        avg_volume = volume_series.iloc[-lookback:-1].mean()
        return current_volume / avg_volume if avg_volume > 0 else 1.0

    def detect_market_regime(self, data: pd.DataFrame) -> MarketRegime:
        if not self.config.get('use_market_regime_detection', True):
            return MarketRegime.TRENDING
        
        close = data['close']
        atr = calculate_atr(data['high'], data['low'], close, 14)
        atr_val = atr.iloc[-1]
        atr_percent = (atr_val / close.iloc[-1]) * 100 if not pd.isna(atr_val) else 0
        
        adx_value = self.calculate_adx(data)
        rsi_series = calculate_rsi(close, 14)
        rsi_value = rsi_series.iloc[-1]
        volume_ratio = self.calculate_volume_ratio(data['volume'])
        
        min_adx = self.config.get('min_adx', 25.0)
        
        # Trend detection
        if adx_value > min_adx and atr_percent > 0.5:
             # Check Trend Direction
             fast_ma = calculate_ema(close, 7).iloc[-1]
             slow_ma = calculate_ema(close, 21).iloc[-1]
             if fast_ma != slow_ma:
                 return MarketRegime.TRENDING
        
        # Range detection
        if atr_percent < 0.3 and adx_value < 20:
            return MarketRegime.RANGING
        
        # Breakout detection
        volume_spike_threshold = self.config.get('volume_spike_threshold', 2.5)
        if volume_ratio > volume_spike_threshold and atr_percent > 0.8:
            return MarketRegime.BREAKOUT
        
        # Reversal detection
        if abs(rsi_value - 50) > 20 and volume_ratio > 2.0:
            return MarketRegime.REVERSAL
        
        return MarketRegime.TRENDING

    def generate_signal(self, data: pd.DataFrame) -> dict:
        if len(data) < 50:
            return {'type': 'HOLD', 'price': 0, 'atr': 0, 'rsi': 0, 'reason': 'Waiting for more data...'}
        
        # 1. Regime Detection
        self.current_regime = self.detect_market_regime(data)
        
        # 2. Main Logic: MA Crossover
        close = data['close']
        fast_ma = calculate_ema(close, self.config['fast_ma_period1'])
        slow_ma = calculate_ema(close, self.config['slow_ma_period1'])
        
        i = len(data) - 1
        c_price = close.iloc[i]
        
        # Signal Crossover
        bullish_cross = (fast_ma.iloc[i-1] <= slow_ma.iloc[i-1] and fast_ma.iloc[i] > slow_ma.iloc[i])
        bearish_cross = (fast_ma.iloc[i-1] >= slow_ma.iloc[i-1] and fast_ma.iloc[i] < slow_ma.iloc[i])
        
        signal = 'HOLD'
        reason = [f"Regime: {self.current_regime.value}"]
        
        # 3. Confirmation Logic
        confirmed = False
        if bullish_cross or bearish_cross:
            # RSI Momentum Confirmation
            rsi = calculate_rsi(close, self.config['rsi_period'])
            c_rsi = rsi.iloc[i]
            
            if 30 < c_rsi < 70:
                # Volume Flow Confirmation
                vol_ratio = self.calculate_volume_ratio(data['volume'])
                vol_threshold = self.config['volume_spike_threshold']
                
                if not self.config['trade_with_volume_flow'] or vol_ratio > vol_threshold:
                    confirmed = True
                    signal = 'BUY' if bullish_cross else 'SELL'
                    reason.append(f"Institutional Signal Confirmed: {signal} cross + RSI OK + Vol Ratio {vol_ratio:.2f}")
                else:
                    reason.append(f"Signal ignored: Low Volume Flow ({vol_ratio:.2f} < {vol_threshold})")
            else:
                reason.append(f"Signal ignored: RSI in extreme territory ({c_rsi:.2f})")
        
        if signal == 'HOLD' and len(reason) == 1:
            reason.append("Steady market, waiting for institutional flow.")

        # 4. Return formatted signal
        atr_series = calculate_atr(data['high'], data['low'], close, 14)
        c_atr = atr_series.iloc[i]
        c_rsi_val = calculate_rsi(close, 14).iloc[i] # Just for output
        
        # Risk Management (Adjusted by Regime)
        # We handle sizing in LiveTrader/RiskManager, but we can pass a 'confidence' or multi-TPs
        if signal != 'HOLD':
            # Dynamic TP/SL distances
            # Trending uses wider TPs
            tp_mults = [2, 3, 5] if self.current_regime == MarketRegime.TRENDING else [1.5, 2.5, 3.5]
            
            stops = self.rm.get_stop_targets(
                entry_price=c_price,
                atr=c_atr,
                side='long' if signal == 'BUY' else 'short',
                tp_multipliers=tp_mults,
                sl_multiplier=2.0 # Standard Institutional 2 ATR stop
            )
            
            return {
                'type': signal,
                'price': c_price,
                'sl': stops.get('sl'),
                'tp1': stops.get('tp1'),
                'tp2': stops.get('tp2'),
                'tp3': stops.get('tp3'),
                'atr': c_atr,
                'rsi': c_rsi_val,
                'reason': " | ".join(reason)
            }

        return {
            'type': 'HOLD',
            'price': c_price,
            'atr': c_atr,
            'rsi': c_rsi_val,
            'reason': " | ".join(reason)
        }

    def analyze_historical(self, data: pd.DataFrame) -> list:
        """
        Analyzes historical data to identify potential BUY, SELL, and FAKEOUT signals.
        Returns a list of markers compatible with Lightweight Charts.
        """
        if len(data) < 50:
            return []
        
        signals = []
        close = data['close']
        volume = data['volume']
        
        # Calculate Indicators
        fast_ma = calculate_ema(close, self.config['fast_ma_period1'])
        slow_ma = calculate_ema(close, self.config['slow_ma_period1'])
        rsi = calculate_rsi(close, self.config['rsi_period'])
        
        # Helper for volume ratio (vectorize or simple sliding window calculation inside loop)
        # Pre-calculating rolling mean for efficiency
        # Average volume of previous 10 candles
        avg_vol = volume.rolling(window=10).mean().shift(1) # Shift 1 to use PAST data for current candle
        
        # Iterate starting from index 50
        for i in range(50, len(data)):
            try:
                # Crossover Check
                bullish_cross = (fast_ma.iloc[i-1] <= slow_ma.iloc[i-1] and fast_ma.iloc[i] > slow_ma.iloc[i])
                bearish_cross = (fast_ma.iloc[i-1] >= slow_ma.iloc[i-1] and fast_ma.iloc[i] < slow_ma.iloc[i])
                
                if bullish_cross or bearish_cross:
                    # Logic Replication
                    c_rsi = rsi.iloc[i]
                    c_vol = volume.iloc[i]
                    c_avg_vol = avg_vol.iloc[i] if not pd.isna(avg_vol.iloc[i]) else c_vol
                    vol_ratio = c_vol / c_avg_vol if c_avg_vol > 0 else 1.0
                    
                    vol_threshold = self.config['volume_spike_threshold']
                    
                    signal_type = 'FAKEOUT'
                    
                    if 30 < c_rsi < 70:
                        if not self.config['trade_with_volume_flow'] or vol_ratio > vol_threshold:
                            signal_type = 'BUY' if bullish_cross else 'SELL'
                    
                    # Construct Marker (Lightweight Charts format usually handled in frontend, but we return data)
                    # Time needs to be unix timestamp in seconds
                    ts = int(data.iloc[i]['timestamp'] / 1000)
                    
                    if signal_type == 'BUY':
                        signals.append({
                            'time': ts,
                            'position': 'belowBar',
                            'color': '#0ecb81', # Green
                            'shape': 'arrowUp',
                            'text': 'BUY'
                        })
                    elif signal_type == 'SELL':
                        signals.append({
                            'time': ts,
                            'position': 'aboveBar',
                            'color': '#f6465d', # Red
                            'shape': 'arrowDown',
                            'text': 'SELL'
                        })
                    else: # FAKEOUT
                        signals.append({
                            'time': ts,
                            'position': 'aboveBar' if bearish_cross else 'belowBar',
                            'color': '#808080', # Grey
                            'shape': 'circle',
                            'text': 'FAKEOUT'
                        })
            except Exception as e:
                continue
                
        return signals
