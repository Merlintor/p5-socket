import asyncio
from server import WebSocketServer

from modules import to_load


class Controller:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.server = WebSocketServer(loop=self.loop)

        self.modules = [m(self) for m in to_load]

    async def update(self):
        for module in self.modules:
            if await module.is_active():
                if not module.loaded:
                    await module.load()

            elif module.loaded:
                await module.unload()

    async def _update_loop(self):
        while True:
            await asyncio.sleep(5)
            await self.update()

    def add_listener(self, *args, **kwargs):
        return self.server.add_listener(*args, **kwargs)

    def remove_listener(self, *args, **kwargs):
        return self.server.remove_listener(*args, **kwargs)

    def register_event(self, *args, **kwargs):
        return self.server.register_event(*args, **kwargs)

    def unregister_event(self, *args, **kwargs):
        return self.server.unregister_event(*args, **kwargs)

    async def start(self, *args, **kwargs):
        await self.update()
        self.loop.create_task(self._update_loop())

        host, port = kwargs.pop("host", "localhost"), kwargs.pop("port", 8080)
        await self.server.serve(host, port)

    def run(self, *args, **kwargs):
        self.loop.create_task(self.start(*args, **kwargs))
        self.loop.run_forever()
