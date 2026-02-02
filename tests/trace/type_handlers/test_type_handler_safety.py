"""Tests to verify that type handlers never crash user code.

Requirement: The weave op decorator is complex but should never crash user code.
Type handlers that fail during serialization should gracefully degrade without
affecting the user's program execution.
"""

from __future__ import annotations

import weave
from tests.trace.test_utils import FailingSaveType


def test_op_output_with_failing_serializer_returns_value(client, failing_serializer):
    """Requirement: Op functions must return their values even when serialization fails
    Interface: @weave.op decorated function returning an object with failing type handler
    Given: An @weave.op function returns an object whose type handler save raises an exception
    When: The function is called
    Then: The function returns the correct value to the user (not None, not an exception)
    """

    @weave.op
    def return_failing_type(value: str) -> FailingSaveType:
        return FailingSaveType(value)

    # This should NOT raise - the user should get their return value
    result = return_failing_type("hello")

    # The user must receive the actual object they created
    assert isinstance(result, FailingSaveType)
    assert result.value == "hello"


def test_op_input_with_failing_serializer_executes_normally(client, failing_serializer):
    """Requirement: Op functions must execute normally even when input serialization fails
    Interface: @weave.op decorated function accepting an object with failing type handler
    Given: An @weave.op function accepts an object whose type handler save raises an exception
    When: The function is called
    Then: The function executes normally and returns the expected result
    """

    @weave.op
    def process_failing_type(obj: FailingSaveType) -> str:
        return f"processed: {obj.value}"

    failing_obj = FailingSaveType("test_input")

    # This should NOT raise - the function should execute normally
    result = process_failing_type(failing_obj)

    # The function must return its computed result
    assert result == "processed: test_input"


def test_op_with_failing_serializer_call_is_recorded(client, failing_serializer):
    """Requirement: Calls should still be recorded even when serialization fails (with stringified fallback)
    Interface: @weave.op decorated function and call record retrieval
    Given: An @weave.op function returns an object whose type handler save fails
    When: The function is called and we fetch the call record
    Then: The call is recorded with a stringified representation of the failed object
    """

    @weave.op
    def return_failing_for_record(value: str) -> FailingSaveType:
        return FailingSaveType(value)

    # Call the function
    result = return_failing_for_record("record_test")

    # Ensure the result was returned correctly
    assert isinstance(result, FailingSaveType)
    assert result.value == "record_test"

    # Flush to ensure the call is recorded
    client.flush()

    # Get the call record
    calls = return_failing_for_record.calls()
    assert len(calls) == 1

    call = calls[0]

    # The output should be recorded - either as the actual object (if serialization
    # worked on the second try or there's a fallback) or as a stringified version
    # The key assertion is that the call record exists and has an output
    assert call.output is not None

    # If it fell back to stringify, it would be a string representation
    # If serialization succeeded elsewhere, it might be the actual object
    # Either way, the call should be recorded
    output_str = str(call.output)
    assert "record_test" in output_str or "FailingSaveType" in output_str


def test_op_with_multiple_args_one_failing_serializer(client, failing_serializer):
    """Requirement: A failing serializer for one argument should not affect other arguments
    Interface: @weave.op decorated function with multiple arguments
    Given: An @weave.op function has multiple args, one with a failing type handler
    When: The function is called
    Then: The function executes normally and non-failing arguments are serialized properly
    """

    @weave.op
    def mixed_args(normal_arg: str, failing_arg: FailingSaveType) -> str:
        return f"{normal_arg}: {failing_arg.value}"

    failing_obj = FailingSaveType("failing_value")

    # This should NOT raise
    result = mixed_args("normal", failing_obj)

    # Function should execute normally
    assert result == "normal: failing_value"

    # Verify call was recorded
    client.flush()
    calls = mixed_args.calls()
    assert len(calls) == 1

    call = calls[0]
    # The normal_arg should be serialized properly
    assert call.inputs["normal_arg"] == "normal"
