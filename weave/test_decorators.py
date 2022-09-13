import pytest

from . import api as weave
from . import weave_types as types
from . import storage
from . import errors
from .decorators import cache_control
from . import compile
from . import forward_graph
from .execute import execute_forward

from .ops_primitives import list_


def test_function_op_name():
    @weave.op()
    def test_decorators_function_op(a: int, b: int) -> int:
        return a + b

    assert test_decorators_function_op.name == "op-test_decorators_function_op"


def test_method_op_name():
    class MyObjType(types.Type):
        name = "test-decorators-my-obj"

    @weave.weave_class(weave_type=MyObjType)
    class MyObj:
        @weave.op()
        def my_op(self: int, b: int) -> int:  # type: ignore
            return self + b

    assert MyObj.my_op.name == "test-decorators-my-obj-my_op"


@weave.type()
class Point:
    x: float
    y: float


def test_attr_access():
    p = weave.save(Point(1, 2), "my-point")
    assert weave.use(p.x) == 1
    assert weave.use(p.y) == 2


@weave.type()
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


def test_cache_control_decorator():
    target = {"t": 1, "b": [1, 2, 3, 4]}
    node_that_should_not_cache = list_.make_list(**{"0": target})
    second_node_that_should_not_cache = list_.unnest(node_that_should_not_cache)

    nodes = compile.compile([second_node_that_should_not_cache])
    fg = forward_graph.ForwardGraph(nodes)
    stats = execute_forward(fg, no_cache=False)
    summary = stats.summary()
    assert sum([v["cache_used"] for v in summary.values()]) == 0

    node_that_should_cache = list_.make_list(**{"0": target, "1": target})
    node_that_should_not_cache = list_.unnest(node_that_should_cache)

    nodes = compile.compile([node_that_should_not_cache])
    fg = forward_graph.ForwardGraph(nodes)
    stats = execute_forward(fg, no_cache=False)
    summary = stats.summary()
    assert sum([v["cache_used"] for v in summary.values()]) == 1


def test_cache_control_decorator_fails_on_sig_mismatch():
    with pytest.raises(errors.WeaveDefinitionError):

        @cache_control("number-add")
        def number_add(number1, number2):
            return True

    with pytest.raises(errors.WeaveDefinitionError):

        @cache_control("number-add")
        def number_add(lhs, rhs, superfluous_arg):
            return True
