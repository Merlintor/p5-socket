from module import Module, listener
import asyncio
from enum import IntEnum
import RPi.GPIO as GPIO
import servos


GPIO.setmode(GPIO.BOARD)


class Pins(IntEnum):
    OCC = 29
    EN = 31
    ENB = 33
    PWM2 = 35
    PWM1 = 37

    SERVO = 11


class VehicleModule(Module):
    NAME = "engine"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = {
            "movement": [0, 0, 0, 0],
        }

        self._rot = 70
        self._last_rot = None
        self._speed = 0

        self._setup_gpio()
        self.loop.create_task(self.speed_adjuster())

    def _setup_gpio(self):
        # Over Current Response configuration
        GPIO.setup(Pins.OCC, GPIO.OUT)
        GPIO.output(Pins.OCC, 1)

        # Motor mode setup
        GPIO.setup(Pins.EN, GPIO.OUT)
        GPIO.output(Pins.EN, 1)
        GPIO.setup(Pins.ENB, GPIO.OUT)
        GPIO.output(Pins.ENB, 0)

        GPIO.setup(Pins.PWM1, GPIO.OUT)
        GPIO.setup(Pins.PWM2, GPIO.OUT)

        # PWM on 1khz frequency
        self.pwm1 = GPIO.PWM(Pins.PWM1, 1000)
        self.pwm2 = GPIO.PWM(Pins.PWM2, 1000)

        GPIO.setup(Pins.SERVO, GPIO.OUT)
        asyncio.run_coroutine_threadsafe(self._apply_engine(), self.loop)

    async def _apply_engine(self):
        print(self._speed)
        if self._speed > 0:
            self.pwm2.stop()
            self.pwm1.start(self._speed)
            self.pwm1.ChangeDutyCycle(self._speed)

        elif self._speed < 0:
            self.pwm1.stop()
            self.pwm2.start(-self._speed)
            self.pwm2.ChangeDutyCycle(-self._speed)

        else:
            self.pwm1.stop()
            self.pwm2.stop()
            GPIO.output(Pins.PWM1, 1)
            GPIO.output(Pins.PWM2, 1)

        if self._rot != self._last_rot:
            self._last_rot = self._rot
            self.loop.run_in_executor(None, servos.set_rotation, Pins.SERVO, self._rot)

    async def speed_adjuster(self):
        while True:
            await asyncio.sleep(0.1)
            mov = self.state["movement"]
            self._speed += mov[2]
            self._speed -= mov[0]
            self._speed = min(max(self._speed, -50), 50)

            self._rot += mov[1]
            self._rot -= mov[3]
            self._rot = min(max(self._rot, 50), 90)

            await self._apply_engine()

    @listener("engine_move")
    async def on_engine_move(self, ws, payload):
        movement = payload["movement"]
        new_movement = self.state["movement"]
        for key, value in movement.items():
            new_movement[int(key)] = value

        await self.state_update({
            "movement": new_movement
        })
