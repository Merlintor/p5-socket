from module import Module, listener, http_route
from aiohttp import web
import random


class MJPEGResponse(web.StreamResponse):
    async def write_jpeg(self, jpeg):
        pass


class CameraModule(Module):
    NAME = "cam"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def http_stream(self, request):
        stream = MJPEGResponse()
        await stream.prepare(request)
        while self.loaded:
            await stream.write_jpeg(None)

        await stream.write_eof()
        return stream

    @listener("connect")
    async def on_connect(self, ws):
        await ws.send_event("hello", "hello")

    @listener("test")
    async def on_test(self, ws, payload):
        print(ws, payload)

    @http_route()
    async def handle_stream(self, request):
        return web.Response(text="This is a stream!")
