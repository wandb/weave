from . import api as weave
from PIL import Image


@weave.type()
class Point2D:
    x: float
    y: float

    @weave.op()
    def get_x(self) -> float:
        return self.x


@weave.type()
class Size2D:
    w: float
    h: float


@weave.type()
class BoundingBox2D:
    top_left: Point2D
    size: Size2D

    @weave.op()
    def center(self) -> Point2D:
        return Point2D(
            self.top_left.x + self.size.w / 2, self.top_left.y + self.size.h / 2
        )


@weave.type()
class ImageWithBoxes:
    im: Image.Image
    boxes: list[BoundingBox2D]

    @weave.op()
    def get_boxes(self) -> list[BoundingBox2D]:
        return self.boxes
