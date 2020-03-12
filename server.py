import asyncio
import websockets
import traceback

from modules import to_load
from protocol import WebSocketConnection, Opcodes


class WebSocketServer:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.connections = []
        self.listeners = {}

        self.modules = [m(self) for m in to_load]

    async def handle_connection(self, ws, path):
        """
        Called for each incoming connection request
        Connection gets closed automatically when this returns
        """
        self.connections.append(ws)
        ws.server = self
        try:
            await ws.send_op(Opcodes.HELLO, d={
                "modules": [m.NAME for m in self.loaded_modules]
                # Current State etc.
            })
            self.loop.create_task(ws.start_heartbeat())
            self._dispatch_received("client_connect", ws)
            await ws.start_polling()
        except websockets.ConnectionClosed:
            pass
        finally:
            self.connections.remove(ws)
            self._dispatch_received("client_disconnect", ws)

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
            self.loop.create_task(ws.dispatch(event, payload))

    def _dispatch_received(self, event, *args, **kwargs):
        """
        Called by the individual websocket connections for received dispatch messages
        """
        listeners = self.listeners.get(event, [])
        to_remove = []
        for i, listener in enumerate(listeners):
            if listener.onetime:
                to_remove.append(i)

            try:
                listener.run(*args, **kwargs, loop=self.loop)
            except:
                traceback.print_exc()

        # Remove onetime listerners starting from the highest index
        for i in sorted(to_remove, reverse=True):
            to_remove.pop(i)

    @property
    def loaded_modules(self):
        for module in self.modules:
            if module.loaded:
                yield module

    async def update_modules(self):
        update = False
        for module in self.modules:
            if await module.is_active():
                if not module.loaded:
                    update = True
                    await module.load()

            elif module.loaded:
                update = True
                await module.unload()

        if update:
            for ws in self.connections:
                await ws.send_op(Opcodes.MODULES_UPDATE, d={
                    "modules": [m.NAME for m in self.loaded_modules]
                    # Current State etc.
                })

    async def _update_loop(self):
        while True:
            await asyncio.sleep(5)
            await self.update_modules()

    async def start(self, *args, **kwargs):
        """
        Start serving
        Non blocking
        """
        self.loop.create_task(self._update_loop())
        return await websockets.serve(self.handle_connection, klass=WebSocketConnection, *args, **kwargs)

    def run(self, *args, **kwargs):
        self.loop.create_task(self.start(*args, **kwargs))
        self.loop.run_forever()
