import os
import threading
import json
import asyncio
from fastapi import FastAPI, BackgroundTasks, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from config import BINANCE_API_KEY, BINANCE_API_SECRET, SYMBOL, TIMEFRAME
from execution.binance_client import BinanceClient
# from execution.binance_client import BinanceClient
from strategies.smart_futures_strategy import SmartFuturesStrategy
from strategies.institutional_strategy import InstitutionalStrategy
from strategies.scalping_strategy import ScalpingStrategy
from execution.risk_manager import RiskManager
from execution.trader import LiveTrader

class BotConfig(BaseModel):
    symbol: str = "BTC/USDT"
    leverage: int = 5
    margin_mode: str = "isolated"
    risk_per_trade: float = 0.01
    trade_amount: float = 100.0  # Default budget per trade
    strategy: str = "mq5"  # mq5 or institutional

class ManualTrade(BaseModel):
    symbol: str
    side: str
    amount: float
    price: float = None
    type: str = "market"

class ClosePosition(BaseModel):
    symbol: str
    side: str
    amount: float

app = FastAPI(title="Algo Trade Bot API")

# Configure CORS to allow requests from the Next.js frontend
import os

# Determine if we are running in production (set PRODUCTION=1 in env)
IS_PRODUCTION = os.getenv("PRODUCTION", "0") == "1"

# CORS origins – allow only the production domain when in prod, otherwise allow local dev URLs
if IS_PRODUCTION:
    origins = ["https://crypton0.com"]
else:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global bot state: {symbol: trader_instance}
traders = {}
bot_threads = {}

# Internal shared client for general read-only queries
_shared_client = None

def get_shared_client():
    global _shared_client
    if _shared_client is None:
        # Use testnet in development, mainnet in production
        _shared_client = BinanceClient(testnet=not IS_PRODUCTION)
    return _shared_client

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

async def binance_ws_stream():
    """Background task to stream from Binance and broadcast to clients"""
    import websockets
    # Use Testnet Stream to match BinanceClient(testnet=True)
    uri = "wss://stream.binancefuture.com/ws"
    
    # Track current subscriptions to avoid duplicates
    subscribed_symbols = set()
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                # Initial default symbols + any active traders
                base_symbols = {"btcusdt", "ethusdt", "solusdt", "bnbusdt", "xrpusdt", "dogeusdt", "adausdt", "bchusdt", "ltcusdt", "trxusdt", "etcusdt", "linkusdt"}
                
                while True:
                    # Check for new traders that need subscription
                    current_symbols = base_symbols.union({s.replace('/', '').lower() for s in traders.keys()})
                    new_symbols = current_symbols - subscribed_symbols
                    
                    if new_symbols:
                        params = []
                        for s in new_symbols:
                            params.append(f"{s}@ticker")
                            params.append(f"{s}@depth20@100ms")
                        
                        subscribe_msg = {
                            "method": "SUBSCRIBE",
                            "params": params,
                            "id": 1
                        }
                        await websocket.send(json.dumps(subscribe_msg))
                        subscribed_symbols.update(new_symbols)
                    
                    # Receive data with timeout to allow checking for new subscriptions
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        await manager.broadcast(data)
                    except asyncio.TimeoutError:
                        continue
        except Exception as e:
            print(f"WebSocket Relay Error: {e}")
            subscribed_symbols.clear()
            await asyncio.sleep(5)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def init_bot(symbol=SYMBOL, strategy_type="mq5", force_update=False):
    if symbol in traders:
        current_trader = traders[symbol]
        # Check if we need to switch strategy
        current_strat_name = current_trader.strategy.name
        
        # Map input types to class names for comparison
        target_strat_map = {
            "mq5": "SmartFuturesStrategy",
            "institutional": "InstitutionalStrategy",
            "scalping": "ScalpingStrategy"
        }
        target_name = target_strat_map.get(strategy_type, "SmartFuturesStrategy")
        
        if not force_update and current_strat_name == target_name:
            return current_trader
            
        print(f"Re-initializing {symbol}: Switching from {current_strat_name} to {strategy_type}...")
        if current_trader.running:
            current_trader.stop()
        del traders[symbol]
        
    print(f"Initializing components for {symbol} with strategy {strategy_type}...")
    client = BinanceClient(testnet=not IS_PRODUCTION)
    rm = RiskManager(account_size=15000, risk_per_trade=0.01)
    
    if strategy_type == "institutional":
        strategy = InstitutionalStrategy(risk_manager=rm)
    elif strategy_type == "scalping":
        strategy = ScalpingStrategy(risk_manager=rm)
    else:
        strategy = SmartFuturesStrategy(risk_manager=rm)
        
    trader = LiveTrader(client, strategy, risk_manager=rm, symbol=symbol, timeframe=TIMEFRAME)
    trader.leverage = 5
    trader.trade_amount = 100.0
    traders[symbol] = trader
    return trader

