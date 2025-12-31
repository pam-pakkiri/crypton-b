import pandas as pd
import numpy as np

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean() # Simple Mean for speed/simplicity
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Use Wilder's Smoothing for better accuracy if needed, but Rolling is standard for many
    # To match 'standard' RSI, we often use EWMA
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()

    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    dataset = pd.DataFrame({'high': high, 'low': low, 'close': close})
    dataset['tr0'] = dataset['high'] - dataset['low']
    dataset['tr1'] = np.abs(dataset['high'] - dataset['close'].shift(1))
    dataset['tr2'] = np.abs(dataset['low'] - dataset['close'].shift(1))
    dataset['tr'] = dataset[['tr0', 'tr1', 'tr2']].max(axis=1)
    return dataset['tr'].ewm(alpha=1/period, adjust=False).mean()

def detect_swings(df: pd.DataFrame, window: int = 5):
    """
    Identify Swing Highs and Lows.
    Returns boolean columns 'is_swing_high', 'is_swing_low'.
    A valid swing point is confirmed after 'window' candles.
    """
    df['is_swing_high'] = False
    df['is_swing_low'] = False
    
    # We use shifting to check neighbors
    # For a swing high at index i, high[i] must be max of i-window to i+window
    # NOTE: This uses LOOKAHEAD. In live trading, we detect this at i+window.
    # The backtester must respect this delay.
    
    # For Signal Generation at time T:
    # We check if a swing confirmed at T-Window (or newly confirmed now).
    # Actually, simpler: 
    # Current Candle T. 
    # Did T-window just become a swing high?
    # Yes if T-window is max of [T-2*window, T]
    
    # Let's vectorize simple pivot detection
    # A point is a pivot high if it's highest in window around it.
    
    # We will just mark them based on past. 
    # At index 'i', we want to know what the RECENT confirmed swings were.
    
    # Implementation:
    # We iterate? Vectorized:
    # Use rolling max centered.
    
    # But for strict production logic:
    # Just look at peaks.
    pass # logic handled inside class or refined below
    
    # Let's implement a robust iterate (slower but correct logic) or smart shift
    # Shift approach:
    # 0 is potential pivot
    # check 1..window left < 0
    # check 1..window right < 0
    
    # Since we need this for "Market Structure" (HH/HL), we need a list of pivots.
    
    # Let's return just the indicator series for use by strategy
    # Strategy will handle lookback to find recent ones.
    return df

def get_recent_swings(df: pd.DataFrame, window=5):
    """
    Returns list of (index, price, type) for confirmed swings.
    Confirmed means we are 'window' bars past the pivot.
    """
    swings = []
    # Optimization: Iterate only necessary?
    # For full backtest, we iterate all.
    # We can detect if i-window was a pivot.
    
    highs = df['high'].values
    lows = df['low'].values
    
    for i in range(window, len(df) - window):
        # Potential High at i
        if all(highs[i] > highs[i-k] for k in range(1, window+1)) and \
           all(highs[i] > highs[i+k] for k in range(1, window+1)):
             swings.append({'index': i, 'price': highs[i], 'type': 'high', 'time': df.iloc[i]['timestamp']})
             
        # Potential Low at i
        if all(lows[i] < lows[i-k] for k in range(1, window+1)) and \
           all(lows[i] < lows[i+k] for k in range(1, window+1)):
             swings.append({'index': i, 'price': lows[i], 'type': 'low', 'time': df.iloc[i]['timestamp']})
             
    return swings

def check_divergence(price_series, rsi_series, window=5):
    """
    Check for divergence between Price and RSI.
    """
    # Simple logic:
    # Bullish Div: Price Made Lower Low, RSI Made Higher Low
    # Bearish Div: Price Made Higher High, RSI Made Lower High
    
    # This requires looking at the last two peaks/troughs.
    pass # Implemented in Strategy using get_recent_swings
