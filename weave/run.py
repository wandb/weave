import typing


class RunKey(typing.Protocol):
    @property
    def id(self) -> str:
        ...

    @property
    def trace_id(self) -> str:
        ...


class Run(typing.Protocol):
    @property
    def id(self) -> str:
        ...

    @property
    def trace_id(self) -> str:
        ...
