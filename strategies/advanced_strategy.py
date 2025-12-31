import pandas as pd
from strategies.base_strategy import BaseStrategy
from analysis.indicators import calculate_ema, calculate_rsi, calculate_atr, calculate_sma
from execution.risk_manager import RiskManager

class AdvancedStrategy(BaseStrategy):
    def __init__(self, risk_manager: RiskManager):
        super().__init__("AdvancedStrategy")
        self.rm = risk_manager

    def generate_signal(self, data: pd.DataFrame) -> dict:
        if len(data) < 200:
            return {'type': 'HOLD', 'price': 0, 'reason': 'Not enough data'}
        
        # 1. Indicators
        close = data['close']
        high = data['high']
        low = data['low']
        volume = data['volume']
        
        ema20 = calculate_ema(close, 20)
        ema50 = calculate_ema(close, 50)
        ema200 = calculate_ema(close, 200)
        
        rsi = calculate_rsi(close, 14)
        atr = calculate_atr(high, low, close, 14)
        vol_sma = calculate_sma(volume, 20)
        
        # Current Candle
        curr_price = close.iloc[-1]
        curr_time = data['timestamp'].iloc[-1]
        
        curr_ema20 = ema20.iloc[-1]
        curr_ema50 = ema50.iloc[-1]
        curr_ema200 = ema200.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_vol = volume.iloc[-1]
        curr_vol_sma = vol_sma.iloc[-1]
        curr_atr = atr.iloc[-1]
        
        signal = 'HOLD'
        reason = []
        
        # 2. Trend Engine (EMA Alignment)
        is_bullish_trend = (curr_ema20 > curr_ema50) and (curr_ema50 > curr_ema200) and (curr_price > curr_ema200)
        is_bearish_trend = (curr_ema20 < curr_ema50) and (curr_ema50 < curr_ema200) and (curr_price < curr_ema200)
        
        # 3. Volume Check
        has_volume = curr_vol > (1.5 * curr_vol_sma)
        
        # 4. Entry Logic
        # LONG
        if is_bullish_trend and has_volume:
            # RSI Filter: Not overbought, or bullish breakout
            if 40 < curr_rsi < 70:
                signal = 'BUY'
                reason.append(f"Bullish Trend + Vol Spike (RSI {curr_rsi:.1f})")

        # SHORT
        elif is_bearish_trend and has_volume:
            if 30 < curr_rsi < 60: # Not oversold yet
                signal = 'SELL'
                reason.append(f"Bearish Trend + Vol Spike (RSI {curr_rsi:.1f})")
        
        # Return Risk Parameters with Signal
        stops = None
        if signal != 'HOLD':
            # Calculate Risk Profile
            side = 'long' if signal == 'BUY' else 'short'
            
            # Simple structure stop: Low of last 5 candles (approx)
            if side == 'long':
                struct_stop = low.iloc[-5:].min()
                 # Ensure Stop is not above entry
                if struct_stop >= curr_price: struct_stop = curr_price - curr_atr
            else:
                struct_stop = high.iloc[-5:].max()
                if struct_stop <= curr_price: struct_stop = curr_price + curr_atr
            
            stops = self.rm.get_stop_targets(curr_price, curr_atr, side, struct_stop)
            
            return {
                'type': signal,
                'price': curr_price,
                'reason': ", ".join(reason),
                'sl': stops['sl'],
                'tp1': stops['tp1'],
                'tp2': stops['tp2'],
                'tp3': stops['tp3']
            }
            
        return {
            'type': signal,
            'price': curr_price,
            'reason': ''
        }
