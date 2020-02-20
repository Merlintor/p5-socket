import inspect
import asyncio


class Listener:
    def __init__(self, callback, onetime=False):
        self.callback = callback
        self.onetime = onetime

    def run(self, *args, loop=None, **kwargs):
        res = self.callback(*args, **kwargs)
        if inspect.isawaitable(res):
            loop = loop or asyncio.get_event_loop()
            return loop.create_task(res)

        return res
