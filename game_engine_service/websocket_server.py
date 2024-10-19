import asyncio
import websockets
import json

connected_clients = set()

async def handler(websocket, path):
    # Register client
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            print(f"Received message: {data}")

            # Broadcast the message to all connected clients
            for client in connected_clients:
                if client != websocket:
                    await client.send(json.dumps(data))
    except websockets.ConnectionClosed:
        print("Connection closed")
    finally:
        # Unregister client
        connected_clients.remove(websocket)

async def main():
    async with websockets.serve(handler, "localhost", 5003):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())