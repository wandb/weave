"""Tests for the weave.trace.debugger.debug module."""

import pytest
from fastapi import HTTPException

import weave
from weave.trace.debugger.debug import (
    Debugger,
    Span,
    derive_callable_name,
    get_callable_input_json_schema,
    safe_serialize_input_value,
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


# --- Tests for derive_callable_name ---


class TestDeriveCallableName:
    def test_derives_name_from_function(self) -> None:
        """Test that derive_callable_name extracts the function's __name__."""
        assert derive_callable_name(adder) == "adder"
        assert derive_callable_name(multiplier) == "multiplier"
        assert derive_callable_name(liner) == "liner"

    def test_derives_name_from_lambda(self) -> None:
        """Test that derive_callable_name works with lambda functions."""
        my_lambda = lambda x: x * 2
        assert derive_callable_name(my_lambda) == "<lambda>"


# --- Tests for safe_serialize_input_value ---


class TestSafeSerializeInputValue:
    def test_serializes_primitives(self) -> None:
        """Test serialization of primitive types."""
        assert safe_serialize_input_value("hello") == "hello"
        assert safe_serialize_input_value(42) == 42
        assert safe_serialize_input_value(3.14) == 3.14
        assert safe_serialize_input_value(True) is True
        assert safe_serialize_input_value(False) is False

    def test_serializes_lists(self) -> None:
        """Test serialization of lists."""
        assert safe_serialize_input_value([1, 2, 3]) == [1, 2, 3]
        assert safe_serialize_input_value(["a", "b"]) == ["a", "b"]

    def test_serializes_tuples(self) -> None:
        """Test serialization of tuples (converted to lists)."""
        assert safe_serialize_input_value((1, 2, 3)) == [1, 2, 3]

    def test_serializes_dicts(self) -> None:
        """Test serialization of dictionaries."""
        assert safe_serialize_input_value({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_serializes_nested_structures(self) -> None:
        """Test serialization of nested data structures."""
        nested = {"list": [1, 2, {"inner": "value"}], "tuple": (3, 4)}
        expected = {"list": [1, 2, {"inner": "value"}], "tuple": [3, 4]}
        assert safe_serialize_input_value(nested) == expected

    def test_serializes_custom_objects_to_string(self) -> None:
        """Test that custom objects are converted to their string representation."""

        class CustomObj:
            def __str__(self) -> str:
                return "CustomObj()"

        obj = CustomObj()
        assert safe_serialize_input_value(obj) == "CustomObj()"


# --- Tests for Debugger.add_callable ---


class TestDebuggerAddCallable:
    def test_add_callable_with_auto_derived_name(self) -> None:
        """Test adding a callable without specifying a name."""
        debugger = Debugger()
        debugger.add_callable(adder)

        assert "adder" in debugger.callables
        assert debugger.callables["adder"] is adder

    def test_add_callable_with_custom_name(self) -> None:
        """Test adding a callable with a custom name."""
        debugger = Debugger()
        debugger.add_callable(adder, name="my_adder")

        assert "my_adder" in debugger.callables
        assert debugger.callables["my_adder"] is adder
        assert "adder" not in debugger.callables

    def test_add_multiple_callables(self) -> None:
        """Test adding multiple callables."""
        debugger = Debugger()
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)
        debugger.add_callable(liner)

        assert len(debugger.callables) == 3
        assert "adder" in debugger.callables
        assert "multiplier" in debugger.callables
        assert "liner" in debugger.callables

    def test_add_callable_duplicate_name_raises_error(self) -> None:
        """Test that adding a callable with a duplicate name raises ValueError."""
        debugger = Debugger()
        debugger.add_callable(adder)

        with pytest.raises(ValueError, match="Callable with name adder already exists"):
            debugger.add_callable(adder)

    def test_add_callable_duplicate_custom_name_raises_error(self) -> None:
        """Test that adding a callable with a duplicate custom name raises ValueError."""
        debugger = Debugger()
        debugger.add_callable(adder, name="my_func")

        with pytest.raises(
            ValueError, match="Callable with name my_func already exists"
        ):
            debugger.add_callable(multiplier, name="my_func")


# --- Tests for Debugger.list_callables ---


class TestDebuggerListCallables:
    @pytest.mark.asyncio
    async def test_list_callables_empty(self) -> None:
        """Test listing callables when none are registered."""
        debugger = Debugger()
        names = await debugger.list_callables()

        assert names == []

    @pytest.mark.asyncio
    async def test_list_callables_with_callables(self) -> None:
        """Test listing callables after adding some."""
        debugger = Debugger()
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)
        debugger.add_callable(liner)

        names = await debugger.list_callables()

        assert set(names) == {"adder", "multiplier", "liner"}


# --- Tests for Debugger.invoke_callable ---


class TestDebuggerInvokeCallable:
    @pytest.mark.asyncio
    async def test_invoke_returns_correct_result(self) -> None:
        """Test that invoking a callable returns the correct result."""
        debugger = Debugger()
        debugger.add_callable(adder)

        result = await debugger.invoke_callable("adder", {"a": 3.0, "b": 5.0})

        assert result == 8.0

    @pytest.mark.asyncio
    async def test_invoke_creates_call(self) -> None:
        """Test that invoking a callable creates a call record."""
        debugger = Debugger()
        debugger.add_callable(adder)

        await debugger.invoke_callable("adder", {"a": 2.0, "b": 3.0})

        calls = await debugger.get_calls("adder")
        assert len(calls) == 1

        call = calls[0]
        assert call.name == "adder"
        assert call.inputs == {"a": 2.0, "b": 3.0}
        assert call.output == 5.0
        assert call.error is None

    @pytest.mark.asyncio
    async def test_invoke_records_timing(self) -> None:
        """Test that calls record timing information."""
        debugger = Debugger()
        debugger.add_callable(adder)

        await debugger.invoke_callable("adder", {"a": 1.0, "b": 1.0})

        calls = await debugger.get_calls("adder")
        call = calls[0]

        assert call.start_time_unix_nano > 0
        assert call.end_time_unix_nano >= call.start_time_unix_nano

    @pytest.mark.asyncio
    async def test_multiple_invokes_create_multiple_calls(self) -> None:
        """Test that multiple invocations create multiple call records."""
        debugger = Debugger()
        debugger.add_callable(adder)

        await debugger.invoke_callable("adder", {"a": 1.0, "b": 2.0})
        await debugger.invoke_callable("adder", {"a": 3.0, "b": 4.0})
        await debugger.invoke_callable("adder", {"a": 5.0, "b": 6.0})

        calls = await debugger.get_calls("adder")
        assert len(calls) == 3

        assert calls[0].output == 3.0
        assert calls[1].output == 7.0
        assert calls[2].output == 11.0

    @pytest.mark.asyncio
    async def test_invoke_not_found_raises_error(self) -> None:
        """Test that invoking an unknown callable raises HTTPException."""
        debugger = Debugger()

        with pytest.raises(HTTPException) as exc_info:
            await debugger.invoke_callable("nonexistent", {})

        assert exc_info.value.status_code == 404
        assert "nonexistent" in exc_info.value.detail


# --- Tests for Debugger.get_calls ---


class TestDebuggerGetCalls:
    @pytest.mark.asyncio
    async def test_get_calls_empty(self) -> None:
        """Test getting calls when none have been made."""
        debugger = Debugger()
        debugger.add_callable(adder)

        calls = await debugger.get_calls("adder")
        assert calls == []

    @pytest.mark.asyncio
    async def test_get_calls_not_found_raises_error(self) -> None:
        """Test that getting calls for unknown callable raises HTTPException."""
        debugger = Debugger()

        with pytest.raises(HTTPException) as exc_info:
            await debugger.get_calls("nonexistent")

        assert exc_info.value.status_code == 404
        assert "nonexistent" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_calls_isolated_per_callable(self) -> None:
        """Test that calls are isolated per callable."""
        debugger = Debugger()
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)

        await debugger.invoke_callable("adder", {"a": 1.0, "b": 2.0})
        await debugger.invoke_callable("multiplier", {"a": 3.0, "b": 4.0})
        await debugger.invoke_callable("adder", {"a": 5.0, "b": 6.0})

        adder_calls = await debugger.get_calls("adder")
        multiplier_calls = await debugger.get_calls("multiplier")

        assert len(adder_calls) == 2
        assert len(multiplier_calls) == 1


