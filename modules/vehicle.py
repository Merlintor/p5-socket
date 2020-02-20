from module import Module
from listener import Listener


class VehicleModule(Module):
    NAME = "vehicle"

    async def is_active(self):
        # Check if motors are connected
        # Not implementable without knowing about the specifications of the motors
        return await self.loop.run_in_executor(None, lambda: True)

    async def on_move(self, data):
        # Control motors
        print("now move", data)
