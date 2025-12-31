import asyncio
import websockets
import json

async def test_relay():
    uri = "ws://127.0.0.1:8000/ws"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to Local Relay!")
            while True:
                msg = await websocket.recv()
                data = json.loads(msg)
                if 'e' in data:
                    print(f"Received Event: {data['e']} for {data.get('s')}")
                else:
                    print(f"Other Msg: {msg[:100]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_relay())
