import asyncio
import websockets
import time
import json
import traceback
import math


class Opcodes:
    DISPATCH = 0  # Dispatch Event
    HELLO = 1  # Send to the client immediately after the connection was established
    EVENTS_UPDATE = 2  # The client updates which events it wants to receive or server updates which events are available
    HEARTBEAT = 10  # Client or Server requests a heartbeat_ack from the other party
    HEARTBEAT_ACK = 11  # Client or Server acknowledges a heartbeat by the other party


class WebSocketConnection(websockets.WebSocketServerProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server = None  # Filled by handle_connection
        self.subscriptions = []
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

            elif op == Opcodes.EVENTS_UPDATE:
                # Client updates which events it wants to receive
                if not isinstance(data, list):
                    return

                for sub in data:
                    if sub in self.server.events:
                        self.subscriptions.append(sub)

            return

        # It's a dispatch message (event)
        event = data.get("t")
        payload = data.get("p")
        self.server._dispatch_received(event, payload)

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


class WebSocketServer:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.connections = []
        self.events = set()
        self.listeners = {}

    async def handle_connection(self, ws, path):
        """
        Called for each incoming connection request
        Connection gets closed automatically when this returns
        """
        self.connections.append(ws)
        ws.server = self
        try:
            await ws.send_op(Opcodes.HELLO, d={
                "events": list(self.events)
                # Current State etc.
            })
            self.loop.create_task(ws.start_heartbeat())
            await ws.start_polling()
        except websockets.ConnectionClosed:
            pass
        finally:
            self.connections.remove(ws)

    def register_event(self, event):
        """
        Add event to the available event list and update clients if necessary
        """
        if event not in self.events:
            self.events.add(event)
            for ws in self.connections:
                self.loop.create_task(ws.events_update())

    def unregister_event(self, event):
        """
        Remove event from the available event list and update clients if necessary
        """
        if event in self.events:
            self.events.remove(event)
            for ws in self.connections:
                self.loop.create_task(ws.events_update())

    def add_listener(self, event, listener):
        """
        Add a listener for a specific event
        It can either be a static or onetime listener
        """
        if event not in self.listeners.keys():
            self.listeners[event] = [listener]

        else:
            self.listeners[event].append(listener)

    def remove_listener(self, event, listener):
        """
        Remove a previously added listener
        """
        if event not in self.listeners.keys():
            return False

        try:
            self.listeners[event].remove(listener)
            return True

        except ValueError:
            return False

    def dispatch(self, event, payload):
        """
        Dispatch an event to all websocket connections
        """
        for ws in self.connections:
            self.loop.create_task(ws.send_op(
                Opcodes.DISPATCH,
                d={
                    "t": event,
                    "p": payload
                }
            ))

    def _dispatch_received(self, event, payload):
        """
        Called by the individual websocket connections for received dispatch messages
        """
        listeners = self.listeners.get(event, [])
        to_remove = []
        for i, listener in enumerate(listeners):
            if listener.onetime:
                to_remove.append(i)

            try:
                listener.run(payload, loop=self.loop)
            except:
                traceback.print_exc()

        # Remove onetime listerners starting from the highest index
        for i in sorted(to_remove, reverse=True):
            to_remove.pop(i)

    async def serve(self, *args, **kwargs):
        """
        Start serving
        Non blocking
        """
        return await websockets.serve(self.handle_connection, klass=WebSocketConnection, *args, **kwargs)
