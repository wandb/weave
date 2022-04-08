import typing
import math

from . import api as weave
from . import weave_objects
from . import context


def test_compute_points():
    class XOnly(typing.TypedDict):
        x: float

    class Point(typing.TypedDict):
        x: float
        y: float

    @weave.op()
    def compute_points(xs: list[XOnly], freq: float) -> list[Point]:
        res: list[Point] = []
        for row in xs:
            res.append({"x": row["x"], "y": math.sin(freq * row["x"])})
        return res

    xs = weave_objects.List([{"x": float(i)} for i in range(2)])
    points = compute_points(xs, 1)
    with context.local_http_client():
        assert weave.use(points) == [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.8414709848078965},
        ]
