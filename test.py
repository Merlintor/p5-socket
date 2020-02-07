import websockets
import asyncio
import json

from server import Opcodes


async def test():
    async with websockets.connect("ws://localhost:80") as ws:
        while True:
            msg = await ws.recv()
            msg = json.loads(msg)
            print(msg)
            op = msg.get("op")
            d = msg.get("d")

            if op == Opcodes.HELLO:
                # Subscribe to all available events
                await ws.send(json.dumps({
                    "op": Opcodes.EVENTS_UPDATE,
                    "events": d["events"]
                }))

            elif op == Opcodes.HEARTBEAT:
                # Respond to heartbeat
                await ws.send(json.dumps({
                    "op": Opcodes.HEARTBEAT_ACK
                }))

            # Test dispatch
            await ws.send(json.dumps({
                "op": Opcodes.DISPATCH,
                "d": {
                    "t": "move",
                    "p": [123, 321]
                }
            }))


loop = asyncio.get_event_loop()
loop.run_until_complete(test())
