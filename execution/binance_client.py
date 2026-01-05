import ccxt
import pandas as pd
import hashlib
import hmac
import time
import requests
from config import BINANCE_API_KEY, BINANCE_API_SECRET

class BinanceClient:
    def __init__(self, testnet=True): # Default to testnet for safety during development
        self.testnet = testnet
        # 1. Public exchange for OHLCV data (Always Mainnet)
        self.public_exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # 2. Private exchange for trading
        self.exchange = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True
            }
        })
        if testnet:
            self.public_exchange.set_sandbox_mode(True)
            self.exchange.set_sandbox_mode(True)
            print("Client initialized in TESTNET mode (sandbox).")
        else:
            print("Client initialized in MAINNET mode. USE WITH CAUTION.")

    def get_server_time(self):
        """Fetch server time from Binance to handle clock drift."""
        try:
            res = requests.get("https://fapi.binance.com/fapi/v1/time")
            if res.status_code == 200:
                return res.json()['serverTime']
        except:
            pass
        return int(time.time() * 1000)

    def _request(self, method, endpoint, params={}):
        """Helper to call Binance Futures Testnet API directly."""
        if not self.testnet:
             return None
             
        base_url = "https://testnet.binancefuture.com"
        
        # Fixed: Calculate offset once or periodically
        # For simplicity in this direct helper, we'll use a conservative recvWindow
        # and ensure the timestamp is fresh.
        server_time = self.get_server_time()
        timestamp = server_time
        
        # Build query string with larger recvWindow
        query_params = {**params, "timestamp": timestamp, "recvWindow": 10000}
        query_string = "&".join([f"{k}={v}" for k, v in query_params.items()])
        
        # Sign
        signature = hmac.new(BINANCE_API_SECRET.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
        full_url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        
        if method.upper() == 'GET':
            resp = requests.get(full_url, headers=headers)
        elif method.upper() == 'POST':
            resp = requests.post(full_url, headers=headers)
        elif method.upper() == 'DELETE':
            resp = requests.delete(full_url, headers=headers)
        else:
            return None

        if resp is not None and resp.status_code != 200:
            # Suppress "No need to change margin type" and "Leverage reduction not supported" errors
            if '"code":-4046' not in resp.text and '"code":-4161' not in resp.text:
                print(f"Binance API Error [{resp.status_code}] on {endpoint}: {resp.text}")
            
        return resp

    def fetch_ohlcv(self, symbol, timeframe, limit=1000):
        try:
            # Use public_exchange to avoid 'Invalid API Key' errors on public data
            ohlcv = self.public_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None

    def get_balance(self):
        try:
            response = self._request('GET', "/fapi/v2/account")
            if response is not None and response.status_code == 200:
                res = response.json()
                balance = {'total': {}, 'assets': []}
                if 'assets' in res:
                    for asset in res['assets']:
                        wallet_bal = float(asset['walletBalance'])
                        if wallet_bal > 0:
                            balance['assets'].append({
                                'asset': asset['asset'],
                                'balance': wallet_bal,
                                'unrealizedProfit': float(asset['unrealizedProfit'])
                            })
                            if asset['asset'] == 'USDT':
                                balance['total']['USDT'] = wallet_bal
                return balance
            return None
        except Exception as e:
            print(f"Exception fetching balance: {e}")
            return None

    def get_ticker(self, symbol):
        try:
            return self.public_exchange.fetch_ticker(symbol)
        except Exception as e:
            print(f"Error fetching ticker for {symbol}: {e}")
            return None

    def get_funding_rate(self, symbol):
        """Fetch funding rate using the premium index endpoint."""
        try:
            b_symbol = symbol.replace('/', '')
            params = {"symbol": b_symbol}
            response = self._request('GET', "/fapi/v1/premiumIndex", params)
            if response is not None and response.status_code == 200:
                data = response.json()
                return float(data.get('lastFundingRate', 0))
            return 0.0
        except Exception as e:
            print(f"Error fetching funding rate for {symbol}: {e}")
            return 0.0

    def get_all_tickers(self, symbols=None):
        try:
            tickers = self.public_exchange.fetch_tickers(symbols)
            return tickers
        except Exception as e:
            print(f"Error fetching all tickers: {e}")
            return {}

    def get_all_funding_rates(self):
        try:
            response = self._request('GET', "/fapi/v1/premiumIndex")
            if response is not None and response.status_code == 200:
                data = response.json()
                # Return a dict {symbol: rate}
                return {item['symbol']: float(item['lastFundingRate']) for item in data}
            return {}
        except Exception as e:
            print(f"Error fetching all funding rates: {e}")
            return {}

    def get_ticker_direct(self, symbol):
        """Fetch ticker directly from API if CCXT fails or is slow."""
        try:
            b_symbol = symbol.replace('/', '')
            params = {"symbol": b_symbol}
            response = self._request('GET', "/fapi/v1/ticker/24hr", params)
            if response is not None and response.status_code == 200:
                data = response.json()
                return {
                    "last": float(data['lastPrice']),
                    "percentage": float(data['priceChangePercent']),
                    "high": float(data['highPrice']),
                    "low": float(data['lowPrice'])
                }
            return None
        except Exception as e:
            print(f"Error in direct ticker fetch for {symbol}: {e}")
            return None

    def create_order(self, symbol, type, side, amount, price=None, params={}):
        try:
            # Binance API uses Symbols like 'BTCUSDT' (no slash)
            b_symbol = symbol.replace('/', '')
            data = {
                "symbol": b_symbol,
                "side": side.upper(),
                "type": type.upper(),
                "quantity": amount
            }
            if price:
                data["price"] = price
            
            # Special handling for LIMIT orders: timeInForce is MANDATORY on Binance Futures
            if type.upper() == 'LIMIT' and 'timeInForce' not in params:
                data['timeInForce'] = 'GTC'
                
            # Merge additional params (like stopPrice, reduceOnly)
            if params:
                data.update(params)
                
            response = self._request('POST', "/fapi/v1/order", data)
            if response is not None and response.status_code == 200:
                print(f"Order Success: {response.json()}")
                return response.json()
            else:
                err_msg = response.text if response is not None else "No Response"
                print(f"Order Failed: {err_msg}")
                return None
        except Exception as e:
            print(f"Exception creating order: {e}")
            return None
            
    def set_leverage(self, symbol, leverage):
        try:
            b_symbol = symbol.replace('/', '')
            response = self._request('POST', "/fapi/v1/leverage", {"symbol": b_symbol, "leverage": leverage})
            if response is not None and response.status_code == 200:
                print(f"Leverage set to {leverage}x for {symbol}")
            else:
                err_msg = response.text if response is not None else "No Response"
                if '"code":-4161' not in err_msg:
                    print(f"Error setting leverage: {err_msg}")
        except Exception as e:
            print(f"Exception setting leverage: {e}")
            
    def set_margin_mode(self, symbol, marginType='isolated'):
        try:
            b_symbol = symbol.replace('/', '')
            response = self._request('POST', "/fapi/v1/marginType", {"symbol": b_symbol, "marginType": marginType.upper()})
            if response is not None and response.status_code == 200:
                 print(f"Margin mode set to {marginType} for {symbol}")
            else:
                pass
        except Exception as e:
            # Suppress "No need to change margin type" errors
            if "-4046" not in str(e):
                print(f"Note on setting margin mode: {e}")

    def get_order_book(self, symbol, limit=20):
        try:
            b_symbol = symbol.replace('/', '')
            # Endpoint is /fapi/v1/depth
            params = {"symbol": b_symbol, "limit": limit}
            response = self._request('GET', "/fapi/v1/depth", params)
            if response is not None and response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Exception fetching order book: {e}")
            return None

    def get_positions(self):
        try:
            # We want /fapi/v2/positionRisk
            response = self._request('GET', "/fapi/v2/positionRisk")
            if response is not None and response.status_code == 200:
                pos_data = response.json()
                active_pos = []
                for p in pos_data:
                    amt = float(p['positionAmt'])
                    if amt != 0:
                        active_pos.append({
                            'symbol': p['symbol'],
                            'size': amt,
                            'entryPrice': float(p['entryPrice']),
                            'markPrice': float(p['markPrice']),
                            'unrealizedProfit': float(p['unRealizedProfit']),
                            'liquidationPrice': float(p.get('liquidationPrice', 0)),
                            'marginRatio': float(p.get('marginRatio', 0)),
                            'breakEvenPrice': float(p.get('breakEvenPrice', 0)),
                            'leverage': p['leverage'],
                            'marginType': p['marginType']
                        })
                return active_pos
            return []
        except Exception as e:
            print(f"Exception fetching positions: {e}")
            return []

    def get_open_orders(self, symbol=None):
        try:
            params = {}
            if symbol:
                params['symbol'] = symbol.replace('/', '')
                
            response = self._request('GET', "/fapi/v1/openOrders", params)
            if response is not None and response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Exception fetching open orders: {e}")
            return []

    def cancel_order(self, symbol, order_id):
        try:
            b_symbol = symbol.replace('/', '')
            params = {"symbol": b_symbol, "orderId": order_id}
            response = self._request('DELETE', "/fapi/v1/order", params)
            if response is not None and response.status_code == 200:
                print(f"Order {order_id} cancelled for {symbol}")
                return True
            return False
        except Exception as e:
            print(f"Exception cancelling order: {e}")
            return False

    def cancel_all_orders(self, symbol):
        try:
            b_symbol = symbol.replace('/', '')
            params = {"symbol": b_symbol}
            response = self._request('DELETE', "/fapi/v1/allOpenOrders", params)
            if response is not None and response.status_code == 200:
                print(f"All open orders cancelled for {symbol}")
                return True
            return False
        except Exception as e:
            print(f"Exception cancelling all orders: {e}")
            return False

    def get_trade_history_manual(self, symbol, limit=50):
        """
        Manually fetch trade history from Binance Futures API to bypass CCXT Testnet deprecation issues.
        Returns a list of dicts that mimics CCXT structure enough for the frontend.
        """
        try:
            b_symbol = symbol.replace('/', '')
            params = {"symbol": b_symbol, "limit": limit}
            response = self._request('GET', "/fapi/v1/userTrades", params)
            
            if response is not None and response.status_code == 200:
                raw_trades = response.json()
                # Sort by time descending (newest first)
                raw_trades.sort(key=lambda x: x['time'], reverse=True)
                
                formatted = []
                for t in raw_trades:
                    formatted.append({
                        "id": str(t['id']),
                        "timestamp": t['time'],
                        "datetime": pd.to_datetime(t['time'], unit='ms').isoformat(),
                        "symbol": symbol, # Use the slash formatting
                        "side": t['side'].lower(),
                        "price": float(t['price']),
                        "amount": float(t['qty']),
                        "pnl": float(t['realizedPnl']),
                        "fee": float(t['commission']),
                        "info": t
                    })
                return formatted
            return []
        except Exception as e:
            print(f"Manual history fetch error: {e}")
            return []