# --- Tests for error handling ---


class TestDebuggerErrorHandling:
    @pytest.mark.asyncio
    async def test_invoke_with_error_records_call(self) -> None:
        """Test that errors are recorded in calls and re-raised."""
        debugger = Debugger()
        debugger.add_callable(failing_func)

        with pytest.raises(ValueError, match="Intentional test error"):
            await debugger.invoke_callable("failing_func", {})

        calls = await debugger.get_calls("failing_func")
        assert len(calls) == 1

        call = calls[0]
        assert call.error == "Intentional test error"
        assert call.output is None


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


# --- Tests for get_callable_input_json_schema ---


class TestGetCallableInputJsonSchema:
    def test_basic_types(self) -> None:
        """Test schema generation for basic Python types."""

        def func(a: int, b: str, c: float, d: bool) -> None:
            pass

        schema = get_callable_input_json_schema(func)

        assert schema["type"] == "object"
        assert schema["properties"]["a"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "string"
        assert schema["properties"]["c"]["type"] == "number"
        assert schema["properties"]["d"]["type"] == "boolean"
        assert set(schema["required"]) == {"a", "b", "c", "d"}

    def test_with_defaults(self) -> None:
        """Test that default values are captured in schema."""

        def func(a: int, b: str = "default", c: float = 3.14) -> None:
            pass

        schema = get_callable_input_json_schema(func)

        assert schema["required"] == ["a"]
        assert schema["properties"]["b"]["default"] == "default"
        assert schema["properties"]["c"]["default"] == 3.14

    def test_optional_types(self) -> None:
        """Test schema generation for Optional types (Pydantic uses anyOf)."""

        def func(a: int | None, b: str | None = None) -> None:
            pass

        schema = get_callable_input_json_schema(func)

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

        def func(a: list[int], b: list[str]) -> None:
            pass

        schema = get_callable_input_json_schema(func)

        assert schema["properties"]["a"]["type"] == "array"
        assert schema["properties"]["a"]["items"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "array"
        assert schema["properties"]["b"]["items"]["type"] == "string"

    def test_dict_types(self) -> None:
        """Test schema generation for dict types."""

        def func(a: dict[str, int]) -> None:
            pass

        schema = get_callable_input_json_schema(func)

        assert schema["properties"]["a"]["type"] == "object"
        assert schema["properties"]["a"]["additionalProperties"]["type"] == "integer"

    def test_no_annotations(self) -> None:
        """Test schema generation for functions without type annotations."""

        def func(a, b):
            pass

        schema = get_callable_input_json_schema(func)

        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]
        # No type info, so properties should be empty dicts
        assert schema["properties"]["a"] == {}
        assert schema["properties"]["b"] == {}

    def test_existing_functions(self) -> None:
        """Test schema generation for the existing test functions."""
        schema = get_callable_input_json_schema(adder)

        assert schema["type"] == "object"
        assert schema["properties"]["a"]["type"] == "number"
        assert schema["properties"]["b"]["type"] == "number"
        assert set(schema["required"]) == {"a", "b"}


# --- Tests for Debugger.get_json_schema ---


class TestDebuggerGetJsonSchema:
    @pytest.mark.asyncio
    async def test_get_json_schema(self) -> None:
        """Test getting JSON schema for a registered callable."""
        debugger = Debugger()
        debugger.add_callable(adder)

        schema = await debugger.get_json_schema("adder")

        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]

    @pytest.mark.asyncio
    async def test_get_json_schema_not_found(self) -> None:
        """Test that HTTPException is raised for unknown callable."""
        debugger = Debugger()

        with pytest.raises(HTTPException) as exc_info:
            await debugger.get_json_schema("nonexistent")

        assert exc_info.value.status_code == 404
        assert "nonexistent" in exc_info.value.detail


