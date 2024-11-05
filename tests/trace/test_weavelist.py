from copy import deepcopy

from weave.trace.vals import WeaveDict, WeaveList


def test_deepcopy_weavelist(client):
    lst = WeaveList([1, 2, 3], server=client.server)
    res = deepcopy(lst)
    assert res == [1, 2, 3]


def test_deepcopy_weavedict(client):
    d = WeaveDict({"a": 1, "b": 2}, server=client.server)
    res = deepcopy(d)
    assert res == {"a": 1, "b": 2}