@app.on_event("startup")
async def startup_event():
    print("Algo Trade Bot API Starting...")
    try:
        # Start the WebSocket relay in the background
        asyncio.create_task(binance_ws_stream())
        print("Algo Trade Bot API & WebSocket Relay Started")
    except Exception as e:
        print(f"Error during startup: {e}")

@app.get("/")
def root():
    return {"status": "running", "message": "Algo Trade Bot API is running"}

@app.get("/ping")
def ping():
    return "pong"

@app.get("/health")
def health_check():
    return {"status": "online"}

@app.post("/bot/start")
def start_bot(background_tasks: BackgroundTasks, config: BotConfig = None):
    symbol = config.symbol if config else SYMBOL
    strategy_type = config.strategy if config else "mq5"
    
    force_update = False
    if symbol in traders:
        # If running with DIFFERENT strategy, force update
        current = traders[symbol]
        
        target_strat_map = {
            "mq5": "SmartFuturesStrategy",
            "institutional": "InstitutionalStrategy",
            "scalping": "ScalpingStrategy"
        }
        target_name = target_strat_map.get(strategy_type, "SmartFuturesStrategy")
        
        if current.strategy.name != target_name:
            print(f"Strategy switch detected: {current.strategy.name} -> {target_name}. Restarting...")
            force_update = True
        elif current.running:
             return {"status": "already_running", "symbol": symbol}
    
    trader = init_bot(symbol, strategy_type, force_update=force_update)
    
    # Update numerical params
    if config:
        trader.leverage = config.leverage
        trader.margin_mode = config.margin_mode
        trader.rm.risk_per_trade = config.risk_per_trade
        trader.trade_amount = config.trade_amount

    def run_trader():
        trader.start(interval=60)
    
    # If thread exists, it will naturally die as 'running' flag is checked inside loop? 
    # Actually trader.start() is a loop. We stopped previous trader so its loop should exit.
    # We must ensure new thread starts.
    thread = threading.Thread(target=run_trader, daemon=True)
    bot_threads[symbol] = thread
    thread.start()
    
    return {"status": "started", "symbol": symbol, "strategy": strategy_type}

@app.post("/bot/stop")
def stop_bot(symbol: str = Body(..., embed=True)):
    if symbol in traders:
        traders[symbol].stop()
        return {"status": "stopping", "symbol": symbol}
    return {"status": "not_found", "symbol": symbol}

@app.post("/bot/config")
def update_config(config: BotConfig):
    symbol = config.symbol
    trader = init_bot(symbol)
    
    # Update trader parameters
    trader.leverage = config.leverage
    trader.margin_mode = config.margin_mode
    trader.rm.risk_per_trade = config.risk_per_trade
    trader.trade_amount = config.trade_amount
    
    print(f"Config updated for {symbol}: {config}")
    return {"status": "updated", "config": config}

@app.get("/tickers")
def get_tickers():
    client = BinanceClient(testnet=not IS_PRODUCTION)
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT", "BCH/USDT", "LTC/USDT", "TRX/USDT", "ETC/USDT", "LINK/USDT"]
    all_funding = client.get_all_funding_rates()
    results = {}
    
    for s in symbols:
        ticker = client.get_ticker_direct(s)
        b_symbol = s.replace('/', '')
        funding = all_funding.get(b_symbol, 0.0)
        
        if ticker:
            results[s] = {
                "last": ticker['last'],
                "percentage": ticker['percentage'],
                "high": ticker['high'],
                "low": ticker['low'],
                "funding": funding
            }
    return results

@app.get("/orderbook")
def get_orderbook(symbol: str = "BTC/USDT", limit: int = 20):
    # Binance valid limits: 5, 10, 20, 50, 100, 500, 1000
    valid_limits = [5, 10, 20, 50, 100, 500, 1000]
    if limit not in valid_limits:
        # Round up to nearest valid limit
        limit = next((x for x in valid_limits if x >= limit), 20)
        
    # Use existing trader client if available, else shared client
    client = traders[symbol].client if symbol in traders else get_shared_client()  # unchanged, but will now respect production flag
    
    print(f"Fetching OrderBook for {symbol} (limit {limit})...")
    book = client.get_order_book(symbol, limit)
    if book:
        print(f"OrderBook fetched: {len(book.get('bids', []))} bids, {len(book.get('asks', []))} asks")
    else:
        print("OrderBook fetch failed or returned None")
        
    return book if book else {"bids": [], "asks": []}

