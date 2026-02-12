"""The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.
"""

# TODO: Test postprocess input/output resilience
from collections import Counter

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
# Code Capture Resilience Tests
# =============================================================================
# These tests ensure that the @weave.op decorator and weave.publish() never
# crash user code due to failures in the code capture step.


def test_code_capture_resilience_no_source_available(client):
    """
    Requirement: Publishing an op should not crash when source code is unavailable
    Interface: weave.publish(op)
    Given: A function wrapped with @weave.op where inspect.getsource() would fail
    When: weave.publish(op) is called
    Then: The publish completes without raising an exception
    """
    # Create a function dynamically using exec - this has no source file
    namespace = {}
    exec(
        """
def dynamic_func(x):
    return x * 2
""",
        namespace,
    )
    dynamic_func = namespace["dynamic_func"]

    # Wrap it with weave.op
    op_func = weave.op(dynamic_func)

    # This should not raise - code capture should handle the missing source gracefully
    ref = weave.publish(op_func)
    assert ref is not None

    # The op should still work correctly
    assert op_func(5) == 10


def test_code_capture_resilience_disabled_capture_no_source(client):
    """
    Requirement: Publishing an op with code capture disabled should not crash
                 even when source is unavailable
    Interface: weave.publish(op) with enable_code_capture=False
    Given: A dynamically created function with @weave.op(enable_code_capture=False)
    When: weave.publish(op) is called
    Then: The publish completes without raising an exception
    """
    # Create a function dynamically - no source available
    namespace = {}
    exec(
        """
def no_source_func(x):
    return x + 1
""",
        namespace,
    )
    no_source_func = namespace["no_source_func"]

    # Wrap with code capture disabled
    op_func = weave.op(no_source_func, enable_code_capture=False)

    # This should not raise
    ref = weave.publish(op_func)
    assert ref is not None

    # The op should still work correctly
    assert op_func(10) == 11


def test_code_capture_resilience_builtin_function(client):
    """
    Requirement: Wrapping and publishing a built-in function should not crash
    Interface: @weave.op decorator applied to built-in, then weave.publish()
    Given: A built-in function like len wrapped with @weave.op
    When: weave.publish(op) is called
    Then: The publish completes without raising an exception
    """
    # Wrap a built-in function - these have no Python source
    op_len = weave.op(len)

    # This should not raise
    ref = weave.publish(op_len)
    assert ref is not None

    # The op should still work
    assert op_len([1, 2, 3]) == 3


def test_code_capture_resilience_closure_with_non_serializable_object(client):
    """
    Requirement: Code capture should handle closures with non-serializable objects
    Interface: weave.publish(op) for op with problematic closure
    Given: A function with a closure containing an object that fails serialization
    When: weave.publish(op) is called
    Then: The publish completes (possibly with warnings) without raising an exception
    """

    class NonSerializableObject:
        """An object that raises on equality comparison (like pandas DataFrames)."""

        def __eq__(self, other):
            raise ValueError("Cannot compare this object")

        def __repr__(self):
            return "<NonSerializableObject>"

    # Create a closure with the non-serializable object
    problematic_obj = NonSerializableObject()

    @weave.op
    def func_with_problematic_closure(x):
        # Reference the problematic object in the closure
        _ = problematic_obj
        return x * 2

    # This should not raise - code capture should handle the serialization failure
    ref = weave.publish(func_with_problematic_closure)
    assert ref is not None

    # The op should still work correctly
    assert func_with_problematic_closure(5) == 10


def test_code_capture_resilience_lambda(client):
    """
    Requirement: Publishing a lambda wrapped as an op should not crash
    Interface: weave.publish(op) for lambda
    Given: A lambda function wrapped with weave.op
    When: weave.publish(op) is called
    Then: The publish completes without raising an exception
    """
    # Lambdas can have tricky source extraction
    op_lambda = weave.op(lambda x: x**2)

    # This should not raise
    ref = weave.publish(op_lambda)
    assert ref is not None

    # The op should still work
    assert op_lambda(4) == 16


def test_code_capture_resilience_op_execution_unaffected(client):
    """
    Requirement: Op execution must not be affected by code capture failures
    Interface: Calling an @weave.op decorated function
    Given: An op where code capture would fail
    When: The op is called multiple times
    Then: All calls execute correctly and return expected results
    """
    # Create a function that will have code capture issues
    namespace = {}
    exec(
        """
def compute(a, b):
    return a + b
""",
        namespace,
    )
    compute = namespace["compute"]
    op_compute = weave.op(compute)

    # Multiple calls should all work correctly
    assert op_compute(1, 2) == 3
    assert op_compute(10, 20) == 30
    assert op_compute(-5, 5) == 0

    # Publishing should also work
    ref = weave.publish(op_compute)
    assert ref is not None

    # Calls after publish should still work
    assert op_compute(100, 200) == 300


def test_code_capture_resilience_c_extension_function(client):
    """
    Requirement: Wrapping C extension functions should not crash during publish
    Interface: weave.publish(op) for C extension function
    Given: A C extension function (like math.sqrt) wrapped with @weave.op
    When: weave.publish(op) is called
    Then: The publish completes without raising an exception
    """
    import math

    # math.sqrt is a C extension function with no Python source
    op_sqrt = weave.op(math.sqrt)

    # This should not raise
    ref = weave.publish(op_sqrt)
    assert ref is not None

    # The op should still work
    assert op_sqrt(16) == 4.0
