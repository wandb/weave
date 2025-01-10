import datetime

from weave_query import box


def test_boxdatetime():
    dt = datetime.datetime.now()
    boxed = box.box(dt)
    assert box.unbox(boxed) == dt
