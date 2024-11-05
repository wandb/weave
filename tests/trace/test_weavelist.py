from copy import deepcopy

from weave.trace.vals import WeaveList


def test_deepcopy_weavelist(client):
    lst = WeaveList([1, 2, 3], server=client.server)
    res = deepcopy(lst)
    assert res == [1, 2, 3]
