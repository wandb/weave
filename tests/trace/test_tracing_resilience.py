"""The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.
"""

from __future__ import annotations

from collections import Counter
from unittest.mock import patch

import pytest

import weave
import weave.trace.serialization.op_type
from tests.trace.util import DummyTestException
from weave.trace.context import call_context
from weave.trace.context.tests_context import raise_on_captured_errors
from weave.trace.op import _add_accumulator


def assert_no_current_call():
    assert call_context.get_current_call() is None


def reset_call_context():
    """Force reset the call context to an empty stack."""
    token = call_context._call_stack.set([])
    call_context._call_stack.reset(token)


def test_resilience_to_user_code_errors(client):
    def do_test():
        @weave.op
        def throws():
            raise DummyTestException("This is a test exception")

        throws()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # The user's exception should be raised - even if we're not capturing errors
    with pytest.raises(DummyTestException):
        do_test()

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_server_errors(client_with_throwing_server, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            return "hello"

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # We should gracefully handle the error and return a value
    res = do_test()
    assert res == "hello"

    assert_no_current_call()
    client_with_throwing_server.flush()

    logs = log_collector.get_error_logs()
    ag_res = Counter([k.split(", req:")[0] for k in {l.msg for l in logs}])
    # Tim: This is very specific and intentional, please don't change
    # this unless you are sure that is the expected behavior
    assert ag_res == {
        "Task failed: DummyTestException: ('FAILURE - call_end": 1,
        "Task failed: DummyTestException: ('FAILURE - file_create": 1,
        "Task failed: DummyTestException: ('FAILURE - obj_create": 1,
    }


@pytest.mark.disable_logging_error_check
def test_resilience_to_output_handler_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            return "hello"

        def on_output_handler(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        simple_op._set_on_output_handler(on_output_handler)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # We should gracefully handle the error and return a value
    res = do_test()
    assert res == "hello"

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_output_handler_errors_async(client, log_collector):
    async def do_test():
        @weave.op
        async def simple_op():
            return "hello"

        def on_output_handler(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        simple_op._set_on_output_handler(on_output_handler)

        return await simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert res == "hello"

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_make_accumulator_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        _add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            # Consume the generator to trigger the make_accumulator call
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_make_accumulator_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        _add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            # Consume the generator to trigger the make_accumulator call
            res = await do_test()
            l = [item async for item in res]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_accumulation_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                raise DummyTestException("FAILURE!")

            return accumulate

        _add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith(
        "Error capturing value from iterator, call data may be incomplete"
    )


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_accumulation_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                raise DummyTestException("FAILURE!")

            return accumulate

        _add_accumulator(simple_op, make_accumulator=make_accumulator)

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            res = await do_test()
            l = [item async for item in res]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith(
        "Error capturing async value from iterator, call data may be incomplete"
    )


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_should_accumulate_errors(client, log_collector):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def should_accumulate(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        _add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            should_accumulate=should_accumulate,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_should_accumulate_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def should_accumulate(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        _add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            should_accumulate=should_accumulate,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            # Consume the generator
            gen = await do_test()
            _ = [i async for i in gen]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


# Here we are ignoring this warning because the exception IS being raised,
# and that is expected and tested for. It happens to be at the deletion moment
# so pytest is complaining that the exception is not being raised in the
# expected manner.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_on_finish_post_processor_errors(
    client, log_collector
):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def on_finish_post_processor(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        _add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            on_finish_post_processor=on_finish_post_processor,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            # Consume the generator to trigger the make_accumulator call
            list(do_test())

    # We should gracefully handle the error and return a value
    res = do_test()
    assert list(res) == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) > 0
    for log in logs:
        assert log.msg.startswith("Error capturing call output")


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_accumulator_on_finish_post_processor_errors_async(
    client, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        def make_accumulator(*args, **kwargs):
            def accumulate(*args, **kwargs):
                return {}

            return accumulate

        def on_finish_post_processor(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        _add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            on_finish_post_processor=on_finish_post_processor,
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            # Consume the generator to trigger the make_accumulator call
            res = await do_test()
            l = [item async for item in res]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) > 0
    for log in logs:
        assert log.msg.startswith("Error capturing call output")


def test_resilience_to_accumulator_internal_errors(client):
    def do_test():
        @weave.op(accumulator=lambda *args, **kwargs: {})
        def simple_op():
            yield 1
            raise DummyTestException("FAILURE!")

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            list(do_test())

    # User errors should still be raised
    with pytest.raises(DummyTestException):
        list(do_test())

    assert_no_current_call()


@pytest.mark.asyncio
async def test_resilience_to_accumulator_internal_errors_async(client):
    async def do_test():
        @weave.op(accumulator=lambda *args, **kwargs: {})
        async def simple_op():
            yield 1
            raise DummyTestException("FAILURE!")

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            res = await do_test()
            l = [item async for item in res]

    with raise_on_captured_errors(False):
        with pytest.raises(DummyTestException):
            res = await do_test()
            l = [item async for item in res]


# =============================================================================
# Tests for postprocess_inputs/output and handler resilience
# =============================================================================


def _bad_postprocess_inputs(inputs):
    raise DummyTestException("FAILURE in postprocess_inputs!")


def _bad_postprocess_output(output):
    raise DummyTestException("FAILURE in postprocess_output!")


def _bad_display_name(call):
    raise DummyTestException("FAILURE in call_display_name!")


def _bad_input_handler(op, args, kwargs):
    raise DummyTestException("FAILURE in on_input_handler!")


def _bad_finish_handler(call, output, exception):
    raise DummyTestException("FAILURE in on_finish_handler!")


@pytest.mark.disable_logging_error_check
def test_resilience_to_postprocess_inputs_errors(client, log_collector):
    """Test that errors in postprocess_inputs don't crash the user's program."""

    @weave.op(postprocess_inputs=_bad_postprocess_inputs)
    def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            simple_op()

    res = simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_postprocess_inputs_errors_async(client, log_collector):
    """Test that errors in postprocess_inputs don't crash async ops."""

    @weave.op(postprocess_inputs=_bad_postprocess_inputs)
    async def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_postprocess_output_errors(client, log_collector):
    """Test that errors in postprocess_output don't crash the user's program."""

    @weave.op(postprocess_output=_bad_postprocess_output)
    def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            simple_op()

    res = simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_postprocess_output_errors_async(client, log_collector):
    """Test that errors in postprocess_output don't crash async ops."""

    @weave.op(postprocess_output=_bad_postprocess_output)
    async def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_call_display_name_errors(client, log_collector):
    """Test that errors in call_display_name callable don't crash the user's program."""

    @weave.op(call_display_name=_bad_display_name)
    def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            simple_op()

    res = simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_call_display_name_errors_async(client, log_collector):
    """Test that errors in call_display_name callable don't crash async ops."""

    @weave.op(call_display_name=_bad_display_name)
    async def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_on_input_handler_errors(client, log_collector):
    """Test that errors in _on_input_handler don't crash the user's program."""

    @weave.op
    def simple_op():
        return "hello"

    simple_op._set_on_input_handler(_bad_input_handler)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            simple_op()

    res = simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_on_input_handler_errors_async(client, log_collector):
    """Test that errors in _on_input_handler don't crash async ops."""

    @weave.op
    async def simple_op():
        return "hello"

    simple_op._set_on_input_handler(_bad_input_handler)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_on_finish_handler_errors(client, log_collector):
    """Test that errors in _on_finish_handler don't crash the user's program."""

    @weave.op
    def simple_op():
        return "hello"

    simple_op._set_on_finish_handler(_bad_finish_handler)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            simple_op()

    res = simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_on_finish_handler_errors_async(client, log_collector):
    """Test that errors in _on_finish_handler don't crash async ops."""

    @weave.op
    async def simple_op():
        return "hello"

    simple_op._set_on_finish_handler(_bad_finish_handler)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


# =============================================================================
# Tests for code capture resilience
#
# Key invariant: code capture failures must NEVER break the user's op execution.
#
# Code capture (serialization of op source code) happens inside a deferred
# background executor (_save_object_basic → future_executor.defer). This means
# serialization errors do NOT propagate synchronously to the op caller. Instead,
# they are logged and the op returns its result normally.
#
# These tests verify that:
#   1. Ops return correct values when code capture internals fail
#   2. No exceptions leak to the user from code capture failures
#   3. Various code capture edge cases (closures, lambdas, disabled) work
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_to_getsource_failure(client, log_collector):
    """Op returns correct value when inspect.getsource() raises OSError.

    Simulates dynamically generated functions or C extensions where source
    is unavailable. Serialization is deferred so errors don't reach the caller.
    """

    def do_test():
        @weave.op
        def simple_op(x: int) -> int:
            return x + 1

        return simple_op(1)

    with patch(
        "weave.trace.serialization.op_type.get_source_notebook_safe",
        side_effect=OSError("could not get source code"),
    ):
        res = do_test()
        assert res == 2

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_getsource_failure_async(client, log_collector):
    """Async op returns correct value when getsource fails."""

    async def do_test():
        @weave.op
        async def simple_op(x: int) -> int:
            return x + 1

        return await simple_op(1)

    with patch(
        "weave.trace.serialization.op_type.get_source_notebook_safe",
        side_effect=OSError("could not get source code"),
    ):
        res = await do_test()
        assert res == 2

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_ast_parse_failure(client, log_collector):
    """Op returns correct value when AST parsing of source code fails."""

    def do_test():
        @weave.op
        def simple_op() -> str:
            return "hello"

        return simple_op()

    with patch(
        "weave.trace.serialization.op_type.ast.parse",
        side_effect=SyntaxError("invalid syntax"),
    ):
        res = do_test()
        assert res == "hello"

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_code_deps_exception(client, log_collector):
    """Op returns correct value when get_code_deps_safe raises."""

    def do_test():
        @weave.op
        def simple_op() -> str:
            return "hello"

        return simple_op()

    with patch(
        "weave.trace.serialization.op_type.get_code_deps_safe",
        side_effect=RuntimeError("unexpected serialization failure"),
    ):
        res = do_test()
        assert res == "hello"

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_save_instance_exception(client, log_collector):
    """Op returns correct value when save_instance completely fails."""

    def do_test():
        @weave.op
        def simple_op(a: int, b: int) -> int:
            return a + b

        return simple_op(2, 3)

    with patch(
        "weave.trace.serialization.op_type.save_instance",
        side_effect=Exception("total save failure"),
    ):
        res = do_test()
        assert res == 5

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_save_instance_exception_async(client, log_collector):
    """Async op returns correct value when save_instance completely fails."""

    async def do_test():
        @weave.op
        async def simple_op(a: int, b: int) -> int:
            return a + b

        return await simple_op(2, 3)

    with patch(
        "weave.trace.serialization.op_type.save_instance",
        side_effect=Exception("total save failure"),
    ):
        res = await do_test()
        assert res == 5

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_signature_reconstruction_failure(client, log_collector):
    """Op returns correct value when getsource and reconstruct_signature both fail."""

    def do_test():
        @weave.op
        def simple_op() -> str:
            return "works"

        return simple_op()

    with (
        patch(
            "weave.trace.serialization.op_type.get_source_notebook_safe",
            side_effect=OSError("no source"),
        ),
        patch(
            "weave.trace.serialization.op_type.reconstruct_signature",
            side_effect=TypeError("cannot reconstruct"),
        ),
    ):
        res = do_test()
        assert res == "works"

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_code_capture_with_generator(client, log_collector):
    """Generator op yields correct values when code capture fails."""

    def do_test():
        @weave.op
        def gen_op():
            yield from [1, 2, 3]

        return list(gen_op())

    with patch(
        "weave.trace.serialization.op_type.get_code_deps_safe",
        side_effect=RuntimeError("code capture broken"),
    ):
        res = do_test()
        assert res == [1, 2, 3]

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_code_capture_with_async_generator(client, log_collector):
    """Async generator op yields correct values when code capture fails."""

    async def do_test():
        @weave.op
        async def async_gen_op():
            yield 1
            yield 2
            yield 3

        return [item async for item in async_gen_op()]

    with patch(
        "weave.trace.serialization.op_type.get_code_deps_safe",
        side_effect=RuntimeError("code capture broken"),
    ):
        res = await do_test()
        assert res == [1, 2, 3]

    assert_no_current_call()


def test_code_capture_disabled_does_not_crash(client):
    """Disabling code capture per-op doesn't crash."""

    @weave.op(enable_code_capture=False)
    def simple_op() -> str:
        return "no code captured"

    res = simple_op()
    assert res == "no code captured"
    assert_no_current_call()


def test_code_capture_disabled_globally_does_not_crash(client):
    """Disabling code capture globally doesn't crash."""

    def do_test():
        @weave.op
        def simple_op() -> str:
            return "globally disabled"

        return simple_op()

    with patch(
        "weave.trace.serialization.op_type.settings.should_capture_code",
        return_value=False,
    ):
        res = do_test()
        assert res == "globally disabled"

    assert_no_current_call()


def test_code_capture_with_closure_variables(client):
    """Code capture works for ops that reference closure variables."""
    multiplier = 10

    @weave.op
    def multiply(x: int) -> int:
        return x * multiplier

    res = multiply(5)
    assert res == 50
    assert_no_current_call()


def test_code_capture_with_lambda_op(client):
    """Code capture works for lambda-based ops."""
    my_op = weave.op()(lambda x: x * 2)
    res = my_op(5)
    assert res == 10
    assert_no_current_call()


def test_code_capture_with_programmatic_op(client):
    """Code capture works for programmatically created ops (no decorator in source)."""

    def plain_function(x: int) -> int:
        return x + 100

    my_op = weave.op()(plain_function)
    res = my_op(5)
    assert res == 105
    assert_no_current_call()


@pytest.mark.asyncio
async def test_code_capture_with_async_programmatic_op(client):
    """Code capture works for async programmatically created ops."""

    async def plain_async(x: int) -> int:
        return x + 200

    my_op = weave.op()(plain_async)
    res = await my_op(5)
    assert res == 205
    assert_no_current_call()


def test_code_capture_with_nested_op_calls(client):
    """Code capture works with nested op calls (op calling another op)."""

    @weave.op
    def inner_op(x: int) -> int:
        return x * 2

    @weave.op
    def outer_op(x: int) -> int:
        return inner_op(x) + 1

    res = outer_op(5)
    assert res == 11
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_code_capture_failure_preserves_nested_calls(client, log_collector):
    """Nested op calls still work when code capture fails for the outer op."""

    def do_test():
        @weave.op
        def inner_op(x: int) -> int:
            return x * 2

        @weave.op
        def outer_op(x: int) -> int:
            return inner_op(x) + 1

        return outer_op(5)

    call_count = 0
    original_save = weave.trace.serialization.op_type.save_instance

    def failing_save_for_outer(obj, artifact, name):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("outer code capture failed")
        return original_save(obj, artifact, name)

    with patch(
        "weave.trace.serialization.op_type.save_instance",
        side_effect=failing_save_for_outer,
    ):
        res = do_test()
        assert res == 11

    assert_no_current_call()
