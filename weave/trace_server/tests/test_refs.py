import pytest
from weave.trace_server.refs import ObjectRef


def test_isdescended_from():
    a = ObjectRef(entity="e", project="p", name="n", version="v", extra=["x1"])
    b = ObjectRef(entity="e", project="p", name="n", version="v", extra=["x1", "x2"])
    assert a.is_descended_from(b) == False
    assert b.is_descended_from(a) == True
