import typing

from .. import weave_types as types
from .. import graph


def currently_weavifying(input_types: typing.Any) -> bool:
    return isinstance(input_types, graph.Node) and types.TypedDict({}).assign_type(
        input_types.type
    )
