"""Blocking view of an async trace server, over a small pool of long-lived loops.

`SyncTraceServerFacade` bridges every coroutine method of the wrapped server
onto one of a few event loops that run forever on their own threads, so a `def`
FastAPI handler on the Starlette threadpool, or a test, can call the async
server without an `await`. Async generators come back as blocking iterators.
Nothing here has a method body of its own: the async server is the only
implementation.

Why a pool and not a loop per calling thread: an aiohttp session belongs to the
loop that opened it. Starlette's worker threads are pruned after ten seconds
idle, so a loop per thread meant a fresh session, a fresh ClickHouse client and
a fresh TLS connection inside the first request on every new thread, and large
results then ran on cold connections. A fixed set of loops keeps a fixed set of
warm sessions for the whole process.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import inspect
import itertools
import os
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, TypeVar

_T = TypeVar("_T")

# How many loops, and so how many ClickHouse sessions, a process runs for its
# sync callers. A blocking call inside a converted body stalls only its own
# loop's neighbours, so this is also the blast radius of such a call.
LOOP_POOL_SIZE = int(os.environ.get("WEAVE_SYNC_FACADE_LOOPS", "4"))

# One executor for every pool loop, for the driver's response parsing and for
# `asyncio.to_thread`. Sized to the request pool rather than the CPU count so
# no caller waits on another's parse.
SHARED_EXECUTOR_WORKERS = 64


class _SharedExecutor(ThreadPoolExecutor):
    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        # `loop.close()` shuts down the loop's default executor; this one is
        # shared by every pool loop and outlives all of them.
        pass


_shared_executor = _SharedExecutor(
    max_workers=SHARED_EXECUTOR_WORKERS, thread_name_prefix="sync-facade"
)


class LoopPool:
    """`size` event loops, each running forever on its own daemon thread."""

    def __init__(self, size: int) -> None:
        if size < 1:
            raise ValueError("LoopPool needs at least one loop")
        self._loops: list[asyncio.AbstractEventLoop] = []
        self._threads: list[threading.Thread] = []
        self._next = itertools.count()
        ready = threading.Barrier(size + 1)
        for i in range(size):
            loop = asyncio.new_event_loop()
            loop.set_default_executor(_shared_executor)
            thread = threading.Thread(
                target=self._serve,
                args=(loop, ready),
                name=f"sync-facade-loop-{i}",
                daemon=True,
            )
            thread.start()
            self._loops.append(loop)
            self._threads.append(thread)
        ready.wait()

    @staticmethod
    def _serve(loop: asyncio.AbstractEventLoop, ready: threading.Barrier) -> None:
        asyncio.set_event_loop(loop)
        ready.wait()
        loop.run_forever()

    @property
    def loops(self) -> list[asyncio.AbstractEventLoop]:
        return list(self._loops)

    def pick(self) -> asyncio.AbstractEventLoop:
        """Round-robin. Cheap, and it spreads a burst over every loop."""
        return self._loops[next(self._next) % len(self._loops)]

    def run(self, loop: asyncio.AbstractEventLoop, awaitable: Awaitable[_T]) -> _T:
        """Run `awaitable` on `loop` from another thread and block for the result.

        The task is created inside a copy of the caller's context, so contextvars
        (OTel context, the write batch, secret fetchers) are visible inside, as
        they were under `run_until_complete`. `ctx.run(...)` rather than
        `create_task(context=...)` because weave still supports Python 3.10.
        """
        ctx = contextvars.copy_context()
        done: concurrent.futures.Future[_T] = concurrent.futures.Future()

        def start() -> None:
            try:
                task = ctx.run(asyncio.ensure_future, awaitable, loop=loop)
            except BaseException as exc:
                done.set_exception(exc)
                return

            def finish(t: asyncio.Future[_T]) -> None:
                if t.cancelled():
                    done.cancel()
                elif t.exception() is not None:
                    done.set_exception(t.exception())  # type: ignore[arg-type]
                else:
                    done.set_result(t.result())

            task.add_done_callback(finish)

        loop.call_soon_threadsafe(start)
        return done.result()

    def shutdown(self, closer: Callable[[], Awaitable[None]] | None = None) -> None:
        """Run `closer` on every loop, then stop the loops and join the threads."""
        for loop in self._loops:
            if loop.is_closed():
                continue
            if closer is not None:
                self.run(loop, closer())
            self.run(loop, loop.shutdown_asyncgens())
            loop.call_soon_threadsafe(loop.stop)
        for thread in self._threads:
            thread.join(timeout=30)
        for loop in self._loops:
            if not loop.is_closed():
                loop.close()


_pool: LoopPool | None = None
_pool_lock = threading.Lock()


def loop_pool() -> LoopPool:
    """The process-wide pool, started on first use."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = LoopPool(LOOP_POOL_SIZE)
    return _pool


def shutdown_loop_pool(closer: Callable[[], Awaitable[None]] | None = None) -> None:
    """Drain and stop the pool. Services call this on shutdown; tests between cases.

    `closer` runs once on each loop first, so a server can close the aiohttp
    session that belongs to that loop.
    """
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.shutdown(closer)


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
    """Run `awaitable` to completion on a pool loop and return its result."""
    _refuse_inside_running_loop()
    pool = loop_pool()
    return pool.run(pool.pick(), awaitable)


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
    """Drive an async iterator one item per step, pinned to one pool loop.

    Lazy on purpose: a streaming response is consumed item by item. The
    generator, every `anext`, and the final `aclose` all run on the same loop.
    """
    _refuse_inside_running_loop()
    pool = loop_pool()
    loop = pool.pick()
    try:
        while True:
            try:
                yield pool.run(loop, anext(agen))
            except StopAsyncIteration:
                return
    finally:
        aclose = getattr(agen, "aclose", None)
        if aclose is not None:
            pool.run(loop, aclose())


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


def _sync_call(fn: Callable[..., Awaitable[_T]]) -> Callable[..., _T]:
    @wraps(fn)
    def call(*args: Any, **kwargs: Any) -> _T:
        # Refuse before creating the coroutine, or it is never awaited.
        _refuse_inside_running_loop()
        return run_sync(fn(*args, **kwargs))

    return call


def _sync_iterate(fn: Callable[..., AsyncIterator[_T]]) -> Callable[..., Iterator[_T]]:
    @wraps(fn)
    def iterate(*args: Any, **kwargs: Any) -> Iterator[_T]:
        _refuse_inside_running_loop()
        return iterate_sync(fn(*args, **kwargs))

    return iterate
