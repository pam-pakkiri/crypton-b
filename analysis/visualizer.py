import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from analysis.indicators import calculate_ema

class Visualizer:
    def __init__(self, data: pd.DataFrame, trades: list = None):
        self.data = data
        self.trades = trades

    def plot(self, title="Backtest Results"):
        # Create figure with secondary y-axis
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, subplot_titles=(title, 'Volume'), 
                            row_width=[0.2, 0.7])

        # 1. Candlestick
        fig.add_trace(go.Candlestick(x=self.data['timestamp'],
                        open=self.data['open'],
                        high=self.data['high'],
                        low=self.data['low'],
                        close=self.data['close'],
                        name='Price'), row=1, col=1)

        # 2. EMAs
        ema20 = calculate_ema(self.data['close'], 20)
        ema50 = calculate_ema(self.data['close'], 50)
        ema200 = calculate_ema(self.data['close'], 200)

        fig.add_trace(go.Scatter(x=self.data['timestamp'], y=ema20, line=dict(color='blue', width=1), name='EMA 20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=self.data['timestamp'], y=ema50, line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
        fig.add_trace(go.Scatter(x=self.data['timestamp'], y=ema200, line=dict(color='red', width=1), name='EMA 200'), row=1, col=1)

        # 3. Buy/Sell Markers
        if self.trades:
            buy_times = [t['time'] for t in self.trades if t['type'] == 'BUY']
            buy_prices = [t['price'] for t in self.trades if t['type'] == 'BUY']
            sell_times = [t['time'] for t in self.trades if t['type'] == 'SELL']
            sell_prices = [t['price'] for t in self.trades if t['type'] == 'SELL']
            
            fig.add_trace(go.Scatter(x=buy_times, y=buy_prices, mode='markers', marker=dict(symbol='triangle-up', color='green', size=10), name='Buy Signal'), row=1, col=1)
            fig.add_trace(go.Scatter(x=sell_times, y=sell_prices, mode='markers', marker=dict(symbol='triangle-down', color='red', size=10), name='Sell Signal'), row=1, col=1)

        # 4. Volume
        fig.add_trace(go.Bar(x=self.data['timestamp'], y=self.data['volume'], name='Volume'), row=2, col=1)

        fig.update_layout(xaxis_rangeslider_visible=False, height=800, title_text="Advanced Algo Strategy")
        
        # Save to HTML
        output_file = "backtest_result.html"
        fig.write_html(output_file)
        print(f"Chart saved to {output_file}")
