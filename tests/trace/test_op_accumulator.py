import atexit
import contextlib
import enum
import gc
import subprocess
import sys
import textwrap
import weakref
from collections.abc import Iterator

import pytest

import weave
from tests.trace.util import DummyTestException
from weave.trace.context import call_context
from weave.trace.context.tests_context import raise_on_captured_errors
from weave.trace.op import (
    _add_accumulator,
    _AsyncIteratorWrapper,
    _DualIteratorWrapper,
    _select_iterator_wrapper,
    _SyncIteratorWrapper,
)


def assert_no_current_call():
    assert call_context.get_current_call() is None


def test_finished_iterator_wrappers_do_not_leak_atexit_callbacks():
    """Finished streams must not leave one process-exit callback behind each.

    This is the customer memory-leak regression: the previous implementation
    registered an atexit callback for every ``_IteratorWrapper``. Even after a
    stream finished and the wrapper was garbage-collected, CPython's atexit
    callback registry kept growing linearly with stream count.
    """
    iterator_wrapper_leak_repro_count = 10
    close_count = 0

    def on_close():
        nonlocal close_count
        close_count += 1

    # Warm up weakref.finalize so its one process-level exit hook is already
    # reflected in the baseline. The regression was one new atexit callback per
    # stream, not the stdlib's single finalizer exit hook.
    warmup_wrapper = _SyncIteratorWrapper(
        iter([1]), lambda value: None, lambda error: None, on_close
    )
    warmup_wrapper.close()
    del warmup_wrapper
    # Force GC so weakref.finalize bookkeeping settles before measuring the
    # process-level atexit callback count.
    gc.collect()

    baseline_callback_count = atexit._ncallbacks()
    close_count = 0

    for _ in range(iterator_wrapper_leak_repro_count):
        wrapper = _SyncIteratorWrapper(
            iter([1]), lambda value: None, lambda error: None, on_close
        )
        assert list(wrapper) == [1]

    del wrapper
    # Force GC after dropping the last wrapper reference so the assertion below
    # measures retained exit callbacks, not pending collection.
    gc.collect()

    assert close_count == iterator_wrapper_leak_repro_count
    assert atexit._ncallbacks() == baseline_callback_count


def test_unfinished_iterator_wrapper_does_not_keep_wrapper_alive():
    """The process-exit finalizer must not strongly retain unfinished wrappers.

    Capturing ``self`` or a bound method in ``weakref.finalize`` would keep an
    abandoned unfinished wrapper alive until process exit. Normal GC cleanup is
    supposed to run through ``__del__`` instead.
    """
    close_count = 0

    def on_close():
        nonlocal close_count
        close_count += 1

    wrapper = _SyncIteratorWrapper(
        iter([1]), lambda value: None, lambda error: None, on_close
    )
    wrapper_ref = weakref.ref(wrapper)

    del wrapper
    gc.collect()

    assert wrapper_ref() is None
    assert close_count == 1


def test_process_exit_finalizer_is_idempotent_for_unfinished_iterator_wrapper():
    """The wrapper-owned process-exit finalizer should close an unfinished stream once.

    Finished streams detach their process-exit finalizer in the previous test.
    This covers the finalizer object's idempotency: even if the finalizer is
    invoked more than once, the stream close callback runs once.
    """
    close_count = 0

    def on_close():
        nonlocal close_count
        close_count += 1

    wrapper = _SyncIteratorWrapper(
        iter([1]), lambda value: None, lambda error: None, on_close
    )

    wrapper._process_exit_finalizer()
    wrapper._process_exit_finalizer()

    assert close_count == 1
    wrapper.close()


