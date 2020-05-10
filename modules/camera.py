from module import Module, listener, http_route
from aiohttp import web, MultipartWriter
import asyncio
import time
from enum import IntEnum
from uuid import uuid4
import cv2
import RPi.GPIO as GPIO


GPIO.setmode(GPIO.BOARD)
USB_ID = 0
MAX_ANGLE = 140


class GPIOPins(IntEnum):
    SERVO_X = 16
    SERVO_Y = 18


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
        self.loop.run_in_executor(None, self._setup_gpio)

    def _setup_gpio(self):
        GPIO.setup(GPIOPins.SERVO_X, GPIO.OUT)
        GPIO.setup(GPIOPins.SERVO_Y, GPIO.OUT)
        GPIO.output(GPIOPins.SERVO_X, GPIO.LOW)
        GPIO.output(GPIOPins.SERVO_Y, GPIO.LOW)

        self.set_rotation(GPIOPins.SERVO_X, 0)
        self.set_rotation(GPIOPins.SERVO_Y, 0)

    def set_rotation(self, pin, rotation):
        min_width = 0.000750
        max_width = 0.002250

        pulse_width = ((rotation / MAX_ANGLE) * (max_width - min_width)) + min_width
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(pulse_width)
        GPIO.output(pin, GPIO.LOW)

    async def move_cam(self):
        """
        Apply x- and y-rot to the connected cam
        """
        xrot = self.state["xrot"] + 30
        yrot = self.state["yrot"] + 70
        tasks = (
            self.loop.run_in_executor(None, self.set_rotation, GPIOPins.SERVO_X, xrot),
            self.loop.run_in_executor(None, self.set_rotation, GPIOPins.SERVO_Y, yrot),
        )
        return await asyncio.wait(tasks)

    @listener("cam_move")
    async def on_cam_move(self, ws, payload):
        try:
            # Clip angle to 0 - 140
            new_xrot = min(max(-30, int(payload["xrot"])), 110)
            new_yrot = min(max(-70, int(payload["yrot"])), 70)

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

            result, data = cv2.imencode(".jpg", frame, (int(cv2.IMWRITE_JPEG_QUALITY), 100))

            with MultipartWriter('image/jpeg', boundary=boundary) as mpwriter:
                mpwriter.append(data.tostring(), {'Content-Type': 'image/jpeg'})
                await mpwriter.write(response, close_boundary=False)

            await response.drain()

            # Wait a bit to reach the goal fps (too many frames can cause performance issues on both sides)
            time_dif = time.perf_counter() - time_before
            await asyncio.sleep((1 / self._goal_fps) - time_dif)

        return response
