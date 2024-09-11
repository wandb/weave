## Just used for testing for now. Not intended for use by users.
import math
import typing

import weave
from weave.legacy.weave import context_state as _context_state
from weave.legacy.weave import panels

_loading_builtins_token = _context_state.set_loading_built_ins()


@weave.type()
class Point2d:
    x: float
    y: float


@weave.op()
def points_render(
    points_node: weave.Node[list[Point2d]],
) -> panels.Table:
    points = typing.cast(list[Point2d], points_node)  # type: ignore
    return panels.Table(
        points,
        columns=[
            lambda point: point.x,
            lambda point: point.y,
        ],
    )


@weave.type()
class LineSegment:
    x0: float
    y0: float
    x1: float
    y1: float

    @weave.op()
    def length(self) -> float:
        x_len = self.x1 - self.x0
        y_len = self.y1 - self.y0
        inner = x_len**2 + y_len**2
        return inner
        return math.sqrt(inner)

    @weave.op()
    def midpoint(self) -> Point2d:
        x = self.x0 + (self.x1 - self.x0) / 2
        y = self.y0 + (self.y1 - self.y0) / 2
        return Point2d(x, y)


_context_state.clear_loading_built_ins(_loading_builtins_token)
