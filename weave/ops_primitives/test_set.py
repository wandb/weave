import weave

from .. import weave_internal
from .. import ops_primitives


def test_difference_type():
    diff = ops_primitives.difference(
        [weave_internal.const("a"), weave_internal.const("b")],
        [weave_internal.const("b")],
    )
    # When difference operations on Const Union types, we get a const union
    # type back with the difference applied (ie difference works at type level
    # when types are available as Consts)
    assert diff.type == weave.types.List(
        weave.types.union(weave.types.Const(weave.types.String(), "a"))
    )
