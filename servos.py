import RPi.GPIO as GPIO
import time


MAX_ANGLE = 140


def set_rotation(pin, rotation):
    min_width = 0.000750
    max_width = 0.002250

    pulse_width = ((rotation / MAX_ANGLE) * (max_width - min_width)) + min_width
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(pulse_width)
    GPIO.output(pin, GPIO.LOW)