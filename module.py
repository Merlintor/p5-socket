from listener import Listener


class Module:
    EVENTS = ()

    def __init__(self, controller):
        self.controller = controller
        self.loop = controller.loop
        self.loaded = False

    @staticmethod
    def listener(callback):
        return Listener(callback)

    @property
    def listeners(self):
        for name in dir(self):
            attr = getattr(self, name)
            if name.startswith("on_"):
                yield name.replace("on_", ""), Listener(attr)

    async def is_active(self):
        """
        Checks with the state if the module should be loaded
        """
        return True

    async def load(self):
        for event in self.EVENTS:
            self.controller.register_event(event)

        for event, listener in self.listeners:
            self.controller.add_listener(event, listener)

        self.loaded = True
        await self._post_load()

    async def _post_load(self):
        pass

    async def unload(self):
        for event in self.EVENTS:
            self.controller.unregister_event(event)

        for event, listener in self.listeners:
            self.controller.remove_listener(event, listener)

        self.loaded = False
        await self._post_unload()

    async def _post_unload(self):
        pass
