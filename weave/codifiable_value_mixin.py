import typing


class CodifiableValueMixin:
    def to_code(self) -> typing.Optional[str]:
        raise NotImplementedError()
