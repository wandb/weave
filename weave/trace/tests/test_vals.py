import pytest

from weave.trace.vals import TraceObject


def test_traceobject_properties():
    class A:
        @property
        def x(self):
            return 1

    to = TraceObject(A(), None, None, None)
    assert to.x == 1
