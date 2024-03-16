import typing
import weave

from weave.flow.obj import Object


class Dataset(Object):
    rows: list[typing.Any]

    def __post_init__(self) -> None:
        if not isinstance(self.rows, weave.WeaveList):
            self.__dict__["rows"] = weave.WeaveList(self.rows)
