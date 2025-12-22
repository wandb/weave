"""Tests for the log_call function."""

import weave
from weave.trace.weave_client import WeaveClient


def test_log_call_basic(client: WeaveClient):
    """Test basic log_call functionality."""
    call = weave.log_call("test", {"a": 1}, 2)
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    call = fetched_calls[0]
    assert call.op_name.startswith("weave:///shawn/test-project/op/test:")
    assert call.inputs == {"a": 1}
    assert call.output == 2
    assert call.exception is None


def test_log_call_with_display_name(client: WeaveClient):
    """Test log_call with a custom display name."""
    call = weave.log_call("test_op", {"x": 5}, 10, display_name="Custom Display Name")
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.display_name == "Custom Display Name"


def test_log_call_with_attributes(client: WeaveClient):
    """Test log_call with custom attributes."""
    attrs = {"version": "1.0", "env": "test", "user": "test_user"}
    call = weave.log_call("test_op", {"x": 5}, 10, attributes=attrs)
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    # Check that our custom attributes are present (system may add additional attributes)
    for key, value in attrs.items():
        assert fetched_call.attributes[key] == value


def test_log_call_with_exception(client: WeaveClient):
    """Test log_call with an exception."""
    exc = ValueError("Something went wrong")
    call = weave.log_call("test_op", {"x": 5}, None, exception=exc)
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.exception is not None
    assert "ValueError" in fetched_call.exception
    assert "Something went wrong" in fetched_call.exception


