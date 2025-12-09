"""Tests for the weave.trace.debugger.debug module."""

import pytest

import weave
from weave.trace.debugger.debug import (
    CallableInfo,
    Debugger,
    DebuggerServer,
    Span,
    _derive_callable_name,
    _safe_serialize_value,
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


# --- Tests for _derive_callable_name ---


class TestDeriveCallableName:
    def test_derives_name_from_function(self) -> None:
        """Test that _derive_callable_name extracts the function's __name__."""
        assert _derive_callable_name(adder) == "adder"
        assert _derive_callable_name(multiplier) == "multiplier"
        assert _derive_callable_name(liner) == "liner"

    def test_derives_name_from_lambda(self) -> None:
        """Test that _derive_callable_name works with lambda functions."""
        my_lambda = lambda x: x * 2
        assert _derive_callable_name(my_lambda) == "<lambda>"


# --- Tests for _safe_serialize_value ---


class TestSafeSerializeValue:
    def test_serializes_primitives(self) -> None:
        """Test serialization of primitive types."""
        assert _safe_serialize_value("hello") == "hello"
        assert _safe_serialize_value(42) == 42
        assert _safe_serialize_value(3.14) == 3.14
        assert _safe_serialize_value(True) is True
        assert _safe_serialize_value(False) is False

    def test_serializes_lists(self) -> None:
        """Test serialization of lists."""
        assert _safe_serialize_value([1, 2, 3]) == [1, 2, 3]
        assert _safe_serialize_value(["a", "b"]) == ["a", "b"]

    def test_serializes_tuples(self) -> None:
        """Test serialization of tuples (converted to lists)."""
        assert _safe_serialize_value((1, 2, 3)) == [1, 2, 3]

    def test_serializes_dicts(self) -> None:
        """Test serialization of dictionaries."""
        assert _safe_serialize_value({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_serializes_nested_structures(self) -> None:
        """Test serialization of nested data structures."""
        nested = {"list": [1, 2, {"inner": "value"}], "tuple": (3, 4)}
        expected = {"list": [1, 2, {"inner": "value"}], "tuple": [3, 4]}
        assert _safe_serialize_value(nested) == expected

    def test_serializes_custom_objects_to_string(self) -> None:
        """Test that custom objects are converted to their string representation."""

        class CustomObj:
            def __str__(self) -> str:
                return "CustomObj()"

        obj = CustomObj()
        assert _safe_serialize_value(obj) == "CustomObj()"


# --- Tests for Debugger.add_callable ---


class TestDebuggerAddCallable:
    @pytest.mark.trace_server
    def test_add_callable_returns_ref(self, client) -> None:
        """Test adding a callable returns a ref URI."""
        debugger = Debugger()
        ref = debugger.add_callable(adder)

        assert ref.startswith("weave:///")
        assert ref in debugger.callables

    @pytest.mark.trace_server
    def test_add_callable_with_custom_name(self, client) -> None:
        """Test adding a callable with a custom name."""
        debugger = Debugger()
        ref = debugger.add_callable(adder, name="my_adder")

        assert ref.startswith("weave:///")
        # Check the name is stored
        callables = debugger.list_callables()
        assert any(c.name == "my_adder" for c in callables)

    @pytest.mark.trace_server
    def test_add_multiple_callables(self, client) -> None:
        """Test adding multiple callables."""
        debugger = Debugger()
        ref1 = debugger.add_callable(adder)
        ref2 = debugger.add_callable(multiplier)
        ref3 = debugger.add_callable(liner)

        assert len(debugger.callables) == 3
        assert ref1 in debugger.callables
        assert ref2 in debugger.callables
        assert ref3 in debugger.callables

    @pytest.mark.trace_server
    def test_add_callable_duplicate_ref_raises_error(self, client) -> None:
        """Test that adding the same callable twice raises ValueError."""
        debugger = Debugger()
        debugger.add_callable(adder)

        # Adding the same function again gets the same ref (content hash), so raises
        with pytest.raises(ValueError, match="already exists"):
            debugger.add_callable(adder)


# --- Tests for Debugger.list_callables ---


class TestDebuggerListCallables:
    @pytest.mark.trace_server
    def test_list_callables_empty(self, client) -> None:
        """Test listing callables when none are registered."""
        debugger = Debugger()
        callables = debugger.list_callables()

        assert callables == []

    @pytest.mark.trace_server
    def test_list_callables_with_callables(self, client) -> None:
        """Test listing callables after adding some."""
        debugger = Debugger()
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)
        debugger.add_callable(liner)

        callables = debugger.list_callables()

        assert len(callables) == 3
        names = {c.name for c in callables}
        assert names == {"adder", "multiplier", "liner"}
        # All should have refs
        assert all(c.ref.startswith("weave:///") for c in callables)


# --- Tests for Debugger.invoke_callable ---


class TestDebuggerInvokeCallable:
    @pytest.mark.trace_server
    def test_invoke_returns_correct_result(self, client) -> None:
        """Test that invoking a callable returns the correct result."""
        debugger = Debugger()
        ref = debugger.add_callable(adder)

        result = debugger.invoke_callable(ref, {"a": 3.0, "b": 5.0})

        assert result == 8.0

    @pytest.mark.trace_server
    def test_invoke_not_found_raises_error(self, client) -> None:
        """Test that invoking an unknown callable raises KeyError."""
        debugger = Debugger()

        with pytest.raises(KeyError, match="not found"):
            debugger.invoke_callable("weave:///nonexistent", {})


# --- Tests for Debugger.get_calls ---


class TestDebuggerGetCalls:
    @pytest.mark.trace_server
    def test_get_calls_not_found_raises_error(self, client) -> None:
        """Test that getting calls for unknown callable raises KeyError."""
        debugger = Debugger()

        with pytest.raises(KeyError, match="not found"):
            debugger.get_calls("weave:///nonexistent")


# --- Tests for error handling ---


class TestDebuggerErrorHandling:
    @pytest.mark.trace_server
    def test_invoke_with_error_raises_exception(self, client) -> None:
        """Test that errors are raised when callable fails."""
        debugger = Debugger()
        ref = debugger.add_callable(failing_func)

        with pytest.raises(Exception, match="Intentional test error"):
            debugger.invoke_callable(ref, {})


# --- Tests for Span model ---


class TestSpanModel:
    def test_span_creation(self) -> None:
        """Test creating a Span with all fields."""
        span = Span(
            name="test",
            start_time_unix_nano=1000.0,
            end_time_unix_nano=2000.0,
            inputs={"a": 1},
            output=42,
            error=None,
        )

        assert span.name == "test"
        assert span.start_time_unix_nano == 1000.0
        assert span.end_time_unix_nano == 2000.0
        assert span.inputs == {"a": 1}
        assert span.output == 42
        assert span.error is None

    def test_span_with_error(self) -> None:
        """Test creating a Span with an error."""
        span = Span(
            name="test",
            start_time_unix_nano=1000.0,
            end_time_unix_nano=2000.0,
            inputs={},
            output=None,
            error="Something went wrong",
        )

        assert span.error == "Something went wrong"

    def test_span_with_weave_call_ref(self) -> None:
        """Test creating a Span with a weave call ref."""
        span = Span(
            name="test",
            start_time_unix_nano=1000.0,
            end_time_unix_nano=2000.0,
            inputs={"a": 1},
            output=42,
            error=None,
            weave_call_ref="weave:///entity/project/call/abc123",
        )

        assert span.weave_call_ref == "weave:///entity/project/call/abc123"


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


# --- Tests for Debugger.get_json_schema ---


class TestDebuggerGetJsonSchema:
    @pytest.mark.trace_server
    def test_get_json_schema(self, client) -> None:
        """Test getting JSON schema for a registered callable."""
        debugger = Debugger()
        ref = debugger.add_callable(adder)

        schema = debugger.get_json_schema(ref)

        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]

    @pytest.mark.trace_server
    def test_get_json_schema_not_found(self, client) -> None:
        """Test that KeyError is raised for unknown callable."""
        debugger = Debugger()

        with pytest.raises(KeyError, match="not found"):
            debugger.get_json_schema("weave:///nonexistent")


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
    def test_invoke_op_stores_call_in_weave(self, client) -> None:
        """Test that invoking an op stores the call in weave."""

        @weave.op
        def weave_adder(a: float, b: float) -> float:
            """Add two numbers using weave op."""
            return a + b

        debugger = Debugger()
        ref = debugger.add_callable(weave_adder)

        result = debugger.invoke_callable(ref, {"a": 3.0, "b": 5.0})

        assert result == 8.0

        # Query calls from weave
        calls = debugger.get_calls(ref)
        assert len(calls) >= 1  # At least our call

        # Find our call
        our_call = next(
            (c for c in calls if c.inputs.get("a") == 3.0 and c.inputs.get("b") == 5.0),
            None,
        )
        assert our_call is not None
        assert our_call.output == 8.0
        assert our_call.weave_call_ref is not None
        assert our_call.weave_call_ref.startswith("weave:///")

    @pytest.mark.trace_server
    def test_regular_function_auto_wrapped_as_op(self, client) -> None:
        """Test that regular functions are auto-wrapped as ops."""

        def regular_function(a: float, b: float) -> float:
            """A regular function that will be auto-wrapped."""
            return a - b

        debugger = Debugger()
        ref = debugger.add_callable(regular_function)

        result = debugger.invoke_callable(ref, {"a": 10.0, "b": 3.0})

        assert result == 7.0

        # Should have calls in weave
        calls = debugger.get_calls(ref)
        assert len(calls) >= 1

    @pytest.mark.trace_server
    def test_multiple_invocations_tracked(self, client) -> None:
        """Test that multiple invocations are tracked in weave."""

        @weave.op
        def counter_op(n: int) -> int:
            """Return the input number."""
            return n

        debugger = Debugger()
        ref = debugger.add_callable(counter_op)

        debugger.invoke_callable(ref, {"n": 1})
        debugger.invoke_callable(ref, {"n": 2})
        debugger.invoke_callable(ref, {"n": 3})

        calls = debugger.get_calls(ref)
        assert len(calls) >= 3

        # Each call should have a unique weave_call_ref
        call_refs = [c.weave_call_ref for c in calls if c.weave_call_ref]
        assert len(set(call_refs)) >= 3  # All refs should be unique


# --- Integration-style tests ---


class TestDebuggerIntegration:
    @pytest.mark.trace_server
    def test_end_to_end_workflow(self, client) -> None:
        """Test the complete workflow: add callable, invoke it, retrieve calls."""
        debugger = Debugger()

        # Add callables
        adder_ref = debugger.add_callable(adder)
        multiplier_ref = debugger.add_callable(multiplier)

        # Verify registration
        callables = debugger.list_callables()
        names = {c.name for c in callables}
        assert names == {"adder", "multiplier"}

        # Invoke callables
        result = debugger.invoke_callable(adder_ref, {"a": 10.0, "b": 5.0})
        assert result == 15.0

        result = debugger.invoke_callable(multiplier_ref, {"a": 3.0, "b": 7.0})
        assert result == 21.0

        # Verify calls are tracked
        adder_calls = debugger.get_calls(adder_ref)
        assert len(adder_calls) >= 1

        multiplier_calls = debugger.get_calls(multiplier_ref)
        assert len(multiplier_calls) >= 1

        # Verify schema
        schema = debugger.get_json_schema(adder_ref)
        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
