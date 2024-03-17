from typing import Union, Any
import weave

from weave.flow.obj import Object


class Dataset(Object):
    rows: Union[weave.Table, list[Any]]

    def model_post_init(self, __context) -> None:
        if not isinstance(self.rows, weave.Table):
            self.__dict__["rows"] = weave.Table(self.rows)
