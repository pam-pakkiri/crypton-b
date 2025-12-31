import requests

def test_local_endpoint():
    url = "http://127.0.0.1:8000/orderbook"
    params = {"symbol": "BTC/USDT", "limit": 10}
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_local_endpoint()