def test_process_exit_closes_unfinished_iterator_wrapper(tmp_path):
    """A real subprocess exit should close an unfinished iterator wrapper.

    This protects the weakref.finalize wiring at interpreter shutdown. A direct
    finalizer call proves idempotency, but the customer bug was specifically in
    process-exit cleanup registration.
    """
    marker_path = tmp_path / "closed.txt"
    code = textwrap.dedent(
        """
        import sys
        from pathlib import Path

        from weave.trace.op import _SyncIteratorWrapper

        # This test is specifically about weakref.finalize/atexit wiring, not
        # the normal GC ``__del__`` cleanup path.
        _SyncIteratorWrapper.__del__ = lambda self: None

        marker_path = Path(sys.argv[1])

        def on_close():
            marker_path.write_text("closed", encoding="utf-8")

        wrapper = _SyncIteratorWrapper(iter([1]), lambda value: None, lambda error: None, on_close)
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code, str(marker_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert marker_path.read_text(encoding="utf-8") == "closed"


async def _async_numbers():
    yield 1


@contextlib.contextmanager
def _context_manager():
    yield iter([1])


@contextlib.asynccontextmanager
async def _async_context_manager():
    yield _async_numbers()


class _IteratorSubclass(Iterator):
    def __next__(self):
        raise StopIteration


class _Color(enum.Enum):
    RED = 1


class _SyncAndAsyncIterable:
    def __iter__(self):
        return self

    def __aiter__(self):
        return self


class _RaisingGetattrMeta(type):
    def __getattr__(cls, name):
        raise KeyError(name)


class _IterableWithRaisingGetattr(metaclass=_RaisingGetattrMeta):
    def __iter__(self):
        return self

    def __getattr__(self, name):
        raise KeyError(name)


class _GetattrProxy:
    def __init__(self, stream):
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(iter([1]), _SyncIteratorWrapper, id="iterator"),
        pytest.param(_IteratorSubclass(), _SyncIteratorWrapper, id="inherited-iter"),
        pytest.param({"stream": iter([1])}, _SyncIteratorWrapper, id="dict"),
        pytest.param(_context_manager(), _SyncIteratorWrapper, id="context-manager"),
        pytest.param(
            _IterableWithRaisingGetattr(), _SyncIteratorWrapper, id="raising-getattr"
        ),
        pytest.param(
            _GetattrProxy(iter([1])), _DualIteratorWrapper, id="getattr-proxy"
        ),
        pytest.param(_async_numbers(), _AsyncIteratorWrapper, id="async-generator"),
        pytest.param(
            _async_context_manager(), _AsyncIteratorWrapper, id="async-context-manager"
        ),
        pytest.param(_SyncAndAsyncIterable(), _DualIteratorWrapper, id="both"),
        pytest.param(object(), _DualIteratorWrapper, id="neither"),
        pytest.param(_Color.RED, _DualIteratorWrapper, id="enum-member"),
    ],
)
def test_select_iterator_wrapper(value, expected):
    selected = _select_iterator_wrapper(
        value, _SyncIteratorWrapper, _AsyncIteratorWrapper
    )
    assert selected is expected


_STREAM_PROTOCOL_METHODS = (
    "__iter__",
    "__next__",
    "__enter__",
    "__exit__",
    "__aiter__",
    "__anext__",
    "__aenter__",
    "__aexit__",
)


@pytest.mark.parametrize(
    ("wrapper_class", "expected"),
    [
        (_SyncIteratorWrapper, {"__iter__", "__next__", "__enter__", "__exit__"}),
        (
            _AsyncIteratorWrapper,
            {"__aiter__", "__anext__", "__aenter__", "__aexit__"},
        ),
        (_DualIteratorWrapper, set(_STREAM_PROTOCOL_METHODS)),
    ],
)
def test_iterator_wrapper_has_only_its_protocols(wrapper_class, expected):
    methods = {
        name for name in _STREAM_PROTOCOL_METHODS if hasattr(wrapper_class, name)
    }
    assert methods == expected


@pytest.mark.asyncio
async def test_op_accumulator_wraps_stream_by_its_protocol(weave_active):
    @weave.op(accumulator=lambda *args, **kwargs: {})
    def stream_op(is_async: bool):
        return _async_numbers() if is_async else iter([1])

    sync_stream = stream_op(False)
    assert type(sync_stream) is _SyncIteratorWrapper
    assert list(sync_stream) == [1]

    async_stream = stream_op(True)
    assert type(async_stream) is _AsyncIteratorWrapper
    assert [value async for value in async_stream] == [1]


@pytest.mark.asyncio
async def test_async_op_accumulates_async_and_traced_sync_streams(client):
    @weave.op(accumulator=lambda acc, value: (acc or []) + [value])
    def inner():
        return iter([1, 2])

    @weave.op(accumulator=lambda acc, value: (acc or []) + [value])
    async def outer(traced: bool):
        return inner() if traced else _async_numbers()

    assert list(await outer(True)) == [1, 2]
    assert [value async for value in await outer(False)] == [1]

    calls = list(client.get_calls())
    assert [call.output for call in calls] == [[1, 2], [1, 2], [1]]


class _CustomSyncWrapper(_SyncIteratorWrapper):
    pass


class _CustomAsyncWrapper(_AsyncIteratorWrapper):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("wrapper_kwargs", "sync_class", "async_class"),
    [
        pytest.param({}, _SyncIteratorWrapper, _AsyncIteratorWrapper, id="default"),
        pytest.param(
            {
                "iterator_wrapper": _CustomSyncWrapper,
                "async_iterator_wrapper": _CustomAsyncWrapper,
            },
            _CustomSyncWrapper,
            _CustomAsyncWrapper,
            id="custom",
        ),
    ],
)
async def test_add_accumulator_wraps_stream_by_its_protocol(
    weave_active, wrapper_kwargs, sync_class, async_class
):
    @weave.op
    def stream_op(is_async: bool):
        return _async_numbers() if is_async else iter([1])

    _add_accumulator(
        stream_op,
        make_accumulator=lambda inputs: lambda acc, value: value,
        **wrapper_kwargs,
    )

    sync_stream = stream_op(False)
    assert type(sync_stream) is sync_class
    assert list(sync_stream) == [1]

    async_stream = stream_op(True)
    assert type(async_stream) is async_class
    assert [value async for value in async_stream] == [1]


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_make_accumulator_errors(weave_active, log_collector):
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
    weave_active, log_collector
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
            _ = [item async for item in await do_test()]

    # We should gracefully handle the error and return a value
    res = await do_test()
    assert [item async for item in res] == [1, 2, 3]

    assert_no_current_call()

    logs = log_collector.get_error_logs()
    assert len(logs) == 1
    assert logs[0].msg.startswith("Error capturing call output")


@pytest.mark.disable_logging_error_check
def test_resilience_to_accumulator_accumulation_errors(weave_active, log_collector):
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
    weave_active, log_collector
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
            _ = [item async for item in await do_test()]

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
def test_resilience_to_accumulator_should_accumulate_errors(
    weave_active, log_collector
):
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
    weave_active, log_collector
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
            _ = [i async for i in await do_test()]

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
    weave_active, log_collector
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
    weave_active, log_collector
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
