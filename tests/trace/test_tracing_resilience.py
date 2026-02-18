"""The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.
"""

# TODO: Test code capture resilience

from collections import Counter

import pytest

import weave
from tests.trace.util import DummyTestException
from weave.trace.context import call_context
from weave.trace.context.tests_context import raise_on_captured_errors


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
