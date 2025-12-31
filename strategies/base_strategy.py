from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> dict:
        """
        Analyze data and return a signal.
        Return dict format: {'type': 'BUY'|'SELL'|'HOLD', 'price': float, 'reason': str}
        """
        pass
