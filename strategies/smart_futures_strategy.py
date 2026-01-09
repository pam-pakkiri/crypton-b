import pandas as pd
import numpy as np
import datetime
from strategies.base_strategy import BaseStrategy
from analysis.indicators import calculate_ema, calculate_rsi, calculate_atr, calculate_sma, get_recent_swings
from execution.risk_manager import RiskManager

class SmartFuturesStrategy(BaseStrategy):
    def __init__(self, risk_manager: RiskManager, swing_window: int = 50, min_trade_interval_minutes: int = 240,
                 tp_atr_multipliers: list = [2.0, 4.0, 6.0], sl_atr_multiplier: float = 2.0,
                 quantity_step: float = 0.001, bars_for_signal: int = 2,
                 rsi_overbought: int = 70, rsi_oversold: int = 30):
        super().__init__("SmartFuturesStrategy")
        self.rm = risk_manager
        # Swing‑trade configuration
        self.swing_window = swing_window
        self.min_trade_interval = datetime.timedelta(minutes=min_trade_interval_minutes)
        self.tp_atr_multipliers = tp_atr_multipliers
        self.sl_atr_multiplier = sl_atr_multiplier
        self.quantity_step = quantity_step
        self.last_trade_timestamp = None  # datetime of last executed trade
        
        # MQ5 Professional Parameters
        self.bars_for_signal = bars_for_signal
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        
        # Time Filters
        self.use_time_filter = False
        self.start_time = "00:00"
        self.end_time = "23:59"
        self.friday_close = True
        self.friday_close_hour = 20

    def generate_signal(self, data: pd.DataFrame) -> dict:
        if len(data) < 600:
            return {'type': 'HOLD', 'price': 0, 'atr': 0, 'rsi': 0, 'reason': f'Not enough data ({len(data)}/600)'}
        
        # --- 1. Data Preparation ---
        high = data['high']
        low = data['low']
        close = data['close']
        open_prices = data['open']
        volume = data['volume']
        
        # Indicators
        ema_fast = calculate_ema(close, 9)  # MQ5 Default
        ema_slow = calculate_ema(close, 21) # MQ5 Default
        ema7 = calculate_ema(close, 7)      # Momentum EMA
        ema200 = calculate_ema(close, 200)
        atr = calculate_atr(high, low, close, 14)
        rsi = calculate_rsi(close, 14)
        vol_sma = calculate_sma(volume, 20)
        
        # Current Values (last closed candle usually)
        # Using -1 as "current completed candle" for signal
        i = len(data) - 1
        
        c_price = close.iloc[i]
        c_ema_fast = ema_fast.iloc[i]
        c_ema_slow = ema_slow.iloc[i]
        c_ema7 = ema7.iloc[i]
        c_ema200 = ema200.iloc[i]
        c_rsi = rsi.iloc[i]
        c_vol = volume.iloc[i]
        c_vol_avg = vol_sma.iloc[i]
        # Dynamic Volume: 80th Percentile of last 100 bars
        vol_p80 = volume.iloc[max(0, i-100):i].quantile(0.8) if i > 10 else c_vol_avg
        c_atr = atr.iloc[i]

        # --- 2. MQ5 Professional Logic ---
        # (Legacy market structure, trend alignment, and divergence logic removed)

        # --- 5. Signal Generation (MQ5 Professional Logic) ---
        signal = 'HOLD'
        reason = []
        
        # Time Filter Check
        now = datetime.datetime.utcnow()
        if self.use_time_filter:
            start_dt = datetime.datetime.strptime(self.start_time, "%H:%M").time()
            end_dt = datetime.datetime.strptime(self.end_time, "%H:%M").time()
            if not (start_dt <= now.time() <= end_dt):
                return {'type': 'HOLD', 'price': c_price, 'atr': c_atr, 'rsi': c_rsi, 'reason': 'Outside trading hours'}

        # Friday Close Check
        if self.friday_close and now.weekday() == 4 and now.hour >= self.friday_close_hour:
             return {'type': 'HOLD', 'price': c_price, 'atr': c_atr, 'rsi': c_rsi, 'reason': 'Friday Close Time'}
             
        # Check Crossover Confirmation (Confirm over multiple bars)
        # MQ5 logic: Fast > Slow for last 'bars_for_signal' bars AND Fast < Slow before that
        def check_crossover(fast_series, slow_series, count, side):
            # Check current and previous 'count' bars
            for shift in range(count + 1):
                idx = i - shift
                if side == 'buy':
                    if fast_series.iloc[idx] <= slow_series.iloc[idx]:
                        return False
                else: # sell
                    if fast_series.iloc[idx] >= slow_series.iloc[idx]:
                        return False
            
            # Check the bar before that was on opposite side (the cross)
            prev_idx = i - (count + 1)
            if side == 'buy':
                return fast_series.iloc[prev_idx] < slow_series.iloc[prev_idx]
            else:
                return fast_series.iloc[prev_idx] > slow_series.iloc[prev_idx]

        # Tighter 7/21 Momentum Check
        momentum_long = c_ema7 > c_ema_slow and ema7.iloc[i-1] <= ema_slow.iloc[i-1]
        momentum_short = c_ema7 < c_ema_slow and ema7.iloc[i-1] >= ema_slow.iloc[i-1]

        # Reactive bars confirmation
        # If strong volume or engulfing, we only need 1 bar (the current one)
        is_high_vol = c_vol > vol_p80 * 1.5
        is_long_engulfing = c_price > high.iloc[i-1] and close.iloc[i-1] < open_prices.iloc[i-1]
        is_short_engulfing = c_price < low.iloc[i-1] and close.iloc[i-1] > open_prices.iloc[i-1]
        
        required_bars = self.bars_for_signal
        if is_high_vol or is_long_engulfing or is_short_engulfing:
            required_bars = 1

        buy_cross = check_crossover(ema_fast, ema_slow, required_bars, 'buy') or momentum_long
        sell_cross = check_crossover(ema_fast, ema_slow, required_bars, 'sell') or momentum_short

        # RSI Swing Filter: Oversold bounce (crossing 40 from below)
        rsi_bullish_swing = rsi.iloc[i-1] < 40 and c_rsi >= 40
        rsi_bearish_swing = rsi.iloc[i-1] > 60 and c_rsi <= 60

        # LONG Logic
        if buy_cross or rsi_bullish_swing:
            # TREND FILTER: Price must be above EMA 200 for Long
            if c_price > c_ema200:
                # RSI Confirmation: Not overbought
                if c_rsi < self.rsi_overbought:
                    signal = 'BUY'
                    if is_high_vol or rsi_bullish_swing:
                        weight = 1.0
                        reason.append(f"BUY: Momentum swing detected ({'RSI bounce' if rsi_bullish_swing else 'EMA cross'}) + High Vol.")
                    else:
                        weight = 0.5
                        reason.append(f"BUY: Trend confirmed. (EMA 9/21 cross)")
                else:
                    reason.append(f"Buy setup ignored: RSI ({c_rsi:.2f}) overbought.")
            else:
                 reason.append(f"Buy setup ignored: Price ({c_price:.2f}) below EMA 200 filter.")
                 
        # SHORT Logic
        elif sell_cross or rsi_bearish_swing:
            # TREND FILTER: Price must be below EMA 200 for Short
            if c_price < c_ema200:
                # RSI Confirmation: Not oversold
                if c_rsi > self.rsi_oversold:
                    signal = 'SELL'
                    if is_high_vol or rsi_bearish_swing:
                        weight = 1.0
                        reason.append(f"SELL: Momentum swing detected ({'RSI drop' if rsi_bearish_swing else 'EMA cross'}) + High Vol.")
                    else:
                        weight = 0.5
                        reason.append(f"SELL: Trend confirmed. (EMA 9/21 cross)")
                else:
                    reason.append(f"Sell setup ignored: RSI ({c_rsi:.2f}) oversold.")
            else:
                 reason.append(f"Sell setup ignored: Price ({c_price:.2f}) above EMA 200 filter.")

        if signal == 'HOLD' and not reason:
            reason.append("Searching for swing transition...")

        # --- 6. Risk Management Output ---
        if signal != 'HOLD':
            # Enforce minimum trade interval
            now = datetime.datetime.utcnow()
            if self.last_trade_timestamp and (now - self.last_trade_timestamp) < self.min_trade_interval:
                # Too soon since last trade, treat as HOLD
                signal = 'HOLD'
            else:
                self.last_trade_timestamp = now
                side = 'long' if signal == 'BUY' else 'short'
                
                sl_price = None
                
                # Use RiskManager to compute stops with configured multipliers
                stops = self.rm.get_stop_targets(
                    entry_price=c_price,
                    atr=c_atr,
                    side=side,
                    structure_stop=sl_price,
                    tp_multipliers=self.tp_atr_multipliers,
                    sl_multiplier=self.sl_atr_multiplier
                )
                
                return {
                    'type': signal,
                    'price': c_price,
                    'sl': stops.get('sl'),
                    'tp1': stops.get('tp1'),
                    'tp2': stops.get('tp2'),
                    'tp3': stops.get('tp3'),
                    'atr': c_atr,
                    'rsi': c_rsi,
                    'reason': ", ".join(reason) if reason else "No specific reason"
                }
        
        return {
            'type': 'HOLD',
            'price': c_price,
            'atr': c_atr,
            'rsi': c_rsi,
            'reason': ", ".join(reason) if reason else "Searching for setup..."
        }
