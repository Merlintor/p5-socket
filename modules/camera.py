from module import Module, listener, http_route
from aiohttp import web, MultipartWriter
import asyncio
import time
from enum import IntEnum
from uuid import uuid4
import cv2
import RPi.GPIO as GPIO
import traceback
import servos


GPIO.setmode(GPIO.BOARD)
USB_ID = 0


class GPIOPins(IntEnum):
    SERVO_X = 16
    SERVO_Y = 18


class CameraModule(Module):
    NAME = "cam"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture = cv2.VideoCapture(USB_ID)
        self.state = {
            "hrot": 70,
            "vrot": 0
        }

        self._goal_fps = 15
        self.loop.run_in_executor(None, self._setup_gpio)

        self._last_hrot = None
        self._last_vrot = None

    def _setup_gpio(self):
        GPIO.setup(GPIOPins.SERVO_X, GPIO.OUT)
        GPIO.setup(GPIOPins.SERVO_Y, GPIO.OUT)
        GPIO.output(GPIOPins.SERVO_X, GPIO.LOW)
        GPIO.output(GPIOPins.SERVO_Y, GPIO.LOW)

        asyncio.run_coroutine_threadsafe(self.move_cam(), self.loop)

    async def move_cam(self):
        """
        Apply h- and v-rot to the connected cam
        """
        tasks = []
        hrot = self.state["hrot"]
        if hrot != self._last_hrot:
            self._last_hrot = hrot
            tasks.append(
                self.loop.run_in_executor(None, servos.set_rotation, GPIOPins.SERVO_X, 140 - hrot)
            )

        vrot = self.state["vrot"]
        if vrot != self._last_vrot:
            self._last_vrot = vrot
            tasks.append(
                self.loop.run_in_executor(None, servos.set_rotation, GPIOPins.SERVO_Y, vrot)
            )

        if tasks:
            return await asyncio.wait(tasks)

    @listener("cam_move")
    async def on_cam_move(self, ws, payload):
        try:
            new_hrot, new_vrot = self.state["hrot"], self.state["vrot"]
            if "hrot" in payload:
                new_hrot = min(max(0, int(payload["hrot"])), 140)

            if "vrot" in payload:
                new_vrot = min(max(0, int(payload["vrot"])), 140)

            await self.state_update({"vrot": new_vrot, "hrot": new_hrot})
            await self.move_cam()

        except (KeyError, ValueError):
            # Invalid payload provided
            traceback.print_exc()
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

            result, data = cv2.imencode(".jpg", frame, (int(cv2.IMWRITE_JPEG_QUALITY), 100))

            with MultipartWriter('image/jpeg', boundary=boundary) as mpwriter:
                mpwriter.append(data.tostring(), {'Content-Type': 'image/jpeg'})
                await mpwriter.write(response, close_boundary=False)

            await response.drain()

            # Wait a bit to reach the goal fps (too many frames can cause performance issues on both sides)
            time_dif = time.perf_counter() - time_before
            await asyncio.sleep((1 / self._goal_fps) - time_dif)

        return response
