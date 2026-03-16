"""Tests for weave.get_trace() and Call.trace()."""

import weave


def test_get_trace_simple(client):
    """A single op call produces a trace with one node."""

    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    result = add(1, 2)
    assert result == 3

    calls = list(client.get_calls())
    assert len(calls) == 1
    trace_id = calls[0].trace_id

    trace = client.get_trace(trace_id)
    assert trace.trace_id == trace_id
    assert trace.call_count == 1
    assert trace.root.func_name == "add"
    assert trace.depth == 0


def test_get_trace_nested(client):
    """Nested ops produce a tree with correct parent-child relationships."""

    @weave.op
    def leaf(x: int) -> int:
        return x * 2

    @weave.op
    def middle(x: int) -> int:
        return leaf(x) + 1

    @weave.op
    def root(x: int) -> int:
        return middle(x) + middle(x + 1)

    result = root(3)
    assert result == (7 + 9)

    calls = list(client.get_calls())
    # root -> middle -> leaf, middle -> leaf = 5 calls
    assert len(calls) == 5

    root_call = [c for c in calls if c.parent_id is None][0]
    trace = client.get_trace(root_call.trace_id)

    assert trace.call_count == 5
    assert trace.root.func_name == "root"
    assert trace.depth == 2

    # Root has 2 children (the two middle calls)
    middle_calls = trace.children_of(trace.root)
    assert len(middle_calls) == 2
    for mc in middle_calls:
        assert mc.func_name == "middle"
        leaf_calls = trace.children_of(mc)
        assert len(leaf_calls) == 1
        assert leaf_calls[0].func_name == "leaf"


def test_trace_walk(client):
    """walk() yields (depth, call) in DFS order."""

    @weave.op
    def child(x: int) -> int:
        return x

    @weave.op
    def parent(x: int) -> int:
        return child(x) + child(x + 1)

    parent(1)

    calls = list(client.get_calls())
    root_call = [c for c in calls if c.parent_id is None][0]
    trace = client.get_trace(root_call.trace_id)

    walk_result = list(trace.walk())
    assert len(walk_result) == 3

    # First item is root at depth 0
    assert walk_result[0][0] == 0
    assert walk_result[0][1].func_name == "parent"

    # Children at depth 1
    assert walk_result[1][0] == 1
    assert walk_result[2][0] == 1


def test_trace_find(client):
    """find() filters calls by op name substring."""

    @weave.op
    def compute(x: int) -> int:
        return x * 2

    @weave.op
    def orchestrate(x: int) -> int:
        return compute(x) + compute(x)

    orchestrate(5)

    calls = list(client.get_calls())
    root_call = [c for c in calls if c.parent_id is None][0]
    trace = client.get_trace(root_call.trace_id)

    found = trace.find("compute")
    assert len(found) == 2
    assert all(c.func_name == "compute" for c in found)

    found_orch = trace.find("orchestrate")
    assert len(found_orch) == 1


def test_trace_duration(client):
    """duration covers root start to latest call end."""

    @weave.op
    def noop() -> int:
        return 1

    @weave.op
    def wrapper() -> int:
        return noop()

    wrapper()

    calls = list(client.get_calls())
    root_call = [c for c in calls if c.parent_id is None][0]
    trace = client.get_trace(root_call.trace_id)

    duration = trace.duration
    assert duration is not None
    assert duration.total_seconds() >= 0


def test_call_trace_method(client):
    """Call.trace() returns the same trace as client.get_trace()."""

    @weave.op
    def my_op(x: int) -> int:
        return x

    my_op(1)

    calls = list(client.get_calls())
    call = calls[0]

    trace_from_call = call.trace()
    trace_from_client = client.get_trace(call.trace_id)

    assert trace_from_call.trace_id == trace_from_client.trace_id
    assert trace_from_call.call_count == trace_from_client.call_count


def test_get_trace_top_level(client):
    """weave.get_trace() works as a top-level function."""

    @weave.op
    def my_op(x: int) -> int:
        return x

    my_op(42)

    calls = list(client.get_calls())
    trace = weave.get_trace(calls[0].trace_id)
    assert trace.call_count == 1
