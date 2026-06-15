"""The purpose of this test suite is to ensure that Weave can handle various types of errors that can occur during tracing.

We should never be breaking the user's program with an error.
"""

# TODO: Test code capture resilience

from __future__ import annotations

import gc
import weakref
from collections import Counter
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

import weave
from tests.trace.util import DummyTestException
from weave.trace import weave_client
from weave.trace.context import call_context
from weave.trace.context.tests_context import raise_on_captured_errors
from weave.trace.op import Op, _add_accumulator

# Raising callbacks and op factories below are referenced eagerly by
# @pytest.mark.parametrize, so they must be defined before the tests.


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


def _define_func_op() -> Op:
    @weave.op
    def simple_op():
        return "hello"

    return simple_op


def _define_gen_op() -> Op:
    @weave.op
    def gen_op():
        yield from [1, 2, 3]

    return gen_op


def _define_async_func_op() -> Op:
    @weave.op
    async def simple_op():
        return "hello"

    return simple_op


def _define_async_gen_op() -> Op:
    @weave.op
    async def gen_op():
        yield 1
        yield 2
        yield 3

    return gen_op


def test_resilience_to_user_code_errors(weave_active):
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
    ag_res = Counter([k.split(", req:")[0] for k in {l.getMessage() for l in logs}])
    # Tim: This is very specific and intentional, please don't change
    # this unless you are sure that is the expected behavior
    assert ag_res == {
        "Task failed: DummyTestException: ('FAILURE - call_end": 1,
        "Task failed: DummyTestException: ('FAILURE - file_create": 1,
        "Task failed: DummyTestException: ('FAILURE - obj_create": 1,
    }


class _Blob(weave.Object):
    data: str


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "make_obj",
    [
        pytest.param(lambda: _Blob(data="X" * 4096), id="pydantic-object"),
        pytest.param(
            lambda: weave_client.Table([{"v": "X" * 256} for _ in range(16)]),
            id="table",
        ),
    ],
)
def test_resilience_to_obj_create_failure_does_not_pin_payload(
    client_with_throwing_server, make_obj
):
    """A failed save must release the user's object for GC.

    Before WB-31070, the failed `digest_future` stayed attached to the
    user's object via `obj.ref._digest`. The future's exception traceback
    retains the serialized payload via frame locals, pinning the object
    for its lifetime. Covers both the pydantic `client.save()` path and
    the `_save_table` path, which share the same shape.
    """
    obj = make_obj()
    obj_weak = weakref.ref(obj)

    try:
        client_with_throwing_server.save(obj, name="payload")
    except Exception:
        pass
    client_with_throwing_server.future_executor.flush()

    assert obj.ref is None

    del obj
    gc.collect()
    assert obj_weak() is None


@pytest.mark.disable_logging_error_check
def test_resilience_to_output_handler_errors(weave_active, log_collector):
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
async def test_resilience_to_output_handler_errors_async(weave_active, log_collector):
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


def _raising_make_accumulator() -> dict[str, object]:
    """make_accumulator kwargs whose make_accumulator itself raises."""

    def make_accumulator(*args, **kwargs):
        raise DummyTestException("FAILURE!")

    return {"make_accumulator": make_accumulator}


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("build_accumulator", "expected_msg"),
    [
        pytest.param(
            _raising_make_accumulator,
            "Error capturing call output",
            id="make-accumulator",
        ),
        pytest.param(
            lambda: {"make_accumulator": _accumulator_with_raising_accumulate()},
            "Error capturing value from iterator, call data may be incomplete",
            id="accumulation",
        ),
        pytest.param(
            lambda: {
                "make_accumulator": _empty_accumulator(),
                "should_accumulate": _raising_callback(),
            },
            "Error capturing call output",
            id="should-accumulate",
        ),
    ],
)
def test_resilience_to_accumulator_errors(
    weave_active, log_collector, build_accumulator, expected_msg
):
    """Sync accumulator callbacks that raise must not crash the user's op."""

    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        _add_accumulator(simple_op, **build_accumulator())
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
    assert logs[0].msg.startswith(expected_msg)


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("build_accumulator", "expected_msg"),
    [
        pytest.param(
            _raising_make_accumulator,
            "Error capturing call output",
            id="make-accumulator",
        ),
        pytest.param(
            lambda: {"make_accumulator": _accumulator_with_raising_accumulate()},
            "Error capturing async value from iterator, call data may be incomplete",
            id="accumulation",
        ),
        pytest.param(
            lambda: {
                "make_accumulator": _empty_accumulator(),
                "should_accumulate": _raising_callback(),
            },
            "Error capturing call output",
            id="should-accumulate",
        ),
    ],
)
async def test_resilience_to_accumulator_errors_async(
    weave_active, log_collector, build_accumulator, expected_msg
):
    """Async accumulator callbacks that raise must not crash the user's op."""

    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        _add_accumulator(simple_op, **build_accumulator())
        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            _ = [item async for item in await do_test()]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith(expected_msg)


