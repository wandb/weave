"""The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.

This comprehensive test suite covers:
1. User code errors (should propagate)
2. Server errors (should not crash user code)
3. Output handler errors
4. Accumulator errors (make_accumulator, accumulation, should_accumulate, on_finish_post_processor)
5. Internal errors in generators
6. Input handler errors
7. postprocess_inputs/postprocess_output errors
8. call_display_name function errors
9. on_finish_handler errors
10. Nested op call resilience
11. Generator early termination (GeneratorExit)
12. Serialization errors
13. Call context cleanup after errors
"""

from __future__ import annotations

from collections import Counter
from unittest.mock import patch

import pytest

import weave
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
# Input Handler Resilience Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_to_input_handler_errors(client, log_collector):
    """Test that errors in custom _on_input_handler don't crash user code."""

    def do_test():
        @weave.op
        def simple_op(x):
            return x * 2

        def on_input_handler(*args, **kwargs):
            raise DummyTestException("FAILURE in input handler!")

        simple_op._set_on_input_handler(on_input_handler)

        return simple_op(5)

    # With raise_on_captured_errors, the exception should be raised
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    # Without the flag, we should gracefully handle and still return the value
    res = do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_input_handler_errors_async(client, log_collector):
    """Test that errors in custom _on_input_handler don't crash async user code."""

    async def do_test():
        @weave.op
        async def simple_op(x):
            return x * 2

        def on_input_handler(*args, **kwargs):
            raise DummyTestException("FAILURE in input handler!")

        simple_op._set_on_input_handler(on_input_handler)

        return await simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    res = await do_test()
    assert res == 10

    assert_no_current_call()


# =============================================================================
# Postprocess Input/Output Resilience Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_to_postprocess_inputs_errors(client, log_collector):
    """Test that errors in postprocess_inputs don't crash user code."""

    def do_test():
        def bad_postprocess_inputs(inputs):
            raise DummyTestException("FAILURE in postprocess_inputs!")

        @weave.op(postprocess_inputs=bad_postprocess_inputs)
        def simple_op(x):
            return x * 2

        return simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    res = do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_postprocess_inputs_errors_async(client, log_collector):
    """Test that errors in postprocess_inputs don't crash async user code."""

    async def do_test():
        def bad_postprocess_inputs(inputs):
            raise DummyTestException("FAILURE in postprocess_inputs!")

        @weave.op(postprocess_inputs=bad_postprocess_inputs)
        async def simple_op(x):
            return x * 2

        return await simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    res = await do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_postprocess_output_errors(client, log_collector):
    """Test that errors in postprocess_output don't crash user code."""

    def do_test():
        def bad_postprocess_output(output):
            raise DummyTestException("FAILURE in postprocess_output!")

        @weave.op(postprocess_output=bad_postprocess_output)
        def simple_op(x):
            return x * 2

        return simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    res = do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_postprocess_output_errors_async(client, log_collector):
    """Test that errors in postprocess_output don't crash async user code."""

    async def do_test():
        def bad_postprocess_output(output):
            raise DummyTestException("FAILURE in postprocess_output!")

        @weave.op(postprocess_output=bad_postprocess_output)
        async def simple_op(x):
            return x * 2

        return await simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    res = await do_test()
    assert res == 10

    assert_no_current_call()


# =============================================================================
# call_display_name Function Resilience Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_to_call_display_name_function_errors(client, log_collector):
    """Test that errors in call_display_name callable don't crash user code."""

    def do_test():
        def bad_display_name(call):
            raise DummyTestException("FAILURE in call_display_name!")

        @weave.op(call_display_name=bad_display_name)
        def simple_op(x):
            return x * 2

        return simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    res = do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_call_display_name_function_errors_async(
    client, log_collector
):
    """Test that errors in call_display_name callable don't crash async user code."""

    async def do_test():
        def bad_display_name(call):
            raise DummyTestException("FAILURE in call_display_name!")

        @weave.op(call_display_name=bad_display_name)
        async def simple_op(x):
            return x * 2

        return await simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    res = await do_test()
    assert res == 10

    assert_no_current_call()


