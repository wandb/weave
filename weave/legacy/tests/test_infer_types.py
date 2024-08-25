import typing

from weave.legacy.weave import graph, infer_types, weave_types


def test_node_with_generic():
    T = typing.TypeVar("T")
    t = graph.Node[T]
    assert infer_types.python_type_to_type(t) == weave_types.Function(
        {}, weave_types.Any()
    )


def test_with_literal():
    assert infer_types.python_type_to_type(
        typing.Literal["a", "b"]
    ) == weave_types.UnionType(
        weave_types.Const(weave_types.String(), "a"),
        weave_types.Const(weave_types.String(), "b"),
    )
