from aiohttp import web
import aiohttp
import asyncio
import weakref

from protocol import WebSocketConnection
import modules


class Server(web.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loop = kwargs.get("loop")

        self.clients = weakref.WeakSet()

        self.on_shutdown.append(self._on_shutdown)
        self.add_routes([web.get("/ws", self._handle_websocket)])

        self._listeners = set()

    @property
    def loop(self):
        return self._loop or asyncio.get_event_loop()

    def load_module(self, module):
        md = module(self)
        for listener in md.listeners:
            self._listeners.add(listener)

        self.add_routes(md.http_routes)

    def spread_event(self, event, payload):
        """
        Sends an event to load connected clients
        """
        tasks = [
            self.loop.create_task(ws.send_event(event, payload))
            for ws in self.clients
        ]
        return asyncio.wait(tasks)

    def dispatch_event(self, event, ws, *args, **kwargs):
        """
        Propagates an event to all internal listeners
        """
        for listener in self._listeners:
            if event == listener.event:
                self.loop.create_task(listener.handler(ws, *args, **kwargs))

    async def _handle_websocket(self, request):
        """
        Handler for GET /ws
        Creates and handles a websocket connection
        """
        ws = WebSocketConnection(self)
        await ws.prepare(request)

        self.clients.add(ws)
        self.dispatch_event("connect", ws)
        try:
            self.loop.create_task(ws.start_heartbeat())
            await ws.start_polling()

        finally:
            self.dispatch_event("disconnect", ws)
            self.clients.discard(ws)

    async def _on_shutdown(self, _):
        """
        Called when the server shutdowns
        Gracefully closes all websocket connections
        """
        for ws in set(self.clients):
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY)

    def run(self, *args, **kwargs):
        web.run_app(self, *args, **kwargs)


if __name__ == "__main__":
    server = Server()
    for module in modules.to_load:
        server.load_module(module)

    server.run(host="0.0.0.0", port=420)
