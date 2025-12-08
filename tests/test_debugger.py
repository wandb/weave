"""Tests for the weave.trace.debugger.debug module."""

import pytest

from weave.trace.debugger.debug import (
    Debugger,
    Span,
    derive_callable_name,
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


# --- Tests for Debugger.get_callable_names ---


class TestDebuggerGetCallableNames:
    @pytest.mark.asyncio
    async def test_get_callable_names_empty(self) -> None:
        """Test getting callable names when no callables are registered."""
        debugger = Debugger()
        names = await debugger.get_callable_names()

        assert names == []

    @pytest.mark.asyncio
    async def test_get_callable_names_with_callables(self) -> None:
        """Test getting callable names after adding callables."""
        debugger = Debugger()
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)
        debugger.add_callable(liner)

        names = await debugger.get_callable_names()

        assert set(names) == {"adder", "multiplier", "liner"}


# --- Tests for Debugger.make_call_fn ---


class TestDebuggerMakeCallFn:
    @pytest.mark.asyncio
    async def test_call_function_returns_correct_result(self) -> None:
        """Test that calling a function through make_call_fn returns correct result."""
        debugger = Debugger()
        debugger.add_callable(adder)

        call_fn = debugger.make_call_fn("adder")
        result = await call_fn(3.0, 5.0)

        assert result == 8.0

    @pytest.mark.asyncio
    async def test_call_function_with_kwargs(self) -> None:
        """Test calling a function with keyword arguments."""
        debugger = Debugger()
        debugger.add_callable(adder)

        call_fn = debugger.make_call_fn("adder")
        result = await call_fn(a=10.0, b=20.0)

        assert result == 30.0

    @pytest.mark.asyncio
    async def test_call_function_creates_span(self) -> None:
        """Test that calling a function creates a span."""
        debugger = Debugger()
        debugger.add_callable(adder)

        call_fn = debugger.make_call_fn("adder")
        await call_fn(2.0, 3.0)

        spans = await debugger.get_spans("adder")
        assert len(spans) == 1

        span = spans[0]
        assert span.name == "adder"
        assert span.inputs == {"a": 2.0, "b": 3.0}
        assert span.output == 5.0
        assert span.error is None

    @pytest.mark.asyncio
    async def test_call_function_records_timing(self) -> None:
        """Test that spans record timing information."""
        debugger = Debugger()
        debugger.add_callable(adder)

        call_fn = debugger.make_call_fn("adder")
        await call_fn(1.0, 1.0)

        spans = await debugger.get_spans("adder")
        span = spans[0]

        assert span.start_time_unix_nano > 0
        assert span.end_time_unix_nano >= span.start_time_unix_nano

    @pytest.mark.asyncio
    async def test_multiple_calls_create_multiple_spans(self) -> None:
        """Test that multiple calls create multiple spans."""
        debugger = Debugger()
        debugger.add_callable(adder)

        call_fn = debugger.make_call_fn("adder")
        await call_fn(1.0, 2.0)
        await call_fn(3.0, 4.0)
        await call_fn(5.0, 6.0)

        spans = await debugger.get_spans("adder")
        assert len(spans) == 3

        assert spans[0].output == 3.0
        assert spans[1].output == 7.0
        assert spans[2].output == 11.0


# --- Tests for Debugger.get_spans ---


class TestDebuggerGetSpans:
    @pytest.mark.asyncio
    async def test_get_spans_empty(self) -> None:
        """Test getting spans when no calls have been made."""
        debugger = Debugger()
        debugger.add_callable(adder)

        spans = await debugger.get_spans("adder")
        assert spans == []

    @pytest.mark.asyncio
    async def test_get_spans_nonexistent_name(self) -> None:
        """Test getting spans for a name that was never registered."""
        debugger = Debugger()

        spans = await debugger.get_spans("nonexistent")
        assert spans == []

    @pytest.mark.asyncio
    async def test_spans_isolated_per_callable(self) -> None:
        """Test that spans are isolated per callable name."""
        debugger = Debugger()
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)

        adder_fn = debugger.make_call_fn("adder")
        multiplier_fn = debugger.make_call_fn("multiplier")

        await adder_fn(1.0, 2.0)
        await multiplier_fn(3.0, 4.0)
        await adder_fn(5.0, 6.0)

        adder_spans = await debugger.get_spans("adder")
        multiplier_spans = await debugger.get_spans("multiplier")

        assert len(adder_spans) == 2
        assert len(multiplier_spans) == 1


# --- Tests for error handling ---


class TestDebuggerErrorHandling:
    @pytest.mark.asyncio
    async def test_call_function_with_error_records_span(self) -> None:
        """Test that errors are recorded in spans and re-raised."""
        debugger = Debugger()
        debugger.add_callable(failing_func)

        call_fn = debugger.make_call_fn("failing_func")

        with pytest.raises(ValueError, match="Intentional test error"):
            await call_fn()

        spans = await debugger.get_spans("failing_func")
        assert len(spans) == 1

        span = spans[0]
        assert span.error == "Intentional test error"
        assert span.output is None


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


# --- Integration-style tests ---


class TestDebuggerIntegration:
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self) -> None:
        """Test the complete workflow: add callable, call it, retrieve spans."""
        debugger = Debugger()

        # Add callables
        debugger.add_callable(adder)
        debugger.add_callable(multiplier)

        # Verify registration
        names = await debugger.get_callable_names()
        assert set(names) == {"adder", "multiplier"}

        # Make calls
        adder_fn = debugger.make_call_fn("adder")
        result = await adder_fn(10.0, 5.0)
        assert result == 15.0

        multiplier_fn = debugger.make_call_fn("multiplier")
        result = await multiplier_fn(3.0, 7.0)
        assert result == 21.0

        # Verify spans
        adder_spans = await debugger.get_spans("adder")
        assert len(adder_spans) == 1
        assert adder_spans[0].inputs == {"a": 10.0, "b": 5.0}
        assert adder_spans[0].output == 15.0

        multiplier_spans = await debugger.get_spans("multiplier")
        assert len(multiplier_spans) == 1
        assert multiplier_spans[0].inputs == {"a": 3.0, "b": 7.0}
        assert multiplier_spans[0].output == 21.0
