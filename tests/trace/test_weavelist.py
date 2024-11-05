from copy import deepcopy

from weave.trace.vals import WeaveDict, WeaveList, WeaveObject


def test_deepcopy_weavelist(client):
    lst = WeaveList([1, 2, 3], server=client.server)
    res = deepcopy(lst)
    assert res == [1, 2, 3]


def test_deepcopy_weavedict(client):
    d = WeaveDict({"a": 1, "b": 2}, server=client.server)
    res = deepcopy(d)
    assert res == {"a": 1, "b": 2}


def test_deepcopy_weaveobject(client):
    o = WeaveObject({"a": 1, "b": 2}, ref=None, root=None, server=client.server)
    res = deepcopy(o)
    assert res == {"a": 1, "b": 2}


# # Not sure about the implications here yet
# def test_deepcopy_weavetable(client):
#     t = WeaveTable(
#         table_ref=None,
#         ref=None,
#         server=client.server,
#         filter=TableRowFilter(),
#         root=None,
#     )
#     res = deepcopy(t)
#     assert res == t
