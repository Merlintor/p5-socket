from aiohttp import web


class Listener:
    def __init__(self, event, handler):
        self.event = event
        self.handler = handler


class listener:
    def __init__(self, event):
        self.event = event

    def __call__(self, handler):
        self.handler = handler
        return self


class http_route:
    def __init__(self, method="GET", path=""):
        self.method = method
        self.path = path

    def __call__(self, handler):
        self.handler = handler
        return self


class Module:
    NAME = ""

    def __init__(self, server):
        self.server = server
        self.loaded = False

        self.listeners = []
        self.http_routes = []

        self._discover_handlers()

    @property
    def loop(self):
        return self.server.loop

    def _discover_handlers(self):
        """
        Looks for module attributes that server as a listener or http_route
        The listener and http_route decorators are used for type checking
        """
        def _function_to_method(fun):
            """
            Wraps a function as a method of this module and adds the self parameter
            """
            def _wrapper(*args, **kwargs):
                return fun(self, *args, **kwargs)

            return _wrapper

        for name in dir(self):
            value = getattr(self, name)
            if isinstance(value, listener):
                self.listeners.append(Listener(
                    event=value.event,
                    handler=_function_to_method(value.handler)
                ))

            elif isinstance(value, http_route):
                # Prefix path with module name
                if value.path:
                    path = "/" + self.NAME + "/" + value.path.strip("/")

                else:
                    path = "/" + self.NAME

                self.http_routes.append(web.route(
                    method=value.method,
                    path=path,
                    handler=_function_to_method(value.handler)
                ))

    async def setup(self):
        pass
