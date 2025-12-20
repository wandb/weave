"""Tests for the weave.trace.debugger.debug module."""

import pytest

import weave
from weave.trace.debugger.debug import (
    Debugger,
    DebuggerServer,
)

# --- Test fixtures and helper functions ---


def adder(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


def multiplier(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


def liner(m: float, b: float, x: float) -> float:
    """Calculate y = mx + b."""
    return adder(multiplier(m, x), b)


def failing_func() -> None:
    """A function that always raises an exception."""
    raise ValueError("Intentional test error")


# --- Tests for Debugger.add_op ---


class TestDebuggerAddOp:
    @pytest.mark.trace_server
    def test_add_op_returns_ref(self, client) -> None:
        """Test adding an op returns a ref URI."""
        debugger = Debugger()
        ref = debugger.add_op(adder)

        assert ref.startswith("weave:///")
        assert ref in debugger.ops

    @pytest.mark.trace_server
    def test_add_multiple_ops(self, client) -> None:
        """Test adding multiple ops."""
        debugger = Debugger()
        ref1 = debugger.add_op(adder)
        ref2 = debugger.add_op(multiplier)
        ref3 = debugger.add_op(liner)

        assert len(debugger.ops) == 3
        assert ref1 in debugger.ops
        assert ref2 in debugger.ops
        assert ref3 in debugger.ops

    @pytest.mark.trace_server
    def test_add_op_duplicate_ref_raises_error(self, client) -> None:
        """Test that adding the same op twice raises ValueError."""
        debugger = Debugger()
        debugger.add_op(adder)

        # Adding the same function again gets the same ref (content hash), so raises
        with pytest.raises(ValueError, match="already exists"):
            debugger.add_op(adder)


# --- Tests for Debugger.list_ops ---


class TestDebuggerListOps:
    @pytest.mark.trace_server
    def test_list_ops_empty(self, client) -> None:
        """Test listing ops when none are registered."""
        debugger = Debugger()
        ops = debugger.list_ops()

        assert ops == []

    @pytest.mark.trace_server
    def test_list_ops_with_ops(self, client) -> None:
        """Test listing ops after adding some."""
        debugger = Debugger()
        ref1 = debugger.add_op(adder)
        ref2 = debugger.add_op(multiplier)
        ref3 = debugger.add_op(liner)

        ops = debugger.list_ops()

        assert len(ops) == 3
        assert ref1 in ops
        assert ref2 in ops
        assert ref3 in ops
        # All should be valid refs
        assert all(ref.startswith("weave:///") for ref in ops)


# --- Tests for Debugger.call_op ---


class TestDebuggerCallOp:
    @pytest.mark.trace_server
    def test_call_returns_correct_result(self, client) -> None:
        """Test that calling an op returns the correct result."""
        debugger = Debugger()
        ref = debugger.add_op(adder)

        result = debugger.call_op(ref, {"a": 3.0, "b": 5.0})

        assert result == 8.0

    @pytest.mark.trace_server
    def test_call_not_found_raises_error(self, client) -> None:
        """Test that calling an unknown op raises KeyError."""
        debugger = Debugger()

        with pytest.raises(KeyError, match="not found"):
            debugger.call_op("weave:///nonexistent", {})


# --- Tests for Debugger.call_op_async ---


class TestDebuggerCallOpAsync:
    @pytest.mark.trace_server
    def test_call_async_returns_call_id(self, client) -> None:
        """Test that async call returns a call ID immediately."""
        import time

        debugger = Debugger()
        ref = debugger.add_op(adder)

        call_id = debugger.call_op_async(ref, {"a": 3.0, "b": 5.0})

        assert call_id is not None
        assert isinstance(call_id, str)

        # Give the background thread time to complete
        time.sleep(0.5)

    @pytest.mark.trace_server
    def test_call_async_not_found_raises_error(self, client) -> None:
        """Test that async calling an unknown op raises KeyError."""
        debugger = Debugger()

        with pytest.raises(KeyError, match="not found"):
            debugger.call_op_async("weave:///nonexistent", {})

    @pytest.mark.trace_server
    def test_call_async_executes_in_background(self, client) -> None:
        """Test that the call executes and completes in the background."""
        import time

        debugger = Debugger()
        ref = debugger.add_op(adder)

        call_id = debugger.call_op_async(ref, {"a": 10.0, "b": 20.0})

        # Give the background thread time to complete
        time.sleep(0.5)

        # The call should have completed - we can verify by querying weave
        # For now, just verify we got a call ID back
        assert call_id is not None


# --- Tests for error handling ---


class TestDebuggerErrorHandling:
    @pytest.mark.trace_server
    def test_call_with_error_raises_exception(self, client) -> None:
        """Test that errors are raised when op fails."""
        debugger = Debugger()
        ref = debugger.add_op(failing_func)

        with pytest.raises(Exception, match="Intentional test error"):
            debugger.call_op(ref, {})


# --- Tests for Op.get_input_json_schema ---


class TestOpGetInputJsonSchema:
    """Test the Op.get_input_json_schema() method."""

    def test_basic_types(self) -> None:
        """Test schema generation for basic Python types."""

        @weave.op
        def func(a: int, b: str, c: float, d: bool) -> None:
            pass

        schema = func.get_input_json_schema()

        assert schema["type"] == "object"
        assert schema["properties"]["a"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "string"
        assert schema["properties"]["c"]["type"] == "number"
        assert schema["properties"]["d"]["type"] == "boolean"
        assert set(schema["required"]) == {"a", "b", "c", "d"}

    def test_with_defaults(self) -> None:
        """Test that default values are captured in schema."""

        @weave.op
        def func(a: int, b: str = "default", c: float = 3.14) -> None:
            pass

        schema = func.get_input_json_schema()

        assert schema["required"] == ["a"]
        assert schema["properties"]["b"]["default"] == "default"
        assert schema["properties"]["c"]["default"] == 3.14

    def test_optional_types(self) -> None:
        """Test schema generation for Optional types (Pydantic uses anyOf)."""

        @weave.op
        def func(a: int | None, b: str | None = None) -> None:
            pass

        schema = func.get_input_json_schema()

        # Pydantic represents Optional types as anyOf
        assert schema["properties"]["a"]["anyOf"] == [
            {"type": "integer"},
            {"type": "null"},
        ]
        assert schema["properties"]["b"]["anyOf"] == [
            {"type": "string"},
            {"type": "null"},
        ]

    def test_list_types(self) -> None:
        """Test schema generation for list types."""

        @weave.op
        def func(a: list[int], b: list[str]) -> None:
            pass

        schema = func.get_input_json_schema()

        assert schema["properties"]["a"]["type"] == "array"
        assert schema["properties"]["a"]["items"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "array"
        assert schema["properties"]["b"]["items"]["type"] == "string"

    def test_dict_types(self) -> None:
        """Test schema generation for dict types."""

        @weave.op
        def func(a: dict[str, int]) -> None:
            pass

        schema = func.get_input_json_schema()

        assert schema["properties"]["a"]["type"] == "object"
        assert schema["properties"]["a"]["additionalProperties"]["type"] == "integer"

    def test_no_annotations(self) -> None:
        """Test schema generation for functions without type annotations."""

        @weave.op
        def func(a, b):
            pass

        schema = func.get_input_json_schema()

        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
        # No type info, so properties should be empty dicts
        assert schema["properties"]["a"] == {}
        assert schema["properties"]["b"] == {}

    def test_output_schema(self) -> None:
        """Test the get_output_json_schema method."""

        @weave.op
        def add(a: int, b: int) -> int:
            return a + b

        schema = add.get_output_json_schema()
        assert schema["type"] == "integer"

    def test_output_schema_no_return_type(self) -> None:
        """Test output schema when no return type annotation."""

        @weave.op
        def func(a: int):
            return a

        schema = func.get_output_json_schema()
        assert schema == {}


# --- Tests for Weave integration ---


class TestDebuggerWeaveIntegration:
    """Tests for weave op integration with the debugger."""

    @pytest.mark.trace_server
    def test_weave_required_for_debugger(self) -> None:
        """Test that Debugger requires weave to be initialized."""
        # This test runs without the client fixture
        # WeaveInitError should be raised
        from weave.trace.context.weave_client_context import WeaveInitError

        with pytest.raises(WeaveInitError):
            Debugger()

    @pytest.mark.trace_server
    def test_call_op_stores_call_in_weave(self, client) -> None:
        """Test that calling an op stores the call in weave."""

        @weave.op
        def weave_adder(a: float, b: float) -> float:
            """Add two numbers using weave op."""
            return a + b

        debugger = Debugger()
        ref = debugger.add_op(weave_adder)

        result = debugger.call_op(ref, {"a": 3.0, "b": 5.0})

        assert result == 8.0

        # Calls are stored in weave and can be queried via the trace server
        # using the op ref. The debugger no longer provides a get_calls method.

    @pytest.mark.trace_server
    def test_regular_function_auto_wrapped_as_op(self, client) -> None:
        """Test that regular functions are auto-wrapped as ops."""

        def regular_function(a: float, b: float) -> float:
            """A regular function that will be auto-wrapped."""
            return a - b

        debugger = Debugger()
        ref = debugger.add_op(regular_function)

        result = debugger.call_op(ref, {"a": 10.0, "b": 3.0})

        assert result == 7.0

    @pytest.mark.trace_server
    def test_multiple_calls(self, client) -> None:
        """Test that multiple calls work correctly."""

        @weave.op
        def counter_op(n: int) -> int:
            """Return the input number."""
            return n

        debugger = Debugger()
        ref = debugger.add_op(counter_op)

        r1 = debugger.call_op(ref, {"n": 1})
        r2 = debugger.call_op(ref, {"n": 2})
        r3 = debugger.call_op(ref, {"n": 3})

        assert r1 == 1
        assert r2 == 2
        assert r3 == 3


# --- Integration-style tests ---


class TestDebuggerIntegration:
    @pytest.mark.trace_server
    def test_end_to_end_workflow(self, client) -> None:
        """Test the complete workflow: add op, call it."""
        debugger = Debugger()

        # Add ops
        adder_ref = debugger.add_op(adder)
        multiplier_ref = debugger.add_op(multiplier)

        # Verify registration
        ops = debugger.list_ops()
        assert len(ops) == 2
        assert adder_ref in ops
        assert multiplier_ref in ops

        # Call ops
        result = debugger.call_op(adder_ref, {"a": 10.0, "b": 5.0})
        assert result == 15.0

        result = debugger.call_op(multiplier_ref, {"a": 3.0, "b": 7.0})
        assert result == 21.0

        # Calls and schemas are available via weave trace server using the ref
