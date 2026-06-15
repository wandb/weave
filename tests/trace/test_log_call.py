"""Tests for the log_call function."""

import pytest

import weave
from weave.trace.weave_client import WeaveClient


def test_log_call_basic_fields(client: WeaveClient):
    """Single log_call records op name, inputs, output, and no exception."""
    weave.log_call("test", {"a": 1}, 2)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    call = fetched_calls[0]
    assert call.op_name.startswith("weave:///shawn/test-project/op/test:")
    assert call.inputs == {"a": 1}
    assert call.output == 2
    assert call.exception is None
    # returned call should be finished, with consistent timestamps
    assert call.started_at is not None
    assert call.ended_at is not None
    assert call.ended_at >= call.started_at


@pytest.mark.parametrize(
    ("inputs", "output"),
    [
        ({}, "result"),
        ({"x": 1}, None),
        (
            {
                "simple": 42,
                "nested": {"a": 1, "b": [2, 3, 4]},
                "list": [{"x": 1}, {"y": 2}],
            },
            {"result": [1, 2, 3], "metadata": {"count": 3, "sum": 6}},
        ),
    ],
)
def test_log_call_inputs_outputs(client: WeaveClient, inputs, output):
    """Empty, None, and deeply-nested inputs/outputs round-trip unchanged."""
    weave.log_call("io_op", inputs, output)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.inputs == inputs
    assert fetched_call.output == output


def test_log_call_display_name_string_and_callable(client: WeaveClient):
    """display_name accepts a literal string or a callable evaluated at creation."""
    weave.log_call("op_a", {"x": 5}, 10, display_name="Custom Display Name")

    def make_display_name(call):
        return f"Call-{call.inputs.get('id', 'unknown')}"

    weave.log_call(
        "op_b", {"id": 123, "value": "test"}, "result", display_name=make_display_name
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 2
    by_op = {c.func_name: c for c in fetched_calls}
    assert by_op["op_a"].display_name == "Custom Display Name"
    assert by_op["op_b"].display_name == "Call-123"


def test_log_call_attributes(client: WeaveClient):
    """Custom attributes are preserved (system may add additional ones)."""
    attrs = {"version": "1.0", "env": "test", "user": "test_user"}
    weave.log_call("test_op", {"x": 5}, 10, attributes=attrs)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    for key, value in attrs.items():
        assert fetched_call.attributes[key] == value


def test_log_call_exception(client: WeaveClient):
    """An exception is captured into the call's exception string."""
    exc = ValueError("Something went wrong")
    weave.log_call("test_op", {"x": 5}, None, exception=exc)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.exception is not None
    assert "ValueError" in fetched_call.exception
    assert "Something went wrong" in fetched_call.exception


def test_log_call_multiple_distinct_calls(client: WeaveClient):
    """Multiple log_call invocations create distinct calls with distinct names."""
    ops = ["op1", "op2", "my_custom_op", "process_data", "analyze"]
    for op_name in ops:
        weave.log_call(op_name, {"input": op_name}, f"output_{op_name}")

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == len(ops)
    assert len({c.id for c in fetched_calls}) == len(ops)
    assert {c.func_name for c in fetched_calls} == set(ops)


def test_log_call_returned_matches_fetched(client: WeaveClient):
    """The returned call object matches the fetched persisted data."""
    returned_call = weave.log_call("test_op", {"input": "test"}, {"output": "result"})

    fetched_call = client.get_calls()[0]
    assert returned_call.id == fetched_call.id
    assert returned_call.inputs == fetched_call.inputs
    assert returned_call.output == fetched_call.output
    assert returned_call.op_name == fetched_call.op_name


def test_log_call_nested_parent_and_combined_params(client: WeaveClient):
    """A child references its parent; combined params all persist on the child."""
    parent_call = weave.log_call("parent", {}, "parent_result")
    child_call = weave.log_call(
        op="combined_op",
        inputs={"x": 1, "y": 2},
        output={"sum": 3},
        parent=parent_call,
        attributes={"version": "2.0", "important": True},
        display_name="Combined Test",
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 2

    parent = next(c for c in fetched_calls if c.id == parent_call.id)
    child = next(c for c in fetched_calls if c.id == child_call.id)
    assert parent.parent_id is None
    assert child.parent_id == parent.id
    assert child.inputs == {"x": 1, "y": 2}
    assert child.output == {"sum": 3}
    assert child.attributes["version"] == "2.0"
    assert child.attributes["important"] is True
    assert child.display_name == "Combined Test"


def test_log_call_use_stack_false_does_not_set_current(client: WeaveClient):
    """use_stack=False logs the call but leaves no current call in context."""
    call = weave.log_call("test_op", {"x": 1}, 2, use_stack=False)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    assert fetched_calls[0].id == call.id
    assert weave.get_current_call() is None


def test_log_call_use_stack_true_and_default_push_and_pop(client: WeaveClient):
    """use_stack=True (explicit) and the default both push then pop the inner call,
    leaving the enclosing op current and parenting the inner call under it."""

    @weave.op
    def explicit_op():
        parent = weave.require_current_call()
        inner_call = weave.log_call("inner_op", {"x": 1}, 2, use_stack=True)
        current = weave.require_current_call()
        return parent.id, current.id, inner_call.id

    @weave.op
    def default_op():
        parent = weave.require_current_call()
        inner_call = weave.log_call("inner_op", {"x": 1}, 2)
        current = weave.require_current_call()
        return parent.id, current.id, inner_call.id

    for op in (explicit_op, default_op):
        parent_id, current_id, inner_id = op()
        assert parent_id == current_id
        inner = next(c for c in client.get_calls() if c.id == inner_id)
        assert inner.parent_id == parent_id
