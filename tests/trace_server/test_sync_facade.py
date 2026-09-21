"""`SyncTraceServerFacade` bridges coroutines and async generators over a fixed
pool of long-lived loop threads.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from weave.trace_server import sync_facade
from weave.trace_server.sync_facade import (
    SyncTraceServerFacade,
    loop_pool,
    resolve,
    shutdown_loop_pool,
)

_request_tag: contextvars.ContextVar[str] = contextvars.ContextVar("tag", default="")


class FakeAsyncServer:
    def __init__(self) -> None:
        self.loops: list[asyncio.AbstractEventLoop] = []
        self.closed_on: list[asyncio.AbstractEventLoop] = []
        self.plain = "attribute"

    async def read(self, value: int) -> int:
        self.loops.append(asyncio.get_running_loop())
        await asyncio.sleep(0)
        return value * 2

    async def tagged(self) -> str:
        return _request_tag.get()

    async def stream(self, n: int) -> AsyncIterator[int]:
        try:
            for i in range(n):
                self.loops.append(asyncio.get_running_loop())
                await asyncio.sleep(0)
                yield i
        finally:
            self.closed_on.append(asyncio.get_running_loop())

    async def boom(self) -> None:
        raise ValueError("boom")

    async def aclose(self) -> None:
        self.closed_on.append(asyncio.get_running_loop())

    def sync_method(self) -> str:
        return "sync"


@pytest.fixture
def facade() -> SyncTraceServerFacade:
    shutdown_loop_pool()
    yield SyncTraceServerFacade(FakeAsyncServer())
    shutdown_loop_pool()


def test_coroutine_runs_to_completion(facade: SyncTraceServerFacade) -> None:
    assert facade.read(21) == 42


def test_non_async_attributes_pass_through(facade: SyncTraceServerFacade) -> None:
    assert facade.plain == "attribute"
    assert facade.sync_method() == "sync"


def test_attribute_writes_land_on_the_inner_server(
    facade: SyncTraceServerFacade,
) -> None:
    facade.plain = "replaced"
    assert facade._inner.plain == "replaced"
    assert "plain" not in vars(facade)
    # unittest.mock.patch.object restores through delattr when the attribute
    # was not in the target's own __dict__.
    with patch.object(facade, "sync_method", return_value="patched"):
        assert facade.sync_method() == "patched"
    assert facade.sync_method() == "sync"


def test_exceptions_propagate(facade: SyncTraceServerFacade) -> None:
    with pytest.raises(ValueError, match="boom"):
        facade.boom()


def test_async_generator_is_a_lazy_iterator_pinned_to_one_loop(
    facade: SyncTraceServerFacade,
) -> None:
    it = facade.stream(3)
    assert next(it) == 0
    assert facade._inner.closed_on == []
    assert list(it) == [1, 2]
    # Every step and the final close ran on the same loop.
    assert len(set(facade._inner.loops)) == 1
    assert facade._inner.closed_on == [facade._inner.loops[0]]


def test_abandoned_iterator_closes_the_generator(facade: SyncTraceServerFacade) -> None:
    it = facade.stream(10)
    next(it)
    it.close()
    assert len(facade._inner.closed_on) == 1


def test_callers_share_a_fixed_number_of_loops(facade: SyncTraceServerFacade) -> None:
    """Forty caller threads, far more than the pool, still touch only the pool's
    loops: this is what keeps ClickHouse sessions warm across thread churn.
    """
    with ThreadPoolExecutor(max_workers=40) as pool:
        results = list(pool.map(facade.read, range(200)))
    assert results == [i * 2 for i in range(200)]
    loops_used = set(facade._inner.loops)
    assert loops_used == set(loop_pool().loops)
    assert len(loops_used) == sync_facade.LOOP_POOL_SIZE


def test_caller_context_is_visible_inside(facade: SyncTraceServerFacade) -> None:
    _request_tag.set("req-7")
    assert facade.tagged() == "req-7"


def test_refuses_to_run_inside_a_running_loop(facade: SyncTraceServerFacade) -> None:
    async def misuse() -> None:
        facade.read(1)

    with pytest.raises(RuntimeError, match="inside a running event loop"):
        asyncio.run(misuse())


def test_refuses_from_a_pool_loop_itself(facade: SyncTraceServerFacade) -> None:
    """A coroutine on a pool loop calling back into the facade would deadlock
    its own loop; it must raise instead.
    """
    inner = facade._inner

    async def reenter() -> None:
        facade.read(1)

    inner.reenter = reenter
    with pytest.raises(RuntimeError, match="inside a running event loop"):
        facade.reenter()


def test_facade_defines_no_server_methods() -> None:
    """The async server is the only implementation; the facade only forwards."""
    own = {
        name
        for name, value in vars(SyncTraceServerFacade).items()
        if callable(value) and not name.startswith("_")
    }
    assert own == set()


def test_shutdown_runs_the_closer_on_every_loop_and_stops_them(
    facade: SyncTraceServerFacade,
) -> None:
    facade.read(1)
    pool = loop_pool()
    loops = pool.loops
    shutdown_loop_pool(facade._inner.aclose)
    assert set(facade._inner.closed_on) == set(loops)
    assert all(loop.is_closed() for loop in loops)
    assert not any(t.is_alive() for t in pool._threads)
    # The next call starts a fresh pool.
    assert facade.read(2) == 4
    assert loop_pool() is not pool


def test_resolve_accepts_a_value_or_an_awaitable() -> None:
    async def later() -> int:
        return 3

    assert resolve(3) == 3
    assert resolve(later()) == 3
    shutdown_loop_pool()


def test_pool_loops_share_one_default_executor(facade: SyncTraceServerFacade) -> None:
    async def where() -> str:
        return await asyncio.to_thread(lambda: threading.current_thread().name)

    inner = facade._inner
    inner.where = where
    names = {facade.where() for _ in range(8)}
    assert all(name.startswith("sync-facade") for name in names), names
