import dataclasses
import random

from . import api as weave
from . import weave_types as types
from . import storage
from . import arrow_util

import typing


def test_function_op_name():
    @weave.op()
    def my_op(a: int, b: int) -> int:
        return a + b

    assert my_op.name == "op-my_op"


def test_method_op_name():
    class MyObjType(types.Type):
        name = "test-decorators-my-obj"

    @weave.weave_class(weave_type=MyObjType)
    class MyObj:
        @weave.op()
        def my_op(self: int, b: int) -> int:  # type: ignore
            return self + b

    assert MyObj.my_op.name == "test-decorators-my-obj-my_op"


@weave.obj()
class Point:
    x: float
    y: float


@weave.obj()
class LineSegment:
    start: Point
    end: Point

    def mid(self):
        return Point(
            self.start.x + (self.end.x - self.start.x) / 2,
            self.start.y + (self.end.y - self.start.y) / 2,
        )


def test_weave_obj():
    box = Point(1, 2)
    box_type = weave.type_of(box)
    assert box_type == Point.WeaveType()
    ref = storage.save(box)
    box2 = ref.get()
    assert box == box2


def test_nested_weave_obj():
    line = LineSegment(Point(1, 2), Point(3, 4))
    line_type = weave.type_of(line)
    assert line_type == LineSegment.WeaveType()
    ref = storage.save(line)
    line2 = ref.get()
    assert line == line2


def make_lines() -> list[LineSegment]:
    lines = []
    for i in range(2):
        line = LineSegment(
            Point(float(i), float(i + 2)),
            Point(float(i * 2), float(i * 2 + 1)),
        )
        lines.append(line)
    return lines


def test_list_nested_weave_obj():
    lines = make_lines()
    lines_type = weave.type_of(lines)
    assert lines_type == types.List(LineSegment.WeaveType())
    ref = storage.save(lines)
    lines2 = ref.get()
    assert lines2 == lines


def test_list_nested_weave_obj_map_attr():
    lines = make_lines()
    ref = storage.save(lines)
    lines = ref.get()
    assert lines.map(lambda line: line.start.x) == [0.0, 1.0]


def test_list_nested_weave_obj_map_method():
    lines = make_lines()
    ref = storage.save(lines)
    lines: arrow_util.ArrowTableList[LineSegment] = ref.get()
    mapped = lines.map(lambda line: line.mid())
    assert mapped == [Point(0.0, 1.5), Point(1.5, 3.0)]
