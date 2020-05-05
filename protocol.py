from aiohttp import web
import aiohttp
import json
import asyncio
import time


class Opcodes:
    DISPATCH = 0  # Dispatch Event
    STATE_UPDATE = 1  # Send to the client immediately after the connection was established
    HEARTBEAT = 10  # Client or Server requests a heartbeat_ack from the other party
    HEARTBEAT_ACK = 11  # Client or Server acknowledges a heartbeat by the other party


class WebSocketConnection(web.WebSocketResponse):
    def __init__(self, server, *args, **kwargs):
        self.server = server
        super().__init__(
            protocols=("columbus",),
            *args,
            **kwargs
        )

        self.latency = -1
        self._hb_interval = 10
        self._hb_ack = self.loop.create_future()

    @property
    def loop(self):
        return self.server.loop

    def send_op(self, op, data=None):
        return self.send_json({
            "op": op,
            "d": data or {}
        })

    def send_event(self, event, payload):
        return self.send_op(Opcodes.DISPATCH, {
            "t": event.lower(),
            "p": payload
        })

    async def heartbeat(self):
        """
        Send a heartbeat and wait for the heartbeat_ack
        """
        self._hb_ack = self.loop.create_future()
        await self.send_op(Opcodes.HEARTBEAT)
        await asyncio.wait_for(self._hb_ack, timeout=self._hb_interval)

    async def start_heartbeat(self):
        """
        Send a heartbeat every self.hb_interval seconds and wait for heartbeat_ack
        Otherwise close the connection
        """
        await asyncio.sleep(self._hb_interval)
        while not self.closed:
            sent = time.perf_counter()
            try:
                await self.heartbeat()

            except asyncio.TimeoutError:
                await self.close(code=aiohttp.WSCloseCode.PROTOCOL_ERROR)
                return

            except RuntimeError:
                # Connection was probably closed somewhere else
                await self.close(code=aiohttp.WSCloseCode.OK)
                return

            self.latency = latency = time.perf_counter() - sent
            await asyncio.sleep(self._hb_interval - latency)

    def heartbeat_ack(self):
        """
        Acknowledge a received heartbeat
        """
        return self.send_op(Opcodes.HEARTBEAT_ACK)

    async def poll(self):
        """
        Poll one message and call message_received
        """
        try:
            msg = await self.receive_json()

        except (TypeError, json.JSONDecodeError):
            await self.close(code=aiohttp.WSCloseCode.UNSUPPORTED_DATA)
            return

        await self._msg_received(msg)

    async def start_polling(self):
        """
        Poll messages until the connection is closed
        """
        while not self.closed:
            try:
                await self.poll()

            except RuntimeError:
                # Connection was probably closed somewhere else
                await self.close(code=aiohttp.WSCloseCode.OK)
                return

    async def _msg_received(self, msg):
        op = msg.get("op")
        data = msg.get("d")

        if op != Opcodes.DISPATCH:
            if op == Opcodes.HEARTBEAT:
                await self.heartbeat_ack()

            elif op == Opcodes.HEARTBEAT_ACK:
                if not self._hb_ack.done():
                    self._hb_ack.set_result(None)

            return

        event = data.get("t")
        payload = data.get("p", {})
        self.server.dispatch_event(event, self, payload)
