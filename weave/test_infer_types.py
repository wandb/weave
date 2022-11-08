import typing
from . import infer_types
from . import graph
from . import weave_types


def test_node_with_generic():
    T = typing.TypeVar("T")
    t = graph.Node[T]
    assert infer_types.python_type_to_type(t) == weave_types.Function(
        {}, weave_types.Any()
    )