# Here we are ignoring this warning because the exception IS being raised,
# and that is expected and tested for. It happens to be at the deletion moment
# so pytest is complaining that the exception is not being raised in the
# expected manner.
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_on_finish_post_processor_errors(
    weave_active, log_collector
):
    def do_test():
        @weave.op
        def simple_op():
            yield from [1, 2, 3]

        _add_accumulator(
            simple_op,
            make_accumulator=_empty_accumulator(),
            on_finish_post_processor=_raising_callback(),
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
    weave_active, log_collector
):
    async def do_test():
        @weave.op
        async def simple_op():
            yield 1
            yield 2
            yield 3

        _add_accumulator(
            simple_op,
            make_accumulator=_empty_accumulator(),
            on_finish_post_processor=_raising_callback(),
        )

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            # Consume the generator to trigger the make_accumulator call
            _ = [item async for item in await do_test()]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) > 0
    for log in logs:
        assert log.msg.startswith("Error capturing call output")


def test_resilience_to_accumulator_internal_errors(weave_active):
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
async def test_resilience_to_accumulator_internal_errors_async(weave_active):
    async def do_test():
        @weave.op(accumulator=lambda *args, **kwargs: {})
        async def simple_op():
            yield 1
            raise DummyTestException("FAILURE!")

        return simple_op()

    # The user's exception should be raised - even if we're capturing errors
    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            _ = [item async for item in await do_test()]

    with raise_on_captured_errors(False):
        with pytest.raises(DummyTestException):
            _ = [item async for item in await do_test()]


# =============================================================================
# Tests for postprocess_inputs/output and handler resilience
# =============================================================================


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "op_kwargs",
    [
        pytest.param(
            {"postprocess_inputs": _bad_postprocess_inputs}, id="postprocess-inputs"
        ),
        pytest.param(
            {"postprocess_output": _bad_postprocess_output}, id="postprocess-output"
        ),
        pytest.param({"call_display_name": _bad_display_name}, id="call-display-name"),
    ],
)
def test_resilience_to_op_kwarg_callback_errors(weave_active, log_collector, op_kwargs):
    """A raising postprocess_inputs/output or call_display_name must not crash the op."""

    @weave.op(**op_kwargs)
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
@pytest.mark.parametrize(
    "op_kwargs",
    [
        pytest.param(
            {"postprocess_inputs": _bad_postprocess_inputs}, id="postprocess-inputs"
        ),
        pytest.param(
            {"postprocess_output": _bad_postprocess_output}, id="postprocess-output"
        ),
        pytest.param({"call_display_name": _bad_display_name}, id="call-display-name"),
    ],
)
async def test_resilience_to_op_kwarg_callback_errors_async(
    weave_active, log_collector, op_kwargs
):
    """Async variant: a raising postprocess/display_name callback must not crash the op."""

    @weave.op(**op_kwargs)
    async def simple_op():
        return "hello"

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "set_handler",
    [
        pytest.param(
            lambda op: op._set_on_input_handler(_bad_input_handler), id="on-input"
        ),
        pytest.param(
            lambda op: op._set_on_finish_handler(_bad_finish_handler), id="on-finish"
        ),
    ],
)
def test_resilience_to_handler_errors(weave_active, log_collector, set_handler):
    """A raising _on_input_handler or _on_finish_handler must not crash the op."""

    @weave.op
    def simple_op():
        return "hello"

    set_handler(simple_op)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            simple_op()

    res = simple_op()
    assert res == "hello"
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    "set_handler",
    [
        pytest.param(
            lambda op: op._set_on_input_handler(_bad_input_handler), id="on-input"
        ),
        pytest.param(
            lambda op: op._set_on_finish_handler(_bad_finish_handler), id="on-finish"
        ),
    ],
)
async def test_resilience_to_handler_errors_async(
    weave_active, log_collector, set_handler
):
    """Async variant: a raising _on_input/_on_finish handler must not crash the op."""

    @weave.op
    async def simple_op():
        return "hello"

    set_handler(simple_op)

    with raise_on_captured_errors(True):
        with pytest.raises(DummyTestException):
            await simple_op()

    res = await simple_op()
    assert res == "hello"
    assert_no_current_call()


