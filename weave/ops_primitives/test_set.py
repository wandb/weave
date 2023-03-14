import weave


def test_difference_type():
    diff = weave.ops.difference(
        [weave.const("a"), weave.const("b")], [weave.const("b")]
    )
    # When difference operations on Const Union types, we get a const union
    # type back with the difference applied (ie difference works at type level
    # when types are available as Consts)
    assert diff.type == weave.types.List(
        weave.types.union(weave.types.Const(weave.types.String(), "a"))
    )
