from module import Module, listener, http_route
from aiohttp import web, MultipartWriter
import asyncio
import time
from uuid import uuid4
import cv2


USB_ID = 0


class CameraModule(Module):
    NAME = "cam"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture = cv2.VideoCapture(USB_ID)
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
            new_xrot = int(payload["xrot"])
            new_yrot = int(payload["yrot"])

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
            time_before = time.perf_counter()

            # Run in thread pool to not block the main thread
            rc, frame = await self.loop.run_in_executor(None, self.capture.read)
            if not rc:
                continue

            result, data = cv2.imencode(".jpg", frame, (int(cv2.IMWRITE_JPEG_QUALITY), 50))

            with MultipartWriter('image/jpeg', boundary=boundary) as mpwriter:
                mpwriter.append(data.tostring(), {'Content-Type': 'image/jpeg'})
                await mpwriter.write(response, close_boundary=False)

            await response.drain()

            # Wait a bit to reach the goal fps (too many frames can cause performance issues on both sides)
            time_dif = time.perf_counter() - time_before
            await asyncio.sleep((1 / self._goal_fps) - time_dif)

        return response
