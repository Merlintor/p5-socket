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

        self._goal_fps = 30

    async def get_cam_state(self):
        """
        Get current x- and y-rot of the connected cam
        """
        pass

    async def move_cam(self):
        """
        Apply x- and y-rot to the connected cam
        """
        pass

    @listener("cam_move")
    async def on_cam_move(self, ws, payload):
        try:
            new_xrot = int(payload.get("xrot"))
            new_yrot = int(payload.get("yrot"))

            await self.state_update({
                "xrot": new_xrot,
                "yrot": new_yrot
            })
            await self.move_cam()

        except (KeyError, ValueError):
            # Invalid payload provided
            return

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

                # Wait a bit to reach 30 fps (too many frames can cause performance issues)
                time_dif = time.perf_counter() - time_before
                await asyncio.sleep((1 / self._goal_fps) - time_dif)
