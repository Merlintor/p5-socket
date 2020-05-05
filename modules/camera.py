from module import Module, listener, http_route
from aiohttp import web, MultipartWriter
import asyncio
import time
from uuid import uuid4


class CameraModule(Module):
    NAME = "cam"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = {
            "available": True,
            "xrot": 0,
            "yrot": 0
        }

        self.goal_fps = 30

    @listener("connect")
    async def on_connect(self, ws):
        await ws.send_event("hello", "hello")

    @listener("test")
    async def on_test(self, ws, payload):
        print(ws, payload)

    @http_route()
    async def handle_stream(self, request):
        frames = (
            open("sample.jpeg", "rb").read(),
            open("sample2.jpeg", "rb").read()
        )

        boundary = str(uuid4())
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'multipart/x-mixed-replace;boundary={}'.format(boundary)
            }
        )
        await response.prepare(request)

        while True:
            for frame in frames:
                time_before = time.perf_counter()

                with MultipartWriter('image/jpeg', boundary=boundary) as mpwriter:
                    mpwriter.append(frame, {'Content-Type': 'image/jpeg'})
                    await mpwriter.write(response, close_boundary=False)

                await response.drain()

                time_dif = time.perf_counter() - time_before
                await asyncio.sleep((1 / self.goal_fps) - time_dif)
