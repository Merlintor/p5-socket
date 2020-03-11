import asyncio
import websockets
import json
import math
import time


class Opcodes:
    DISPATCH = 0  # Dispatch Event
    HELLO = 1  # Send to the client immediately after the connection was established
    MODULES_UPDATE = 2  # Server updates which modules are available
    HEARTBEAT = 10  # Client or Server requests a heartbeat_ack from the other party
    HEARTBEAT_ACK = 11  # Client or Server acknowledges a heartbeat by the other party


class WebSocketConnection(websockets.WebSocketServerProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server = None  # Filled by handle_connection
        self.hb_interval = 10
        self.latency = math.inf  # Difference between the last sent heartbeat and received ack
        self._ack = self.loop.create_future()

    async def send_json(self, data):
        await self.send(json.dumps(data))

    def send_op(self, op, **kwargs):
        return self.send_json({
            "op": op,
            **kwargs
        })

    async def dispatch(self, event, payload):
        await self.send_op(
            Opcodes.DISPATCH,
            d={
                "t": event,
                "p": payload
            }
        )

    async def heartbeat(self):
        """
        Send a heartbeat and wait for the heartbeat_ack
        """
        self._ack = self.loop.create_future()
        await self.send_op(Opcodes.HEARTBEAT)
        await asyncio.wait_for(self._ack, timeout=self.hb_interval)

    async def heartbeat_ack(self):
        """
        Acknowledge a received heartbeat
        """
        await self.send_op(Opcodes.HEARTBEAT_ACK)

    async def events_update(self):
        """
        Called by the server when the available events update
        """
        await self.send_op(Opcodes.EVENTS_UPDATE, d=self.server.events)

    async def message_received(self, msg):
        """
        Parse message data and respond if necessary
        Dispatch messages are dispatched back to the websocket server
        """
        print(msg)
        msg = json.loads(msg)
        op = msg.get("op")
        data = msg.get("d")

        if op != Opcodes.DISPATCH:
            if op == Opcodes.HEARTBEAT:
                # Client requests a heartbeat_ack
                await self.heartbeat_ack()

            elif op == Opcodes.HEARTBEAT_ACK:
                # Client acknowledges a received heartbeat
                if not self._ack.done():
                    self._ack.set_result(None)

            return

        # It's a dispatch message (event)
        event = data.get("t")
        payload = data.get("p", [])
        if isinstance(payload, dict):
            self.server._dispatch_received(event, self, **payload)

        elif isinstance(payload, list):
            self.server._dispatch_received(event, self, *payload)

        else:
            self.server._dispatch_received(event, self)

    async def poll(self):
        """
        Poll one message and call message_receivedx
        """
        msg = await self.recv()
        await self.message_received(msg)

    async def start_polling(self):
        """
        Poll messages "forever"
        """
        while True:
            await self.poll()

    async def start_heartbeat(self):
        """
        Send a heartbeat every self.hb_interval seconds and wait for heartbeat_ack
        Otherwise close the connection
        """
        await asyncio.sleep(self.hb_interval)
        while True:
            sent = time.perf_counter()
            try:
                await self.heartbeat()
            except asyncio.TimeoutError:
                await self.close()
                return

            except websockets.ConnectionClosed:
                return

            self.latency = latency = time.perf_counter() - sent
            await asyncio.sleep(self.hb_interval - latency)