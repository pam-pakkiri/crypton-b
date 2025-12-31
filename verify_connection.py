from config import BINANCE_API_KEY, BINANCE_API_SECRET
import hashlib
import hmac
import requests
import time

def verify():
    k = str(BINANCE_API_KEY)
    s = str(BINANCE_API_SECRET)
    
    print(f"DEBUG: API Key starts with: '{k[:4]}'")
    
    # Simple authenticated request to Futures Testnet
    base_url = "https://testnet.binancefuture.com"
    endpoint = "/fapi/v2/account"
    
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(s.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    
    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": k}
    
    print(f"Requesting: {base_url}{endpoint}")
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
