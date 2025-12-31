import requests

def test_order_book():
    url = "https://testnet.binancefuture.com/fapi/v1/depth"
    params = {"symbol": "BTCUSDT", "limit": 10}
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_order_book()
