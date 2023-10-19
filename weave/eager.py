import typing

from . import context_state
from . import weave_internal
from . import graph
from . import weave_types as types


WeaveIterObjectType = typing.TypeVar("WeaveIterObjectType")


class WeaveIter(typing.Generic[WeaveIterObjectType]):
    def __init__(
        self, node: graph.Node, cls: typing.Optional[type[WeaveIterObjectType]] = None
    ) -> None:
        self.cls = cls
        self.node = node.map(lambda row: select_all(row))

    def __len__(self) -> int:
        with context_state.lazy_execution():
            return weave_internal.use(self.node.count())

    def __getitem__(self, index) -> typing.Optional[WeaveIterObjectType]:
        with context_state.lazy_execution():
            result = weave_internal.use(self.node[index])
            if self.cls:
                return self.cls(result)
            return result

    def __iter__(self) -> typing.Iterator[WeaveIterObjectType]:
        page_size = 10
        page_num = 0
        with context_state.lazy_execution():
            count = weave_internal.use(self.node.count())
            while True:
                page = weave_internal.use(
                    self.node.offset(page_num * page_size).limit(page_size)
                )
                if not page:
                    break
                for page_offset in range(page_size):
                    row = page[page_offset]
                    if row == None:
                        break
                    if self.cls:
                        yield self.cls(row)
                    else:
                        yield row
                page_num += 1


def select_all(node: graph.Node):
    if not types.TypedDict().assign_type(node.type):
        raise ValueError("only TypedDict supported for now")
    from .ops_primitives import dict_

    return dict_(**{k: node[k] for k in node.type.property_types})
