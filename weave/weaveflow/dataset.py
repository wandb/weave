import typing
import weave


@weave.type()
class Dataset:
    rows: list[typing.Any]

    def __post_init__(self) -> None:
        if not isinstance(self.rows, weave.WeaveList):
            self.__dict__["rows"] = weave.WeaveList(self.rows)
