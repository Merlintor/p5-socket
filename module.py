from listener import Listener


class Module:
    NAME = ""

    def __init__(self, server):
        self.server = server
        self.loop = server.loop
        self.loaded = False

        self.listeners = [
            (name[3:], Listener(getattr(self, name)))
            for name in dir(self)
            if name.startswith("on_")
        ]

    @staticmethod
    def listener(callback):
        return Listener(callback)

    async def is_active(self):
        """
        Checks with the state if the module should be loaded
        """
        return True

    async def load(self):
        for event, listener in self.listeners:
            self.server.add_listener(event, listener)

        self.loaded = True
        await self._post_load()

    async def _post_load(self):
        pass

    async def unload(self):
        for event, listener in self.listeners:
            self.server.remove_listener(event, listener)

        self.loaded = False
        await self._post_unload()

    async def _post_unload(self):
        pass
