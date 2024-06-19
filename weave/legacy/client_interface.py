import typing


class ClientInterface(typing.Protocol):
    def execute(self, nodes, no_cache=False) -> list[typing.Any]:
        pass
