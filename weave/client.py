from . import storage


class Client:
    def __init__(self, server):
        self.server = server

    def execute(self, nodes, no_cache=False):
        results = self.server.execute(nodes, no_cache=no_cache)
        return [storage.deref(r) for r in results]


class NonCachingClient:
    def __init__(self, server):
        self.server = server

    def execute(self, nodes):
        return self.server.execute(nodes, no_cache=True)
