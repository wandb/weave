import pytest

from weave.trace.refs import ObjectRef
from weave.trace_server.refs_internal import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
)


def test_dict_refs(client):
    d = client.save({"a": 1, "b": 2}, name="d")

    assert d["a"] == 1
    assert isinstance(d["a"].ref, ObjectRef)
    assert d["a"].ref.is_descended_from(d.ref)
    assert d["a"].ref.extra == (DICT_KEY_EDGE_NAME, "a")

    assert d["b"] == 2
    assert isinstance(d["b"].ref, ObjectRef)
    assert d["b"].ref.is_descended_from(d.ref)
    assert d["b"].ref.extra == (DICT_KEY_EDGE_NAME, "b")


def test_dict_iter(client):
    d_orig = client.save({"a": 1, "b": 2, "c": 3}, name="d")
    d = dict(d_orig)
    with pytest.raises(AttributeError):
        d.ref

    assert d["a"] == 1
    assert isinstance(d["a"].ref, ObjectRef)
    assert d["a"].ref.is_descended_from(d_orig.ref)
    assert d["a"].ref.extra == (DICT_KEY_EDGE_NAME, "a")

    assert d["b"] == 2
    assert isinstance(d["b"].ref, ObjectRef)
    assert d["b"].ref.is_descended_from(d_orig.ref)
    assert d["b"].ref.extra == (DICT_KEY_EDGE_NAME, "b")


def test_list_refs(client):
    l = client.save([1, 2], name="l")

    assert l[0] == 1
    assert isinstance(l[0].ref, ObjectRef)
    assert l[0].ref.is_descended_from(l.ref)
    assert l[0].ref.extra == (LIST_INDEX_EDGE_NAME, "0")

    assert l[1] == 2
    assert isinstance(l[1].ref, ObjectRef)
    assert l[1].ref.is_descended_from(l.ref)
    assert l[1].ref.extra == (LIST_INDEX_EDGE_NAME, "1")


def test_list_iter(client):
    l_orig = client.save([1, 2], name="l")
    l = list(l_orig)
    with pytest.raises(AttributeError):
        l.ref

    assert l[0] == 1
    assert l[0].ref.is_descended_from(l_orig.ref)
    assert isinstance(l[0].ref, ObjectRef)

    assert l[1] == 2
    assert l[1].ref.is_descended_from(l_orig.ref)
    assert isinstance(l[1].ref, ObjectRef)