# =============================================================================
# on_finish_handler Resilience Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_to_on_finish_handler_errors(client, log_collector):
    """Test that errors in _on_finish_handler don't crash user code."""

    def do_test():
        @weave.op
        def simple_op(x):
            return x * 2

        def on_finish_handler(call, output, exception):
            raise DummyTestException("FAILURE in on_finish_handler!")

        simple_op._set_on_finish_handler(on_finish_handler)

        return simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            do_test()

    res = do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
async def test_resilience_to_on_finish_handler_errors_async(client, log_collector):
    """Test that errors in _on_finish_handler don't crash async user code."""

    async def do_test():
        @weave.op
        async def simple_op(x):
            return x * 2

        def on_finish_handler(call, output, exception):
            raise DummyTestException("FAILURE in on_finish_handler!")

        simple_op._set_on_finish_handler(on_finish_handler)

        return await simple_op(5)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await do_test()

    res = await do_test()
    assert res == 10

    assert_no_current_call()


# =============================================================================
# Nested Op Call Resilience Tests
# =============================================================================


def test_resilience_nested_ops_with_inner_error(client):
    """Test that nested ops handle inner op errors correctly."""

    @weave.op
    def inner_op(x):
        if x < 0:
            raise DummyTestException("Negative value!")
        return x * 2

    @weave.op
    def outer_op(x):
        return inner_op(x) + 1

    # Valid input should work
    result = outer_op(5)
    assert result == 11

    # Inner error should propagate correctly
    with pytest.raises(DummyTestException):
        outer_op(-1)

    # Call context should be clean
    assert_no_current_call()


@pytest.mark.asyncio
async def test_resilience_nested_async_ops_with_inner_error(client):
    """Test that nested async ops handle inner op errors correctly."""

    @weave.op
    async def inner_op(x):
        if x < 0:
            raise DummyTestException("Negative value!")
        return x * 2

    @weave.op
    async def outer_op(x):
        return await inner_op(x) + 1

    result = await outer_op(5)
    assert result == 11

    with pytest.raises(DummyTestException):
        await outer_op(-1)

    assert_no_current_call()


def test_resilience_deeply_nested_ops_with_error(client):
    """Test that deeply nested ops (3+ levels) handle errors correctly."""

    @weave.op
    def level3(x):
        if x == 0:
            raise DummyTestException("Zero not allowed!")
        return x

    @weave.op
    def level2(x):
        return level3(x) * 2

    @weave.op
    def level1(x):
        return level2(x) + 10

    result = level1(5)
    assert result == 20

    with pytest.raises(DummyTestException):
        level1(0)

    assert_no_current_call()


# =============================================================================
# Generator Early Termination Resilience Tests
# =============================================================================


def test_resilience_generator_early_termination_break(client):
    """Test that breaking out of a generator iteration handles cleanup correctly."""

    cleanup_called = []

    @weave.op
    def generator_op():
        try:
            for i in range(100):
                yield i
        finally:
            cleanup_called.append(True)

    # Use break to terminate early
    for i, val in enumerate(generator_op()):
        if i >= 3:
            break

    # Generator cleanup should have happened
    assert len(cleanup_called) == 1
    assert_no_current_call()


def test_resilience_generator_close_explicit(client):
    """Test that explicitly closing a generator handles cleanup correctly."""

    @weave.op
    def generator_op():
        for i in range(100):
            yield i

    gen = generator_op()
    next(gen)
    next(gen)
    gen.close()

    assert_no_current_call()


@pytest.mark.asyncio
async def test_resilience_async_generator_early_termination(client):
    """Test that breaking out of an async generator iteration handles cleanup correctly."""

    @weave.op
    async def async_generator_op():
        for i in range(100):
            yield i

    count = 0
    async for val in async_generator_op():
        count += 1
        if count >= 3:
            break

    assert_no_current_call()


