import pytest

import weave
from weave.legacy.weave import ops_arrow

LIST_CONSTRUCTORS = [
    lambda x: x,
    lambda x: ops_arrow.to_arrow(x),
]


@pytest.mark.parametrize("self_constructor", LIST_CONSTRUCTORS)
def test_index_simple(self_constructor):
    items = weave.save(self_constructor(["a", "b", "c"]))
    assert weave.use(items[0]) == "a"


@pytest.mark.parametrize("self_constructor", LIST_CONSTRUCTORS)
def test_index_negative(self_constructor):
    items = weave.save(self_constructor(["a", "b", "c"]))
    assert weave.use(items[-1]) == "c"


@pytest.mark.parametrize("self_constructor", LIST_CONSTRUCTORS)
def test_index_list(self_constructor):
    items = weave.save(self_constructor(["a", "b", "c"]))
    res = weave.use(items[[0, 2]])
    if isinstance(res, ops_arrow.ArrowWeaveList):
        res = res.to_pylist_notags()
    assert res == ["a", "c"]


@pytest.mark.parametrize("self_constructor", LIST_CONSTRUCTORS)
def test_index_arrowlist(self_constructor):
    items = weave.save(self_constructor(["a", "b", "c"]))
    res = weave.use(items[ops_arrow.to_arrow([0, 2])])
    if isinstance(res, ops_arrow.ArrowWeaveList):
        res = res.to_pylist_notags()
    assert res == ["a", "c"]


def test_index_listawl_oob():
    val = ops_arrow.to_arrow([[0, 1], [2, 3]])
    val.object_type = ops_arrow.ArrowWeaveListType(val.object_type.object_type)
    items = weave.save(val)
    res = weave.use(items[2])
    if isinstance(res, ops_arrow.ArrowWeaveList):
        res = res.to_pylist_notags()
    assert res == None
