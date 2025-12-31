import asyncio
import json
import os
import sys

# Mocking config and other things if needed or just importing
sys.path.append(os.getcwd())

from execution.binance_client import BinanceClient
from strategies.smart_futures_strategy import SmartFuturesStrategy
from execution.risk_manager import RiskManager
from execution.trader import LiveTrader

def test_init():
    print("Step 1: Initializing BinanceClient...")
    client = BinanceClient(testnet=True)
    print("Done.")
    
    print("Step 2: Initializing RiskManager...")
    rm = RiskManager(account_size=15000, risk_per_trade=0.01)
    print("Done.")

    print("Step 3: Initializing Strategy...")
    strategy = SmartFuturesStrategy(risk_manager=rm)
    print("Done.")

    print("Step 4: Initializing LiveTrader...")
    trader = LiveTrader(client, strategy, risk_manager=rm)
    print("Done.")
    return trader

async def test_ws_stream():
    import websockets
    uri = "wss://fstream.binance.com/ws"
    print(f"Step 5: Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            subscribe_msg = {
                "method": "SUBSCRIBE",
                "params": ["btcusdt@ticker"],
                "id": 1
            }
            await websocket.send(json.dumps(subscribe_msg))
            print("Subscribed. Waiting for message...")
            data = await websocket.recv()
            print(f"Received: {data[:100]}")
    except Exception as e:
        print(f"WS Error: {e}")

if __name__ == "__main__":
    test_init()
    asyncio.run(test_ws_stream())
    print("Debug script finished.")