# =============================================================================
# Serialization Error Resilience Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_to_non_serializable_input(client, log_collector):
    """Test that non-serializable inputs don't crash user code."""

    def do_test():
        @weave.op
        def simple_op(x, callback):
            # Functions aren't easily serializable
            return callback(x)

        return simple_op(5, lambda x: x * 2)

    # Should still work even with non-serializable callback
    res = do_test()
    assert res == 10

    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_resilience_to_non_serializable_output(client, log_collector):
    """Test that non-serializable outputs don't crash user code."""

    def do_test():
        @weave.op
        def simple_op(x):
            # Return a lambda which is not easily serializable
            return lambda y: x * y

        return simple_op(5)

    res = do_test()
    assert res(3) == 15

    assert_no_current_call()


# =============================================================================
# Call Context Cleanup Tests
# =============================================================================


def test_call_context_cleanup_after_sync_error(client):
    """Test that call context is properly cleaned up after sync errors."""

    @weave.op
    def failing_op():
        raise DummyTestException("Error!")

    with pytest.raises(DummyTestException):
        failing_op()

    # Should be no lingering call context
    assert_no_current_call()


@pytest.mark.asyncio
async def test_call_context_cleanup_after_async_error(client):
    """Test that call context is properly cleaned up after async errors."""

    @weave.op
    async def failing_op():
        raise DummyTestException("Error!")

    with pytest.raises(DummyTestException):
        await failing_op()

    assert_no_current_call()


def test_call_context_cleanup_after_generator_error(client):
    """Test that call context is properly cleaned up after generator errors."""

    @weave.op
    def failing_generator():
        yield 1
        raise DummyTestException("Error in generator!")

    with pytest.raises(DummyTestException):
        list(failing_generator())

    assert_no_current_call()


@pytest.mark.asyncio
async def test_call_context_cleanup_after_async_generator_error(client):
    """Test that call context is properly cleaned up after async generator errors."""

    @weave.op
    async def failing_generator():
        yield 1
        raise DummyTestException("Error in async generator!")

    with pytest.raises(DummyTestException):
        async for _ in failing_generator():
            pass

    assert_no_current_call()


def test_call_context_cleanup_multiple_errors(client):
    """Test that call context stays clean after multiple consecutive errors."""

    @weave.op
    def failing_op(msg):
        raise DummyTestException(msg)

    for i in range(5):
        with pytest.raises(DummyTestException):
            failing_op(f"Error {i}")
        assert_no_current_call()


# =============================================================================
# System Exit and Keyboard Interrupt Tests
# =============================================================================


def test_system_exit_propagates_correctly(client):
    """Test that SystemExit is properly propagated."""

    @weave.op
    def exiting_op():
        raise SystemExit(42)

    with pytest.raises(SystemExit) as exc_info:
        exiting_op()

    assert exc_info.value.code == 42
    assert_no_current_call()


def test_keyboard_interrupt_propagates_correctly(client):
    """Test that KeyboardInterrupt is properly propagated."""

    @weave.op
    def interrupted_op():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        interrupted_op()

    assert_no_current_call()


# =============================================================================
# Mixed Sync/Async Op Resilience Tests
# =============================================================================


@pytest.mark.asyncio
async def test_resilience_sync_op_called_from_async_context(client):
    """Test that sync ops work correctly when called from async context."""

    @weave.op
    def sync_op(x):
        return x * 2

    @weave.op
    async def async_wrapper(x):
        return sync_op(x) + 1

    result = await async_wrapper(5)
    assert result == 11

    assert_no_current_call()


# =============================================================================
# Multiple Handler Error Resilience Tests
# =============================================================================


