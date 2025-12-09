"""Tests for the weave.trace.debugger.debug module."""

import pytest

import weave
from weave.trace.debugger.debug import (
    CallableInfo,
    Debugger,
    DebuggerServer,
    _derive_callable_name,
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


# --- Tests for error handling ---


class TestDebuggerErrorHandling:
    @pytest.mark.trace_server
    def test_invoke_with_error_raises_exception(self, client) -> None:
        """Test that errors are raised when callable fails."""
        debugger = Debugger()
        ref = debugger.add_callable(failing_func)

        with pytest.raises(Exception, match="Intentional test error"):
            debugger.invoke_callable(ref, {})


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

        # Calls are stored in weave and can be queried via the trace server
        # using the op ref. The debugger no longer provides a get_calls method.

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

    @pytest.mark.trace_server
    def test_multiple_invocations(self, client) -> None:
        """Test that multiple invocations work correctly."""

        @weave.op
        def counter_op(n: int) -> int:
            """Return the input number."""
            return n

        debugger = Debugger()
        ref = debugger.add_callable(counter_op)

        r1 = debugger.invoke_callable(ref, {"n": 1})
        r2 = debugger.invoke_callable(ref, {"n": 2})
        r3 = debugger.invoke_callable(ref, {"n": 3})

        assert r1 == 1
        assert r2 == 2
        assert r3 == 3


# --- Integration-style tests ---


class TestDebuggerIntegration:
    @pytest.mark.trace_server
    def test_end_to_end_workflow(self, client) -> None:
        """Test the complete workflow: add callable, invoke it."""
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

        # Calls and schemas are available via weave trace server using the ref
