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
import weakref
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, TypeVar

_T = TypeVar("_T")

_thread_state = threading.local()

# One executor for every thread loop. Each loop would otherwise grow its own
# default executor for the driver's response parsing and for `asyncio.to_thread`,
# which on a 40-thread request pool is hundreds of idle threads. Sized to the
# request pool, not the CPU count: the driver parses every response here, and
# cpu+4 threads on a 1-CPU pod queued forty callers' parsing behind five
# workers, which on QA doubled p95 on every read that returns real rows.
SHARED_EXECUTOR_WORKERS = 64


class _SharedExecutor(ThreadPoolExecutor):
    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        # `loop.close()` shuts down the loop's default executor; this one is
        # shared by every thread loop and outlives all of them.
        pass


_shared_executor = _SharedExecutor(
    max_workers=SHARED_EXECUTOR_WORKERS, thread_name_prefix="sync-facade"
)


# Every thread loop ever created, with a weak ref to its thread. Pool threads
# (Starlette's, anyio's) exit when idle and take their thread-local slot with
# them, but not the loop or the aiohttp session opened on it. `reap_dead_loops`
# closes those from whichever thread calls next.
_loops: dict[int, tuple[weakref.ref[threading.Thread], asyncio.AbstractEventLoop]] = {}
_loops_lock = threading.Lock()


def thread_loop() -> asyncio.AbstractEventLoop:
    """The calling thread's private event loop, created on first use."""
    loop: asyncio.AbstractEventLoop | None = getattr(_thread_state, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        loop.set_default_executor(_shared_executor)
        _thread_state.loop = loop
        with _loops_lock:
            _loops[id(loop)] = (weakref.ref(threading.current_thread()), loop)
    return loop


def reap_dead_loops(closer: Callable[[], Awaitable[None]] | None = None) -> int:
    """Close loops whose thread has exited. Returns how many were closed.

    `closer` runs on each dead loop first, so a server can drain the aiohttp
    session that belongs to that loop; a loop that is not running may be driven
    from any thread.
    """
    with _loops_lock:
        dead = [
            (key, loop)
            for key, (thread_ref, loop) in _loops.items()
            if (thread := thread_ref()) is None or not thread.is_alive()
        ]
        for key, _ in dead:
            del _loops[key]
    for _, loop in dead:
        if loop.is_closed():
            continue
        try:
            if closer is not None:
                loop.run_until_complete(closer())
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
    return len(dead)


def close_thread_loop() -> None:
    """Close the calling thread's loop. Tests call this to free its executor."""
    loop: asyncio.AbstractEventLoop | None = getattr(_thread_state, "loop", None)
    if loop is not None and not loop.is_closed():
        loop.run_until_complete(loop.shutdown_asyncgens())
        # The default executor is shared; it outlives any one loop.
        loop.close()
    with _loops_lock:
        _loops.pop(id(loop), None)
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


def run_sync(awaitable: Awaitable[_T]) -> _T:
    """Run `awaitable` to completion on the calling thread's loop."""
    _refuse_inside_running_loop()
    return thread_loop().run_until_complete(awaitable)


def resolve(value: _T | Awaitable[_T]) -> _T:
    """Return `value`, running it first if it is awaitable.

    For a blocking body that calls a sibling which may already be a coroutine,
    or may be reached through the facade and already resolved. Goes away when
    the caller itself becomes a coroutine.
    """
    if inspect.isawaitable(value):
        return run_sync(value)
    return value


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
            return _sync_call(attr, self._reap)
        if inspect.isasyncgenfunction(attr):
            return _sync_iterate(attr, self._reap)
        return attr

    def _reap(self) -> None:
        reap_dead_loops(getattr(self._inner, "aclose", None))


def _sync_call(
    fn: Callable[..., Coroutine[Any, Any, _T]], before: Callable[[], None]
) -> Callable[..., _T]:
    @wraps(fn)
    def call(*args: Any, **kwargs: Any) -> _T:
        # Refuse before creating the coroutine, or it is never awaited.
        _refuse_inside_running_loop()
        before()
        return thread_loop().run_until_complete(fn(*args, **kwargs))

    return call


def _sync_iterate(
    fn: Callable[..., AsyncIterator[_T]], before: Callable[[], None]
) -> Callable[..., Iterator[_T]]:
    @wraps(fn)
    def iterate(*args: Any, **kwargs: Any) -> Iterator[_T]:
        _refuse_inside_running_loop()
        before()
        return iterate_sync(fn(*args, **kwargs))

    return iterate
