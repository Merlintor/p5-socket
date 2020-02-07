import inspect
import asyncio


class Listener:
    def __init__(self, callback, onetime=False):
        self.callback = callback
        self.onetime = onetime

    def run(self, payload, loop=None):
        res = self.callback(payload)
        if inspect.isawaitable(res):
            loop = loop or asyncio.get_event_loop()
            return loop.create_task(res)

        return res
