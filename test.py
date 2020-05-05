import aiohttp
import asyncio
import json

from protocol import Opcodes


async def side_test(ws):
    await ws.send_json({
        "op": Opcodes.HEARTBEAT
    })
    await asyncio.sleep(1)
    await ws.send_json({
        "op": Opcodes.DISPATCH,
        "d": {
            "t": "test",
            "p": {"test": "payload"}
        }
    })


async def run_test():
    session = aiohttp.ClientSession()
    async with session.ws_connect("http://localhost:420/ws") as ws:
        asyncio.get_event_loop().create_task(side_test(ws))
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                msg_data = json.loads(msg.data)
                op = msg_data.get("op")
                d = msg_data.get("d")

                print(op, d)
                if op == Opcodes.HEARTBEAT:
                    await ws.send_json({
                        "op": Opcodes.HEARTBEAT_ACK
                    })

            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(msg)

        print(ws.close_code)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_test())
