import pytest

import weave
from tests.trace.util import DummyTestException
from weave.trace.context import call_context
from weave.trace.context.tests_context import raise_on_captured_errors
from weave.trace.op import _add_accumulator


def assert_no_current_call():
    assert call_context.get_current_call() is None


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
            _ = [item async for item in res]

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
            _ = [item async for item in res]

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
            _ = [item async for item in res]

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
            _ = [item async for item in res]

    with raise_on_captured_errors(False):
        with pytest.raises(DummyTestException):
            res = await do_test()
            _ = [item async for item in res]
