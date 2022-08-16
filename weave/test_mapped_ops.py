import pytest
from PIL import Image

from . import api as weave
from . import ops
from . import weave_internal
from . import geom
from . import storage


def test_mapped_add():
    mapped_add = weave_internal.make_mapped_op("number-add")
    assert weave.use(mapped_add([3, 4, 5], 9)) == [12, 13, 14]


def test_mapped_method_on_custom_type():
    segment = geom.LineSegment(0.0, 0.1, 0.9, 1.1)

    len = weave.use(segment.length())
    assert len == 1.81

    mid = weave.use(segment.midpoint())
    assert mid.x == 0.45
    assert mid.y == 0.6

    segments = storage.to_arrow(
        [
            geom.LineSegment(0.0, 0.1, 0.9, 1.1),
            geom.LineSegment(0.0, 0.2, 0.4, 1.1),
        ]
    )
    lens = weave.use(segments.map(lambda seg: seg.length()))
    assert weave.use(lens[0]) == 1.81
    assert weave.use(lens[1]) == pytest.approx(0.97)

    # mid = weave.use(segments.midpoint())
    # mid = weave.use(segments.map(lambda seg: seg.midpoint()))
    # assert mid[0].x == 0.45
    # assert mid[0].y == 0.6
    # assert mid[1].x == 0.2
    # assert mid[1].y == pytest.approx(0.65)


def test_mapped_method_returning_custom_type():
    segments = storage.to_arrow(
        [
            geom.LineSegment(0.0, 0.1, 0.9, 1.1),
            geom.LineSegment(0.0, 0.2, 0.4, 1.1),
        ]
    )
    mid = weave.use(segments.map(lambda seg: seg.midpoint()))

    assert weave.use(mid[0].x) == 0.45
    assert weave.use(mid[0].y) == 0.6
    assert weave.use(mid[1].x) == 0.2
    assert weave.use(mid[1].y) == pytest.approx(0.65)


def test_mapped_on_fully_custom_type():
    data = [
        {"a": 5, "im": Image.linear_gradient("L").rotate(0)},
        {"a": 6, "im": Image.linear_gradient("L").rotate(4)},
    ]
    arrow_arr = storage.to_arrow(data)

    assert weave.use(arrow_arr.map(lambda row: row["im"].width())).to_pylist() == [
        256,
        256,
    ]


def test_mapped_pick():
    data = [
        {"a": 5, "b": 9},
        {"a": 6, "b": 10},
    ]
    arrow_arr = storage.to_arrow(data)

    assert weave.use(arrow_arr.pick("b")).to_pylist() == [9, 10]