# =============================================================================
# Tests for call-context leak fix: _restore_call_stack on _create_call failure
# =============================================================================


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("define_op", "run_op"),
    [
        pytest.param(_define_func_op, lambda op: op(), id="func"),
        pytest.param(_define_gen_op, lambda op: list(op()), id="gen"),
    ],
)
def test_create_call_leak_restores_call_stack_sync(
    weave_active, monkeypatch, log_collector, define_op, run_op
):
    """If _create_call pushes a call then throws, the stack must be cleaned up (sync + sync-gen)."""
    op = define_op()
    monkeypatch.setattr("weave.trace.op._create_call", _make_leaking_create_call())

    res = run_op(op)
    assert res == _expected_result_for(define_op)
    assert_no_current_call()


@pytest.mark.asyncio
@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize(
    ("define_op", "is_gen"),
    [
        pytest.param(_define_async_func_op, False, id="async"),
        pytest.param(_define_async_gen_op, True, id="async-gen"),
    ],
)
async def test_create_call_leak_restores_call_stack_async(
    weave_active, monkeypatch, log_collector, define_op, is_gen
):
    """If _create_call pushes a call then throws, the stack must be cleaned up (async + async-gen)."""
    op = define_op()
    monkeypatch.setattr("weave.trace.op._create_call", _make_leaking_create_call())

    if is_gen:
        res = [item async for item in op()]
        assert res == [1, 2, 3]
    else:
        res = await op()
        assert res == "hello"
    assert_no_current_call()


@pytest.mark.disable_logging_error_check
def test_create_call_leak_preserves_parent_call(
    weave_active, monkeypatch, log_collector
):
    """When a nested op's _create_call leaks, the parent call must remain current."""
    inner_saw_parent = None

    @weave.op
    def outer_op():
        # At this point outer's call is on the stack.
        # Now make the inner op's _create_call leak.
        monkeypatch.setattr("weave.trace.op._create_call", _make_leaking_create_call())

        @weave.op
        def inner_op():
            return 42

        result = inner_op()

        # After inner_op returns, the current call should still be outer's call
        nonlocal inner_saw_parent
        inner_saw_parent = call_context.get_current_call()
        return result

    res = outer_op()
    assert res == 42
    # The parent (outer) call should have been preserved during inner's failure
    assert inner_saw_parent is not None
    assert inner_saw_parent.id != "leaked-call-id"


# =============================================================================
# Helpers
# =============================================================================


def assert_no_current_call():
    assert call_context.get_current_call() is None


def reset_call_context():
    """Force reset the call context to an empty stack."""
    token = call_context._call_stack.set([])
    call_context._call_stack.reset(token)


def _raising_callback() -> Callable[..., object]:
    """A callback that always raises, used for should_accumulate/on_finish."""

    def callback(*args, **kwargs):
        raise DummyTestException("FAILURE!")

    return callback


def _empty_accumulator() -> Callable[..., object]:
    """make_accumulator returning an accumulate fn that yields an empty dict."""

    def make_accumulator(*args, **kwargs):
        def accumulate(*args, **kwargs):
            return {}

        return accumulate

    return make_accumulator


def _accumulator_with_raising_accumulate() -> Callable[..., object]:
    """make_accumulator returning an accumulate fn that raises."""

    def make_accumulator(*args, **kwargs):
        def accumulate(*args, **kwargs):
            raise DummyTestException("FAILURE!")

        return accumulate

    return make_accumulator


def _make_leaking_create_call():
    """Return a fake _create_call that pushes a call onto the stack then raises.

    This simulates the scenario where client.create_call partially succeeds
    (pushes a call) but then something fails, leaving an orphaned call on the
    context stack.
    """

    def leaking_create_call(func, *args, **kwargs):
        # Create a minimal mock call with an id, push it, then fail
        fake_call = MagicMock()
        fake_call.id = "leaked-call-id"
        call_context.push_call(fake_call)
        raise DummyTestException("Simulated _create_call failure after push")

    return leaking_create_call


def _expected_result_for(define_op: Callable[[], Op]) -> object:
    return [1, 2, 3] if define_op is _define_gen_op else "hello"