def test_log_call_nested_with_parent(client: WeaveClient):
    """Test log_call with parent-child relationship."""
    parent_call = weave.log_call("parent_op", {"parent_input": 1}, {"parent_output": 2})
    child_call = weave.log_call(
        "child_op", {"child_input": 3}, {"child_output": 4}, parent=parent_call
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 2

    # Find parent and child in fetched calls
    parent = next(c for c in fetched_calls if c.id == parent_call.id)
    child = next(c for c in fetched_calls if c.id == child_call.id)

    # Verify parent-child relationship
    assert child.parent_id == parent.id
    assert parent.parent_id is None


def test_log_call_multiple_calls(client: WeaveClient):
    """Test multiple log_call invocations."""
    call1 = weave.log_call("op1", {"a": 1}, 2)
    call2 = weave.log_call("op2", {"b": 3}, 4)
    call3 = weave.log_call("op3", {"c": 5}, 6)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 3

    # Verify all calls are distinct
    ids = {c.id for c in fetched_calls}
    assert len(ids) == 3


def test_log_call_with_complex_inputs_outputs(client: WeaveClient):
    """Test log_call with complex nested data structures."""
    inputs = {
        "simple": 42,
        "nested": {"a": 1, "b": [2, 3, 4]},
        "list": [{"x": 1}, {"y": 2}],
    }
    output = {
        "result": [1, 2, 3],
        "metadata": {"count": 3, "sum": 6},
    }

    call = weave.log_call("complex_op", inputs, output)
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.inputs == inputs
    assert fetched_call.output == output


def test_log_call_with_empty_inputs(client: WeaveClient):
    """Test log_call with empty inputs dictionary."""
    call = weave.log_call("no_input_op", {}, "result")
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.inputs == {}
    assert fetched_call.output == "result"


def test_log_call_with_none_output(client: WeaveClient):
    """Test log_call with None as output."""
    call = weave.log_call("none_output_op", {"x": 1}, None)
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.output is None


def test_log_call_with_callable_display_name(client: WeaveClient):
    """Test log_call with a callable display name."""

    def make_display_name(call):
        return f"Call-{call.inputs.get('id', 'unknown')}"

    call = weave.log_call(
        "test_op",
        {"id": 123, "value": "test"},
        "result",
        display_name=make_display_name,
    )
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    # The callable should have been evaluated during call creation
    assert fetched_call.display_name == "Call-123"


def test_log_call_different_op_names(client: WeaveClient):
    """Test log_call with different operation names."""
    ops = ["op1", "op2", "my_custom_op", "process_data", "analyze"]
    for op_name in ops:
        weave.log_call(op_name, {"input": op_name}, f"output_{op_name}")

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == len(ops)

    # Verify each op has the correct name
    op_names = {c.func_name for c in fetched_calls}
    assert op_names == set(ops)


def test_log_call_with_combined_params(client: WeaveClient):
    """Test log_call with all parameters combined."""
    parent_call = weave.log_call("parent", {}, "parent_result")

    call = weave.log_call(
        op="combined_op",
        inputs={"x": 1, "y": 2},
        output={"sum": 3},
        parent=parent_call,
        attributes={"version": "2.0", "important": True},
        display_name="Combined Test",
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 2

    child = next(c for c in fetched_calls if c.id == call.id)
    assert child.inputs == {"x": 1, "y": 2}
    assert child.output == {"sum": 3}
    assert child.parent_id == parent_call.id
    # Check that our custom attributes are present (system may add additional attributes)
    assert child.attributes["version"] == "2.0"
    assert child.attributes["important"] is True
    assert child.display_name == "Combined Test"


def test_log_call_preserves_call_data(client: WeaveClient):
    """Test that the returned call object matches fetched data."""
    returned_call = weave.log_call("test_op", {"input": "test"}, {"output": "result"})

    fetched_calls = client.get_calls()
    fetched_call = fetched_calls[0]

    # The returned call should match the fetched one
    assert returned_call.id == fetched_call.id
    assert returned_call.inputs == fetched_call.inputs
    assert returned_call.output == fetched_call.output
    assert returned_call.op_name == fetched_call.op_name


def test_log_call_returns_finished_call(client: WeaveClient):
    """Test that log_call returns a finished call with timestamps."""
    call = weave.log_call("test_op", {"x": 1}, 2)

    # Fetch the call to get the complete data including timestamps
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]

    # The call should have both started_at and ended_at set
    assert fetched_call.started_at is not None
    assert fetched_call.ended_at is not None
    assert fetched_call.ended_at >= fetched_call.started_at


def test_log_call_with_use_stack_false(client: WeaveClient):
    """Test log_call with use_stack=False doesn't add to call stack."""
    # Log a call without adding to stack
    call = weave.log_call("test_op", {"x": 1}, 2, use_stack=False)

    # The call should still be logged
    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    assert fetched_calls[0].id == call.id

    # But it shouldn't be in the current call context
    current_call = weave.get_current_call()
    assert current_call is None


def test_log_call_with_started_at(client: WeaveClient):
    """Test log_call with a custom started_at timestamp."""
    import datetime

    custom_start = datetime.datetime(
        2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc
    )
    call = weave.log_call("test_op", {"x": 1}, 2, started_at=custom_start)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.started_at == custom_start


def test_log_call_with_ended_at(client: WeaveClient):
    """Test log_call with a custom ended_at timestamp."""
    import datetime

    custom_end = datetime.datetime(2024, 1, 15, 11, 45, 0, tzinfo=datetime.timezone.utc)
    call = weave.log_call("test_op", {"x": 1}, 2, ended_at=custom_end)

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.ended_at == custom_end


def test_log_call_with_both_timestamps(client: WeaveClient):
    """Test log_call with both started_at and ended_at timestamps."""
    import datetime

    custom_start = datetime.datetime(
        2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc
    )
    custom_end = datetime.datetime(2024, 1, 15, 10, 35, 0, tzinfo=datetime.timezone.utc)
    call = weave.log_call(
        "test_op", {"x": 1}, 2, started_at=custom_start, ended_at=custom_end
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.started_at == custom_start
    assert fetched_call.ended_at == custom_end


def test_log_call_retroactive_logging(client: WeaveClient):
    """Test log_call for retroactive logging of past operations."""
    import datetime

    # Simulate logging an operation that happened in the past
    past_start = datetime.datetime(2023, 6, 1, 9, 0, 0, tzinfo=datetime.timezone.utc)
    past_end = datetime.datetime(2023, 6, 1, 9, 5, 30, tzinfo=datetime.timezone.utc)

    call = weave.log_call(
        op="historical_data_processing",
        inputs={"batch_id": "batch_001", "records": 1000},
        output={"processed": 1000, "errors": 0},
        started_at=past_start,
        ended_at=past_end,
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 1
    fetched_call = fetched_calls[0]
    assert fetched_call.started_at == past_start
    assert fetched_call.ended_at == past_end
    # Verify duration can be calculated
    duration = fetched_call.ended_at - fetched_call.started_at
    assert duration.total_seconds() == 330  # 5 minutes 30 seconds


def test_log_call_with_timestamps_and_all_params(client: WeaveClient):
    """Test log_call with timestamps combined with all other parameters."""
    import datetime

    parent_call = weave.log_call("parent", {}, "parent_result")

    custom_start = datetime.datetime(
        2024, 3, 20, 14, 0, 0, tzinfo=datetime.timezone.utc
    )
    custom_end = datetime.datetime(2024, 3, 20, 14, 10, 0, tzinfo=datetime.timezone.utc)

    call = weave.log_call(
        op="full_test_op",
        inputs={"x": 1, "y": 2},
        output={"result": 3},
        parent=parent_call,
        attributes={"env": "production", "version": "2.0"},
        display_name="Full Test Operation",
        started_at=custom_start,
        ended_at=custom_end,
    )

    fetched_calls = client.get_calls()
    assert len(fetched_calls) == 2

    child = next(c for c in fetched_calls if c.id == call.id)
    assert child.inputs == {"x": 1, "y": 2}
    assert child.output == {"result": 3}
    assert child.parent_id == parent_call.id
    assert child.attributes["env"] == "production"
    assert child.attributes["version"] == "2.0"
    assert child.display_name == "Full Test Operation"
    assert child.started_at == custom_start
    assert child.ended_at == custom_end


def test_log_call_with_use_stack_true(client: WeaveClient):
    """Test log_call with use_stack=True adds to and removes from call stack."""

    # Create an op context first
    @weave.op
    def parent_op():
        parent = weave.require_current_call()

        # Log a call with use_stack=True - it will be pushed then immediately popped
        # when finished, so the parent remains current
        inner_call = weave.log_call("inner_op", {"x": 1}, 2, use_stack=True)

        # After the call is finished, we should be back to the parent
        current = weave.require_current_call()
        return parent.id, current.id, inner_call.id

    parent_id, current_id, inner_id = parent_op()

    # After finishing the inner call, we should be back to the parent
    assert parent_id == current_id

    # Verify the inner call was created with the correct parent
    fetched_calls = client.get_calls()
    inner = next(c for c in fetched_calls if c.id == inner_id)
    assert inner.parent_id == parent_id


def test_log_call_use_stack_default_behavior(client: WeaveClient):
    """Test that use_stack defaults to True."""

    @weave.op
    def outer_op():
        parent = weave.require_current_call()

        # Log a call without specifying use_stack (should default to True)
        inner_call = weave.log_call("inner_op", {"x": 1}, 2)

        # After finishing, we should be back to the parent
        current = weave.require_current_call()
        return parent.id, current.id, inner_call.id

    parent_id, current_id, inner_id = outer_op()

    # Should have been pushed and popped from stack
    assert parent_id == current_id

    # Verify the inner call was created with the correct parent
    fetched_calls = client.get_calls()
    inner = next(c for c in fetched_calls if c.id == inner_id)
    assert inner.parent_id == parent_id
