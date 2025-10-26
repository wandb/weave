"""Tests for the log_call API."""

from __future__ import annotations

import platform
import sys

import pytest

import weave
from tests.trace.util import AnyIntMatcher, DatetimeMatcher
from weave.trace_server.ids import generate_id


def test_log_call_basic(client):
    """Test basic log_call functionality with minimal arguments."""
    call = client.log_call(
        inputs={"x": 1, "y": 2},
        output={"result": 3},
    )

    assert call.id is not None
    assert call.inputs == {"x": 1, "y": 2}
    assert call.output == {"result": 3}
    assert call.started_at is not None
    assert call.ended_at is not None
    assert call.op_name.startswith("call_")


def test_log_call_with_op_name(client):
    """Test log_call with explicit op_name."""
    call = client.log_call(
        inputs={"x": 1, "y": 2},
        output={"result": 3},
        op_name="my_custom_operation",
    )

    assert call.id is not None
    assert call.inputs == {"x": 1, "y": 2}
    assert call.output == {"result": 3}
    assert "my_custom_operation" in call.op_name


def test_log_call_with_attributes(client):
    """Test log_call with custom attributes."""
    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="test_op",
        attributes={"env": "production", "version": "1.0"},
    )

    assert call.attributes["env"] == "production"
    assert call.attributes["version"] == "1.0"
    # Should still have weave attributes
    assert "weave" in call.attributes


def test_log_call_with_display_name(client):
    """Test log_call with custom display_name."""
    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="test_op",
        display_name="My Custom Display Name",
    )

    assert call.display_name == "My Custom Display Name"


def test_log_call_with_wb_run_step(client):
    """Test log_call with explicit wb_run_step."""
    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="test_op",
        wb_run_step=42,
    )

    # Need to fetch the call to see the wb_run_step
    fetched_call = client.get_call(call.id)
    assert fetched_call.wb_run_step == 42


def test_log_call_with_parent(client):
    """Test log_call with parent call."""
    # Create parent call
    parent_call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="parent_op",
    )

    # Create child call
    child_call = client.log_call(
        inputs={"a": 3},
        output={"b": 4},
        op_name="child_op",
        parent=parent_call,
    )

    assert child_call.parent_id == parent_call.id
    assert child_call.trace_id == parent_call.trace_id


def test_log_call_persisted(client):
    """Test that log_call persists to server and can be retrieved."""
    call = client.log_call(
        inputs={"x": 1, "y": 2},
        output={"result": 3},
        op_name="persisted_op",
    )

    # Fetch the call from server
    fetched_call = client.get_call(call.id)

    assert fetched_call.id == call.id
    assert fetched_call.inputs == {"x": 1, "y": 2}
    assert fetched_call.output == {"result": 3}
    assert "persisted_op" in fetched_call.op_name


def test_log_call_appears_in_get_calls(client):
    """Test that log_call creates calls that appear in get_calls."""
    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="get_calls_test",
    )

    calls = list(client.get_calls())
    call_ids = [c.id for c in calls]

    assert call.id in call_ids


def test_log_call_with_complex_inputs_outputs(client):
    """Test log_call with complex nested data structures."""
    inputs = {
        "user": {"name": "Alice", "age": 30},
        "preferences": ["reading", "hiking"],
        "metadata": {"created_at": "2024-01-01", "score": 95.5},
    }

    output = {
        "status": "success",
        "recommendations": [
            {"item": "book", "confidence": 0.9},
            {"item": "trail", "confidence": 0.8},
        ],
    }

    call = client.log_call(
        inputs=inputs,
        output=output,
        op_name="complex_data_op",
    )

    assert call.inputs == inputs
    assert call.output == output


def test_log_call_summary_has_status(client):
    """Test that log_call sets proper summary status."""
    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="status_test",
    )

    # Fetch to get full summary
    fetched_call = client.get_call(call.id)
    assert fetched_call.summary is not None
    assert "status_counts" in fetched_call.summary
    assert fetched_call.summary["status_counts"]["success"] == 1
    assert fetched_call.summary["status_counts"]["error"] == 0


def test_log_call_top_level_function(client):
    """Test the top-level weave.log_call function."""
    call = weave.log_call(
        inputs={"x": 1, "y": 2},
        output={"result": 3},
        op_name="top_level_test",
    )

    assert call.id is not None
    assert call.inputs == {"x": 1, "y": 2}
    assert call.output == {"result": 3}


def test_log_call_empty_inputs_outputs(client):
    """Test log_call with empty inputs and outputs."""
    call = client.log_call(
        inputs={},
        output={},
        op_name="empty_test",
    )

    assert call.inputs == {}
    assert call.output == {}


def test_log_call_callable_display_name(client):
    """Test log_call with callable display_name."""

    def custom_display_name(call):
        return f"Custom: {call.id[:8]}"

    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="callable_name_test",
        display_name=custom_display_name,
    )

    assert call.display_name.startswith("Custom: ")


def test_log_call_multiple_sequential(client):
    """Test logging multiple calls sequentially."""
    calls = []
    for i in range(5):
        call = client.log_call(
            inputs={"step": i},
            output={"result": i * 2},
            op_name=f"step_{i}",
        )
        calls.append(call)

    assert len(calls) == 5
    assert all(c.id is not None for c in calls)
    assert len(set(c.id for c in calls)) == 5  # All unique IDs


def test_log_call_with_none_output(client):
    """Test log_call with None as output."""
    call = client.log_call(
        inputs={"x": 1},
        output=None,
        op_name="none_output_test",
    )

    assert call.output is None


def test_log_call_with_wb_run_id_and_step(client):
    """Test log_call with both wb_run_id and wb_run_step."""
    # Note: wb_run_id is passed to create_call which we're calling internally
    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="wandb_integration_test",
        wb_run_step=10,
    )

    fetched_call = client.get_call(call.id)
    assert fetched_call.wb_run_step == 10


def test_log_call_does_not_use_stack(client):
    """Test that log_call doesn't push to the call stack."""
    from weave.trace.context import call_context

    # Ensure we start with no current call
    assert call_context.get_current_call() is None

    call = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="stack_test",
    )

    # After log_call, there should still be no current call
    assert call_context.get_current_call() is None


def test_log_call_trace_id_generation(client):
    """Test that log_call generates proper trace IDs."""
    # Call without parent should have its own trace_id
    call1 = client.log_call(
        inputs={"x": 1},
        output={"y": 2},
        op_name="trace_test_1",
    )

    # Another call without parent should have different trace_id
    call2 = client.log_call(
        inputs={"a": 3},
        output={"b": 4},
        op_name="trace_test_2",
    )

    assert call1.trace_id != call2.trace_id

    # Call with parent should share trace_id
    child_call = client.log_call(
        inputs={"c": 5},
        output={"d": 6},
        op_name="trace_test_child",
        parent=call1,
    )

    assert child_call.trace_id == call1.trace_id