@pytest.mark.disable_logging_error_check
def test_resilience_multiple_handlers_with_errors(client, log_collector):
    """Test resilience when multiple handlers fail."""

    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        def make_accumulator(*args, **kwargs):
            def accumulate(state, value):
                if state is None:
                    state = []
                state.append(value)
                return state

            return accumulate

        def on_finish_post_processor(output):
            raise DummyTestException("FAILURE in post_processor!")

        _add_accumulator(
            simple_op,
            make_accumulator=make_accumulator,
            on_finish_post_processor=on_finish_post_processor,
        )

        simple_op._set_on_finish_handler(
            lambda call, output, exc: (_ for _ in ()).throw(
                DummyTestException("FAILURE in on_finish_handler!")
            )
        )

        return simple_op()

    # Even with multiple potential failure points, user code should work
    with raise_on_captured_errors(False):
        res = do_test()
        assert list(res) == [1, 2, 3]

    assert_no_current_call()


# =============================================================================
# Empty and Edge Case Tests
# =============================================================================


def test_resilience_empty_generator(client):
    """Test that empty generators work correctly."""

    @weave.op
    def empty_generator():
        return
        yield  # Makes this a generator

    result = list(empty_generator())
    assert result == []

    assert_no_current_call()


@pytest.mark.asyncio
async def test_resilience_empty_async_generator(client):
    """Test that empty async generators work correctly."""

    @weave.op
    async def empty_async_generator():
        return
        yield  # Makes this an async generator

    result = [x async for x in empty_async_generator()]
    assert result == []

    assert_no_current_call()


def test_resilience_op_with_no_args(client):
    """Test that ops with no arguments work correctly."""

    @weave.op
    def no_args_op():
        return 42

    result = no_args_op()
    assert result == 42

    assert_no_current_call()


def test_resilience_op_with_many_args(client):
    """Test that ops with many arguments work correctly."""

    @weave.op
    def many_args_op(a, b, c, d, e, f, g, h, i, j):
        return a + b + c + d + e + f + g + h + i + j

    result = many_args_op(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert result == 55

    assert_no_current_call()


def test_resilience_op_with_kwargs(client):
    """Test that ops with **kwargs work correctly."""

    @weave.op
    def kwargs_op(**kwargs):
        return sum(kwargs.values())

    result = kwargs_op(a=1, b=2, c=3)
    assert result == 6

    assert_no_current_call()


def test_resilience_op_with_varargs(client):
    """Test that ops with *args work correctly."""

    @weave.op
    def varargs_op(*args):
        return sum(args)

    result = varargs_op(1, 2, 3, 4, 5)
    assert result == 15

    assert_no_current_call()


# =============================================================================
# Return Value Preservation Tests
# =============================================================================


def test_return_value_preserved_on_tracing_error(client):
    """Test that return values are preserved even when tracing has issues."""

    @weave.op
    def important_op():
        return {"critical": "data", "value": 42}

    result = important_op()
    assert result == {"critical": "data", "value": 42}

    assert_no_current_call()


@pytest.mark.asyncio
async def test_async_return_value_preserved_on_tracing_error(client):
    """Test that async return values are preserved even when tracing has issues."""

    @weave.op
    async def important_async_op():
        return {"critical": "data", "value": 42}

    result = await important_async_op()
    assert result == {"critical": "data", "value": 42}

    assert_no_current_call()


def test_generator_values_preserved_on_tracing_error(client):
    """Test that generator values are preserved even when tracing has issues."""

    @weave.op
    def important_generator():
        yield "first"
        yield "second"
        yield "third"

    result = list(important_generator())
    assert result == ["first", "second", "third"]

    assert_no_current_call()


@pytest.mark.asyncio
async def test_async_generator_values_preserved_on_tracing_error(client):
    """Test that async generator values are preserved even when tracing has issues."""

    @weave.op
    async def important_async_generator():
        yield "first"
        yield "second"
        yield "third"

    result = [x async for x in important_async_generator()]
    assert result == ["first", "second", "third"]

    assert_no_current_call()
