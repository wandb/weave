"""Blocking view of an async trace server, one event loop per calling thread.

`SyncTraceServerFacade` bridges every coroutine method of the wrapped server
onto a loop that is local to the calling thread, so a `def` FastAPI handler on
the Starlette threadpool, or a test, can call the async server without an
`await`. Async generators come back as blocking iterators. Nothing here has a
method body of its own: the async server is the only implementation.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from functools import wraps
from typing import Any, TypeVar

_T = TypeVar("_T")

_thread_state = threading.local()


def thread_loop() -> asyncio.AbstractEventLoop:
    """The calling thread's private event loop, created on first use."""
    loop: asyncio.AbstractEventLoop | None = getattr(_thread_state, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_state.loop = loop
    return loop


def close_thread_loop() -> None:
    """Close the calling thread's loop. Tests call this to free its executor."""
    loop: asyncio.AbstractEventLoop | None = getattr(_thread_state, "loop", None)
    if loop is not None and not loop.is_closed():
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()
    _thread_state.loop = None


def _refuse_inside_running_loop() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError(
        "SyncTraceServerFacade was called from inside a running event loop; "
        "await the async server directly instead."
    )


def run_sync(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run `coro` to completion on the calling thread's loop."""
    _refuse_inside_running_loop()
    return thread_loop().run_until_complete(coro)


def iterate_sync(agen: AsyncIterator[_T]) -> Iterator[_T]:
    """Drive an async iterator from the calling thread's loop, one item per step.

    Lazy on purpose: a streaming response is consumed item by item, and the loop
    outlives the iteration because it belongs to the thread, not to this call.
    """
    _refuse_inside_running_loop()
    loop = thread_loop()
    try:
        while True:
            try:
                yield loop.run_until_complete(anext(agen))
            except StopAsyncIteration:
                return
    finally:
        aclose = getattr(agen, "aclose", None)
        if aclose is not None:
            loop.run_until_complete(aclose())


class SyncTraceServerFacade:
    """Every coroutine method of `inner`, callable without `await`.

    Attribute access is forwarded. Coroutine functions come back wrapped in
    `run_sync`, async generator functions in `iterate_sync`, everything else as
    is. The facade defines no server methods itself; a test asserts that.
    """

    def __init__(self, inner: Any) -> None:
        object.__setattr__(self, "_inner", inner)

    def __setattr__(self, name: str, value: Any) -> None:
        # Tests and wiring set state on the server; the facade owns nothing.
        setattr(self._inner, name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self._inner, name)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if inspect.iscoroutinefunction(attr):
            return _sync_call(attr)
        if inspect.isasyncgenfunction(attr):
            return _sync_iterate(attr)
        return attr


def _sync_call(fn: Callable[..., Coroutine[Any, Any, _T]]) -> Callable[..., _T]:
    @wraps(fn)
    def call(*args: Any, **kwargs: Any) -> _T:
        # Refuse before creating the coroutine, or it is never awaited.
        _refuse_inside_running_loop()
        return thread_loop().run_until_complete(fn(*args, **kwargs))

    return call


def _sync_iterate(fn: Callable[..., AsyncIterator[_T]]) -> Callable[..., Iterator[_T]]:
    @wraps(fn)
    def iterate(*args: Any, **kwargs: Any) -> Iterator[_T]:
        _refuse_inside_running_loop()
        return iterate_sync(fn(*args, **kwargs))

    return iterate
