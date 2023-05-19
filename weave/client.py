from . import storage
from . import weave_types


class Client:
    def __init__(self, server):
        self.server = server

    def execute(self, nodes, no_cache=False):
        results = self.server.execute(nodes, no_cache=no_cache)

        # Deref if node output type is not RefType
        # TODO: move to language_ref.py, do in compile pass
        # TODO: this logic is duplicated in server.py:_handle_request
        return [
            r if isinstance(n.type, weave_types.RefType) else storage.deref(r)
            for (n, r) in zip(nodes, results)
        ]


class NonCachingClient:
    def __init__(self, server):
        self.server = server

    def execute(self, nodes):
        res = self.server.execute(nodes, no_cache=True)
        return [
            r if isinstance(n.type, weave_types.RefType) else storage.deref(r)
            for (n, r) in zip(nodes, res)
        ]
