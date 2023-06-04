import typing


class CodifiableValueMixin:
    def to_code(self, to_code_fn: typing.Callable[[typing.Any], str]) -> str:
        raise NotImplementedError()
