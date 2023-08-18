import weave
from weave import ops_arrow


def test_cond_basic():
    assert weave.use(weave.ops.cond({"a": True}, [5])) == 5
    assert weave.use(weave.ops.cond({"a": False}, [5])) == None
    assert weave.use(weave.ops.cond({"a": False, "b": True}, [5, 6])) == 6


def test_cond_vector():
    conds = weave.save(
        ops_arrow.to_arrow(
            [{"a": True, "b": False}, {"a": False, "b": False}, {"a": False, "b": True}]
        ),
        "conds",
    )
    assert weave.use(conds.cond([5, 6])).to_pylist_raw() == [5, None, 6]
