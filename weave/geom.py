import math
from . import api as weave
from . import weave_types as types


class Point2dType(types.ObjectType):
    def property_types(self):
        return {
            "x": types.Float(),
            "y": types.Float(),
        }


@weave.weave_class(weave_type=Point2dType)
class Point2d:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    # Would be really nice to be able to compare this to a dict
    # so compare would do self.as_type(type_of(other)).__equal__
    # Type-casting is the really nice type behavior I want.
    # We can automatically find a type path from a to b, like we do with ConverterPanels.


class LineSegmentType(types.ObjectType):
    def property_types(self):
        return {
            "x0": types.Float(),
            "y0": types.Float(),
            "x1": types.Float(),
            "y1": types.Float(),
        }


@weave.weave_class(weave_type=LineSegmentType)
class LineSegment:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

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
