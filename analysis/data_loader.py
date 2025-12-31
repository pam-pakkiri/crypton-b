from execution.binance_client import BinanceClient

class DataLoader:
    def __init__(self, client: BinanceClient):
        self.client = client

    def get_historical_data(self, symbol, timeframe, limit=1000):
        """
        Wrapper to fetch data from the client
        """
        print(f"Fetching {limit} candles for {symbol} on {timeframe} timeframe...")
        df = self.client.fetch_ohlcv(symbol, timeframe, limit)
        if df is not None:
             print(f"Successfully fetched {len(df)} rows.")
        return df
