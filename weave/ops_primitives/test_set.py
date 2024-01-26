import weave

from .. import val_const
from .. import ops_primitives


def test_difference_type():
    diff = ops_primitives.difference(
        [val_const.const("a"), val_const.const("b")],
        [val_const.const("b")],
    )
    # When difference operations on Const Union types, we get a const union
    # type back with the difference applied (ie difference works at type level
    # when types are available as Consts)
    assert diff.type == weave.types.List(
        weave.types.union(weave.types.Const(weave.types.String(), "a"))
    )
