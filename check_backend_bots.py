import requests
import json

def check_backend():
    try:
        resp = requests.get("http://localhost:8000/bot/status")
        if resp.status_code == 200:
            data = resp.json()
            print("Active Bots:", [b['symbol'] for b in data.get('active_bots', [])])
            print("Positions:", len(data.get('positions', [])))
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    check_backend()
