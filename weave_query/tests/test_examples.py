import math
import typing

from weave.legacy.weave import api as weave
from weave.legacy.weave import context, context_state


class XOnly(typing.TypedDict):
    x: float


class Point(typing.TypedDict):
    x: float
    y: float


_loading_builtins_token = context_state.set_loading_built_ins()


@weave.op()
def _test_compute_points_compute_points(xs: list[XOnly], freq: float) -> list[Point]:
    res: list[Point] = []
    for row in xs:
        res.append({"x": row["x"], "y": math.sin(freq * row["x"])})
    return res


context_state.clear_loading_built_ins(_loading_builtins_token)


def test_compute_points():
    xs = [{"x": float(i)} for i in range(2)]
    points = _test_compute_points_compute_points(xs, 1)
    with context.local_http_client():
        assert weave.use(points) == [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.8414709848078965},
        ]