# --- Integration-style tests ---


class TestDebuggerIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self) -> None:
        """Test the complete workflow: add callable, invoke it, retrieve calls."""
        debugger = Debugger()

        # Add callables
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)

        # Verify registration
        names = await debugger.list_callables()
        assert set(names) == {"adder", "multiplier"}

        # Invoke callables
        result = await debugger.invoke_callable("adder", {"a": 10.0, "b": 5.0})
        assert result == 15.0

        result = await debugger.invoke_callable("multiplier", {"a": 3.0, "b": 7.0})
        assert result == 21.0

        # Verify calls
        adder_calls = await debugger.get_calls("adder")
        assert len(adder_calls) == 1
        assert adder_calls[0].inputs == {"a": 10.0, "b": 5.0}
        assert adder_calls[0].output == 15.0

        multiplier_calls = await debugger.get_calls("multiplier")
        assert len(multiplier_calls) == 1
        assert multiplier_calls[0].inputs == {"a": 3.0, "b": 7.0}
        assert multiplier_calls[0].output == 21.0

        # Verify schema
        schema = await debugger.get_json_schema("adder")
        assert schema["type"] == "object"
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]


# --- Tests for Weave integration ---


class TestDebuggerWeaveIntegration:
    """Tests for weave op integration with the debugger."""

    @pytest.mark.asyncio
    async def test_invoke_op_with_weave_initialized_stores_call_ref(
        self, client
    ) -> None:
        """Test that invoking a weave op with weave initialized stores the call ref."""

        @weave.op
        def weave_adder(a: float, b: float) -> float:
            """Add two numbers using weave op."""
            return a + b

        debugger = Debugger()
        debugger.add_callable(weave_adder)

        result = await debugger.invoke_callable("weave_adder", {"a": 3.0, "b": 5.0})

        assert result == 8.0

        calls = await debugger.get_calls("weave_adder")
        assert len(calls) == 1

        call = calls[0]
        assert call.name == "weave_adder"
        assert call.inputs == {"a": 3.0, "b": 5.0}
        assert call.output == 8.0
        assert call.error is None

        # The weave_call_ref should be populated since weave is initialized
        assert call.weave_call_ref is not None
        assert call.weave_call_ref.startswith("weave:///")
        assert "/call/" in call.weave_call_ref

    @pytest.mark.asyncio
    @pytest.mark.trace_server
    async def test_invoke_op_without_weave_initialized_has_no_call_ref(self) -> None:
        """Test that invoking a weave op without weave initialized has no call ref."""
        # Note: This test runs without the client fixture, so weave is not initialized

        @weave.op
        def weave_multiplier(a: float, b: float) -> float:
            """Multiply two numbers using weave op."""
            return a * b

        debugger = Debugger()
        debugger.add_callable(weave_multiplier)

        result = await debugger.invoke_callable(
            "weave_multiplier", {"a": 4.0, "b": 5.0}
        )

        assert result == 20.0

        calls = await debugger.get_calls("weave_multiplier")
        assert len(calls) == 1

        call = calls[0]
        assert call.output == 20.0
        # weave_call_ref should be None since weave is not initialized
        assert call.weave_call_ref is None

    @pytest.mark.asyncio
    async def test_invoke_regular_function_with_weave_initialized_has_no_call_ref(
        self, client
    ) -> None:
        """Test that invoking a regular function (not an op) has no call ref even with weave initialized."""

        def regular_function(a: float, b: float) -> float:
            """A regular function, not a weave op."""
            return a - b

        debugger = Debugger()
        debugger.add_callable(regular_function)

        result = await debugger.invoke_callable(
            "regular_function", {"a": 10.0, "b": 3.0}
        )

        assert result == 7.0

        calls = await debugger.get_calls("regular_function")
        assert len(calls) == 1

        call = calls[0]
        assert call.output == 7.0
        # weave_call_ref should be None since it's not a weave op
        assert call.weave_call_ref is None

    @pytest.mark.asyncio
    async def test_invoke_op_with_error_still_stores_span(self, client) -> None:
        """Test that errors during op invocation are properly recorded."""

        @weave.op
        def failing_weave_op(x: int) -> int:
            """A weave op that always fails."""
            raise ValueError("Intentional op error")

        debugger = Debugger()
        debugger.add_callable(failing_weave_op)

        # op.call() captures errors in the Call object rather than raising,
        # so the debugger re-raises as a generic Exception with the error message
        with pytest.raises(Exception, match="Intentional op error"):
            await debugger.invoke_callable("failing_weave_op", {"x": 42})

        calls = await debugger.get_calls("failing_weave_op")
        assert len(calls) == 1

        call = calls[0]
        assert "Intentional op error" in call.error
        assert call.output is None
        # Even on error, we should have a weave_call_ref since op.call() completes
        assert call.weave_call_ref is not None
        assert call.weave_call_ref.startswith("weave:///")

    @pytest.mark.asyncio
    async def test_multiple_op_invocations_each_have_unique_refs(self, client) -> None:
        """Test that multiple invocations of the same op get unique call refs."""

        @weave.op
        def counter_op(n: int) -> int:
            """Return the input number."""
            return n

        debugger = Debugger()
        debugger.add_callable(counter_op)

        await debugger.invoke_callable("counter_op", {"n": 1})
        await debugger.invoke_callable("counter_op", {"n": 2})
        await debugger.invoke_callable("counter_op", {"n": 3})

        calls = await debugger.get_calls("counter_op")
        assert len(calls) == 3

        # Each call should have a unique weave_call_ref
        refs = [call.weave_call_ref for call in calls]
        assert all(ref is not None for ref in refs)
        assert len(set(refs)) == 3  # All refs should be unique

    @pytest.mark.asyncio
    @pytest.mark.trace_server
    async def test_span_model_includes_weave_call_ref(self) -> None:
        """Test that the Span model properly handles weave_call_ref field."""
        span_with_ref = Span(
            name="test",
            start_time_unix_nano=1000.0,
            end_time_unix_nano=2000.0,
            inputs={"a": 1},
            output=42,
            error=None,
            weave_call_ref="weave:///entity/project/call/abc123",
        )

        assert span_with_ref.weave_call_ref == "weave:///entity/project/call/abc123"

        span_without_ref = Span(
            name="test",
            start_time_unix_nano=1000.0,
            end_time_unix_nano=2000.0,
            inputs={"a": 1},
            output=42,
            error=None,
        )

        assert span_without_ref.weave_call_ref is None
