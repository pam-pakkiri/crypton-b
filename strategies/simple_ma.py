import pandas as pd
from strategies.base_strategy import BaseStrategy

class SimpleMAStrategy(BaseStrategy):
    def __init__(self, short_window=20, long_window=50):
        super().__init__("SimpleMA")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, data: pd.DataFrame) -> dict:
        if data is None or data.empty or len(data) < self.long_window:
            return {'type': 'HOLD', 'price': 0, 'reason': 'Insufficient data'}

        # Calculate Moving Averages
        data['short_mavg'] = data['close'].rolling(window=self.short_window, min_periods=1).mean()
        data['long_mavg'] = data['close'].rolling(window=self.long_window, min_periods=1).mean()

        # Get the last two rows to check for crossover
        last_row = data.iloc[-1]
        prev_row = data.iloc[-2]

        signal = 'HOLD'
        reason = ''
        
        # Crossover logic: Short crosses above Long (GOLDEN CROSS) -> BUY
        if prev_row['short_mavg'] <= prev_row['long_mavg'] and last_row['short_mavg'] > last_row['long_mavg']:
            signal = 'BUY'
            reason = 'Golden Cross (Short MA crossed above Long MA)'
        
        # Crossover logic: Short crosses below Long (DEATH CROSS) -> SELL
        elif prev_row['short_mavg'] >= prev_row['long_mavg'] and last_row['short_mavg'] < last_row['long_mavg']:
            signal = 'SELL'
            reason = 'Death Cross (Short MA crossed below Long MA)'

        return {
            'type': signal,
            'price': last_row['close'],
            'reason': reason
        }
