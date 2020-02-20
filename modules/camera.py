from module import Module
from aiohttp import web


class CameraModule(Module):
    NAME = "cam"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._app = web.Application()
        self._runner = web.AppRunner(self._app)
        self._port = kwargs.pop("port", 0)

    async def is_active(self):
        return True

    async def _post_load(self):
        await self._runner.setup()
        site = web.TCPSite(self._runner, '0.0.0.0', self._port)
        await site.start()
        self._port = site._server.sockets[0].getsockname()[1]
        self.controller.dispatch("cam_available", {"port": self._port})

    async def _post_unload(self):
        await self._runner.cleanup()

    async def on_client_connect(self, client):
        await client.dispatch("cam_available", {"port": self._port})

    async def on_cam_request(self, client):
        await client.dispatch("cam_available", {"port": self._port})

    async def on_cam_move(self):
        pass
