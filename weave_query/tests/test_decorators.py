from weave.legacy.weave import api as weave
from weave.legacy.weave import storage
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.decorator_op import op


def test_function_op_name():
    @op()
    def test_decorators_function_op(a: int, b: int) -> int:
        return a + b

    assert test_decorators_function_op.name == "op-test_decorators_function_op"


def test_method_op_name():
    class MyObjType(types.Type):
        name = "test_decorators_my_obj"

    @weave.weave_class(weave_type=MyObjType)
    class MyObj:
        @op()
        def my_op(self: int, b: int) -> int:  # type: ignore
            return self + b

    assert MyObj.my_op.name == "test_decorators_my_obj-my_op"


@weave.type()
class Point:
    x: float
    y: float


def test_attr_access():
    p = weave.save(Point(1, 2), "my-point")
    assert weave.use(p.x) == 1
    assert weave.use(p.y) == 2


@weave.type()
class _TestDecoratorLineSegment:
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
    line = _TestDecoratorLineSegment(Point(1, 2), Point(3, 4))
    line_type = weave.type_of(line)
    assert line_type == _TestDecoratorLineSegment.WeaveType()
    ref = storage.save(line)
    line2 = ref.get()
    assert line == line2


def make_lines() -> list[_TestDecoratorLineSegment]:
    lines = []
    for i in range(2):
        line = _TestDecoratorLineSegment(
            Point(float(i), float(i + 2)),
            Point(float(i * 2), float(i * 2 + 1)),
        )
        lines.append(line)
    return lines


def test_list_nested_weave_obj():
    lines = make_lines()
    lines_type = weave.type_of(lines)
    assert lines_type == types.List(_TestDecoratorLineSegment.WeaveType())
    ref = storage.save(lines)
    lines2 = ref.get()
    assert lines2 == lines
