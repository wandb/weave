"""`SyncTraceServerFacade` bridges coroutines and async generators per thread."""

from __future__ import annotations

import asyncio
import contextvars
import threading
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest

from weave.trace_server import sync_facade
from weave.trace_server.sync_facade import (
    SyncTraceServerFacade,
    close_thread_loop,
    resolve,
)

_request_tag: contextvars.ContextVar[str] = contextvars.ContextVar("tag", default="")


class FakeAsyncServer:
    def __init__(self) -> None:
        self.loops: list[asyncio.AbstractEventLoop] = []
        self.closed_on: list[asyncio.AbstractEventLoop] = []
        self.closed_streams = 0
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
                await asyncio.sleep(0)
                yield i
        finally:
            self.closed_streams += 1

    async def boom(self) -> None:
        raise ValueError("boom")

    async def aclose(self) -> None:
        self.closed_on.append(asyncio.get_running_loop())

    def sync_method(self) -> str:
        return "sync"


@pytest.fixture
def facade() -> SyncTraceServerFacade:
    yield SyncTraceServerFacade(FakeAsyncServer())
    close_thread_loop()


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


def test_async_generator_is_a_lazy_iterator(facade: SyncTraceServerFacade) -> None:
    it = facade.stream(3)
    assert next(it) == 0
    assert facade._inner.closed_streams == 0
    assert list(it) == [1, 2]
    assert facade._inner.closed_streams == 1


def test_abandoned_iterator_closes_the_generator(facade: SyncTraceServerFacade) -> None:
    it = facade.stream(10)
    next(it)
    it.close()
    assert facade._inner.closed_streams == 1


def test_one_loop_per_thread_reused_across_calls(facade: SyncTraceServerFacade) -> None:
    facade.read(1)
    facade.read(2)
    main_loops = set(facade._inner.loops)
    assert len(main_loops) == 1

    def other_thread() -> None:
        facade.read(3)
        close_thread_loop()

    t = threading.Thread(target=other_thread)
    t.start()
    t.join()
    assert len(set(facade._inner.loops)) == 2


def test_caller_context_is_visible_inside(facade: SyncTraceServerFacade) -> None:
    _request_tag.set("req-7")
    assert facade.tagged() == "req-7"


def test_refuses_to_run_inside_a_running_loop(facade: SyncTraceServerFacade) -> None:
    async def misuse() -> None:
        facade.read(1)

    with pytest.raises(RuntimeError, match="inside a running event loop"):
        asyncio.run(misuse())


def test_facade_defines_no_server_methods() -> None:
    """The async server is the only implementation; the facade only forwards."""
    own = {
        name
        for name, value in vars(SyncTraceServerFacade).items()
        if callable(value) and not name.startswith("_")
    }
    assert own == set()


def test_close_thread_loop_then_reuse(facade: SyncTraceServerFacade) -> None:
    facade.read(1)
    first = sync_facade.thread_loop()
    close_thread_loop()
    assert first.is_closed()
    assert facade.read(2) == 4
    assert sync_facade.thread_loop() is not first


def test_resolve_accepts_a_value_or_an_awaitable() -> None:
    async def later() -> int:
        return 3

    assert resolve(3) == 3
    assert resolve(later()) == 3
    close_thread_loop()


def test_thread_loops_share_one_default_executor() -> None:
    seen: list[str] = []

    async def where() -> None:
        seen.append(await asyncio.to_thread(lambda: threading.current_thread().name))

    def run() -> None:
        sync_facade.run_sync(where())
        close_thread_loop()

    threads = [threading.Thread(target=run) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(name.startswith("sync-facade") for name in seen), seen


def test_dead_threads_loops_are_reaped_and_their_sessions_closed(
    facade: SyncTraceServerFacade,
) -> None:
    """A pool thread exits without closing its loop; the next caller cleans up,
    running the server's aclose on the orphaned loop so its aiohttp session is
    drained on the loop that owns it.
    """
    orphan: dict[str, asyncio.AbstractEventLoop] = {}

    def use_and_exit() -> None:
        facade.read(1)
        orphan["loop"] = sync_facade.thread_loop()

    t = threading.Thread(target=use_and_exit)
    t.start()
    t.join()
    assert not orphan["loop"].is_closed()

    facade.read(2)  # any bridged call reaps
    assert orphan["loop"].is_closed()
    # Other tests' exited threads may be reaped in the same sweep.
    assert orphan["loop"] in facade._inner.closed_on