@app.get("/bot/status")
def get_bot_status():
    client = BinanceClient(testnet=not IS_PRODUCTION)
    balance = 0
    assets = []
    positions = []
    open_orders = []
    active_bots = []
    
    try:
        bal_data = client.get_balance()
        if bal_data:
            balance = bal_data['total'].get('USDT', 0)
            assets = bal_data.get('assets', [])
        
        positions = client.get_positions()
        
        # Fetch open orders for active positions only
        # This ensures we get specific orders for the symbols we care about
        active_symbols = [p['symbol'] for p in positions if float(p['size']) != 0]
        # Also include active bot symbols if not in positions yet (just in case pending)
        active_bot_symbols = [s for s in traders.keys()]
        all_checks = set(active_symbols + active_bot_symbols)
        
        for sym in all_checks:
            # Check if this input needs slash or not. Client usually handles it?
            # get_open_orders logic: if symbol provided, replace slash. 
            # Our `all_checks` might have "BTCUSDT" (from positions) or "BTC/USDT" (from traders).
            # Convert to slashed for get_open_orders if needed? No, get_open_orders takes standard symbol (BTC/USDT) or raw?
            # Client.get_open_orders replaces slash locally.
            # Positions return raw "BTCUSDT". Traders keys are "BTC/USDT".
            # Let's normalized to "BTC/USDT" for the call if we can, or just pass as is.
            # Client.get_open_orders handles `replace('/', '')`.
            
            # If sym comes from positions (BTCUSDT), pass it. If from traders (BTC/USDT), pass it.
            orders = client.get_open_orders(sym)
            if orders:
                open_orders.extend(orders)

    except Exception as e:
        print(f"Error fetching status data: {e}")
        pass

    for s, t in traders.items():
        if t.running:
            regime = getattr(t.strategy, 'current_regime', None)
            active_bots.append({
                "symbol": s,
                "leverage": t.leverage,
                "strategy": t.strategy.name,
                "regime": regime.value if regime else "N/A",
                "margin_mode": t.margin_mode,
                "risk": t.rm.risk_per_trade,
                "budget": t.trade_amount,
                "atr": t.last_atr
            })
            
    return {
        "balance": balance,
        "assets": assets,
        "positions": positions,
        "open_orders": open_orders,
        "active_bots": active_bots
    }

@app.post("/bot/trade")
def place_manual_trade(trade: ManualTrade):
    symbol = trade.symbol
    trader = init_bot(symbol) # Ensure we have a client for this symbol
    
    print(f"Manual Trade Request: {trade}")
    try:
        # Re-apply leverage/margin first
        trader.client.set_margin_mode(symbol, trader.margin_mode)
        trader.client.set_leverage(symbol, trader.leverage)
        
        order = trader.client.create_order(
            symbol=symbol,
            type=trade.type,
            side=trade.side.lower(),
            amount=trade.amount,
            price=trade.price
        )
        if order:
            return {"status": "success", "order": order}
        else:
            return {"status": "error", "message": "Order placement failed"}
    except Exception as e:
        print(f"Manual trade exception: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/bot/close_position")
def close_specific_position(req: ClosePosition):
    symbol = req.symbol
    trader = init_bot(symbol)
    
    # Close means opposite side
    side = "sell" if req.side.upper() == "BUY" or req.amount > 0 else "buy"
    abs_amount = abs(req.amount)
    
    print(f"Closing position for {symbol}: {abs_amount} {side}")
    try:
        # Re-apply leverage/margin first for safety
        trader.client.set_margin_mode(symbol, trader.margin_mode)
        trader.client.set_leverage(symbol, trader.leverage)
        
        order = trader.client.create_order(
            symbol=symbol,
            type="market",
            side=side,
            amount=abs_amount,
            params={'reduceOnly': 'true'}
        )
        if order:
            return {"status": "success", "order": order}
        else:
            return {"status": "error", "message": "Failed to close position"}
    except Exception as e:
        print(f"Close position exception: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/history")
def get_trade_history(symbol: str = "BTC/USDT", limit: int = 50):
    client = BinanceClient(testnet=not IS_PRODUCTION)
    try:
        # If symbol is "all" or empty, gather history for active pairs
        symbols = [symbol]
        if not symbol or symbol.lower() == "all":
            try:
                pos = client.get_positions()
                symbols = [p['symbol'].replace('USDT', '/USDT') if 'USDT' in p['symbol'] and '/' not in p['symbol'] else p['symbol'] for p in pos]
                if not symbols:
                    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
            except:
                symbols = ["BTC/USDT", "ETH/USDT"]
        
        all_trades = []
        # Support both slashed and non-slashed symbols by uniqueness
        for s in set(symbols):
            trades = client.get_trade_history_manual(s, limit)
            if trades:
                all_trades.extend(trades)
        
        # Sort and trim
        all_trades.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_trades[:limit]
    except Exception as e:
        print(f"History fetch error: {e}")
        return []

@app.get("/klines")
def get_klines(symbol: str = "BTC/USDT", interval: str = "15m", limit: int = 100):
    client = BinanceClient(testnet=not IS_PRODUCTION)
    try:
        # fetch_ohlcv returns a Pandas DataFrame with columns: timestamp, open, high, low, close, volume
        df = client.fetch_ohlcv(symbol, timeframe=interval, limit=limit)
        
        if df is None or df.empty:
            return []

        formatted = []
        # Iterate over DataFrame rows
        for index, row in df.iterrows():
            formatted.append({
                "time": int(row['timestamp'].timestamp()), # Convert datetime to seconds
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row['volume'])
            })
        return formatted
    except Exception as e:
        print(f"Kline fetch error: {e}")
        return []
        return {"status": "error", "message": str(e)}
