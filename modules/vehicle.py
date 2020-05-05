from module import Module
import asyncio
from enum import IntEnum
import RPi.GPIO as GPIO


GPIO.setmode(GPIO.BOARD)


class Pins(IntEnum):
    OCC = 29
    EN = 31
    ENB = 33
    PWM2 = 35
    PWM1 = 37


class VehicleModule(Module):
    NAME = "vehicle"

    async def _post_load(self):
        self.set_speed = 0
        self._speed = 0

        self.loop.create_task(self.speed_adjuster())
        self.server.dispatch(self.NAME, self.get_payload())

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

    async def _post_unload(self):
        pass

    async def _apply_speed(self):
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

    async def speed_adjuster(self):
        while self.loaded:
            print(self._speed)
            await asyncio.sleep(.05)
            if self.set_speed > self._speed:
                self._speed += 1

            elif self.set_speed < self._speed:
                self._speed -= 1

            else:
                continue

            await self._apply_speed()

    async def is_active(self):
        # Motors should be always connected
        return True

    def get_payload(self):
        return {"speed": self.set_speed}

    async def on_client_connect(self, client):
        await client.dispatch(self.NAME, self.get_payload())

    async def on_vehicle_speed(self, ws, speed):
        print("set", speed)
        self.set_speed = max(min(int(speed), 100), -100)
        self.server.dispatch(self.NAME, self.get_payload())
