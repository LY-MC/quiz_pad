import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:5003"
    async with websockets.connect(uri) as websocket:
        print("Connection opened")

        # Send a test message
        await websocket.send(json.dumps({"answer": "test_answer"}))
        print("Sent test message")

        try:
            while True:
                message = await websocket.recv()
                print(f"Received message: {message}")
        except websockets.ConnectionClosed:
            print("Connection closed")

if __name__ == "__main__":
    asyncio.run(test_websocket())