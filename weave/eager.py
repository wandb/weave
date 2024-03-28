import typing

from . import context_state
from . import weave_internal
from . import graph
from . import weave_types as types


WeaveIterObjectType = typing.TypeVar("WeaveIterObjectType")


class WeaveIter(
    typing.Sequence[WeaveIterObjectType], typing.Generic[WeaveIterObjectType]
):
    def __init__(
        self, node: graph.Node, cls: typing.Optional[type[WeaveIterObjectType]] = None
    ) -> None:
        self.cls = cls
        self.node = node

    @property
    def select_node(self) -> graph.Node:
        return self.node.map(lambda row: select_all(row))  # type: ignore

    def __len__(self) -> int:
        with context_state.lazy_execution():
            count_node = self.node.count()  # type: ignore
            count = weave_internal.use(count_node)
            count = typing.cast(int, count)
            return count

    @typing.overload
    def __getitem__(self, index: int) -> WeaveIterObjectType:
        ...

    @typing.overload
    def __getitem__(self, index: slice) -> "WeaveIter[WeaveIterObjectType]":
        ...

    def __getitem__(
        self, index: typing.Union[int, slice]
    ) -> typing.Union[WeaveIterObjectType, "WeaveIter[WeaveIterObjectType]"]:
        if isinstance(index, int):
            with context_state.lazy_execution():
                indexed_node = self.select_node[index]  # type: ignore
                result = weave_internal.use(indexed_node)
                if self.cls:
                    return self.cls(result)  # type: ignore
                return result  # type: ignore
        elif isinstance(index, slice):
            start = index.start if index.start is not None else 0
            stop = index.stop if index.stop is not None else len(self)
            if index.step is not None:
                raise ValueError("step not supported")
            limited_offset_node = self.node.offset(start).limit(stop - start)  # type: ignore
            return WeaveIter(limited_offset_node, self.cls)
        else:
            raise ValueError("index must be int or slice")

    def __iter__(self) -> typing.Iterator[WeaveIterObjectType]:
        page_size = 100
        page_num = 0
        with context_state.lazy_execution():
            count_node = self.node.count()  # type: ignore
            count = weave_internal.use(count_node)
            while True:
                limited_offset_node = self.select_node.offset(page_num * page_size).limit(page_size)  # type: ignore
                page = weave_internal.use(limited_offset_node)
                if not page:
                    break
                for page_offset in range(page_size):
                    row = page[page_offset]
                    if row == None:
                        break
                    if self.cls:
                        yield self.cls(row)  # type: ignore
                    else:
                        yield row
                page_num += 1


def select_all(node: graph.Node) -> graph.Node:
    if not types.TypedDict().assign_type(node.type):
        raise ValueError("only TypedDict supported for now")
    from .ops_primitives import dict_

    node_type = typing.cast(types.TypedDict, node.type)
    return dict_(**{k: node[k] for k in node_type.property_types})  # type: ignore
