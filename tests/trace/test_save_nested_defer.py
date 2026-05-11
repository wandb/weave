"""Tests for the deferred-output structural fix.

Covers:
1. `_collect_pending_digests` — pre-walk that finds unresolved digest futures.
2. The `then(...)`-chained `_save_object_basic` path (no worker block on digest).
3. The deferred `send_end_call` (Phase 1 + Phase 2) doesn't deadlock under
   high concurrency or paused-server scenarios.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import Future
from contextlib import contextmanager
from typing import Any

import pytest

import weave
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, OpRef, TableRef
from weave.trace.weave_client import WeaveClient, _collect_pending_digests
from weave.trace_server import trace_server_interface as tsi


def _make_pending_future() -> Future[str]:
    f: Future[str] = Future()
    return f


def _make_resolved_future(value: str) -> Future[str]:
    f: Future[str] = Future()
    f.set_result(value)
    return f


# ---------------------------------------------------------------------------
# _collect_pending_digests: unit tests over arbitrary value shapes.
# These don't touch the client; they verify the pre-walk that gates `to_json`
# from blocking inside a worker thread.
# ---------------------------------------------------------------------------


class TestCollectPendingDigests:
    def test_primitives_return_empty(self) -> None:
        assert _collect_pending_digests(None) == []
        assert _collect_pending_digests("hello") == []
        assert _collect_pending_digests(42) == []
        assert _collect_pending_digests(3.14) == []
        assert _collect_pending_digests(True) == []

    def test_containers_of_primitives_return_empty(self) -> None:
        assert _collect_pending_digests([]) == []
        assert _collect_pending_digests([1, 2, "a"]) == []
        assert _collect_pending_digests((1, 2)) == []
        assert _collect_pending_digests({}) == []
        assert _collect_pending_digests({"a": 1, "b": [2, 3]}) == []
        assert _collect_pending_digests({"nested": {"deep": {"value": 1}}}) == []

    def test_object_ref_with_resolved_digest_returns_empty(self) -> None:
        ref = ObjectRef(entity="e", project="p", name="obj", _digest="resolved-digest")
        assert _collect_pending_digests(ref) == []

    def test_object_ref_with_pending_digest_is_collected(self) -> None:
        pending = _make_pending_future()
        ref = ObjectRef(entity="e", project="p", name="obj", _digest=pending)
        assert _collect_pending_digests(ref) == [pending]

    def test_object_ref_with_resolved_future_treated_as_pending_caller_handles(
        self,
    ) -> None:
        # Done futures are skipped — the caller will read `.result()` without
        # blocking, so we don't need the `then(...)` gate.
        f = _make_resolved_future("done")
        ref = ObjectRef(entity="e", project="p", name="obj", _digest=f)
        assert _collect_pending_digests(ref) == []

    def test_table_ref_collects_both_digest_and_row_digests(self) -> None:
        digest = _make_pending_future()
        row_digests: Future[list[str]] = Future()
        ref = TableRef(
            entity="e", project="p", _digest=digest, _row_digests=row_digests
        )
        result = _collect_pending_digests(ref)
        assert digest in result
        assert row_digests in result
        assert len(result) == 2

    def test_op_ref_collected(self) -> None:
        pending = _make_pending_future()
        ref = OpRef(entity="e", project="p", name="my_op", _digest=pending)
        assert _collect_pending_digests(ref) == [pending]

    def test_dict_with_nested_pending_ref(self) -> None:
        pending = _make_pending_future()
        ref = ObjectRef(entity="e", project="p", name="obj", _digest=pending)
        val = {"a": 1, "obj": ref, "nested": {"more": [ref]}}
        # Cycle protection: ref appears twice but is collected once.
        result = _collect_pending_digests(val)
        assert result == [pending]

    def test_list_and_tuple_walk(self) -> None:
        p1 = _make_pending_future()
        p2 = _make_pending_future()
        r1 = ObjectRef(entity="e", project="p", name="o1", _digest=p1)
        r2 = ObjectRef(entity="e", project="p", name="o2", _digest=p2)
        result = _collect_pending_digests([r1, (r2, 42)])
        assert set(result) == {p1, p2}

    def test_object_record_walked_via_dunder_dict(self) -> None:
        pending = _make_pending_future()
        ref = ObjectRef(entity="e", project="p", name="child", _digest=pending)
        # Build an ObjectRecord whose __dict__ contains a ref.
        rec = ObjectRecord({"_class_name": "Parent", "child_ref": ref, "n": 7})
        assert _collect_pending_digests(rec) == [pending]

    def test_cycle_is_handled(self) -> None:
        # Build a self-referential structure. Walk must not infinite loop.
        pending = _make_pending_future()
        ref = ObjectRef(entity="e", project="p", name="obj", _digest=pending)
        cycle: dict[str, Any] = {"ref": ref}
        cycle["self"] = cycle
        result = _collect_pending_digests(cycle)
        assert result == [pending]

    def test_does_not_recurse_into_resolved_ref_extras(self) -> None:
        # A Ref is a leaf; its `_extra` etc. shouldn't trigger nested walks.
        ref = ObjectRef(
            entity="e",
            project="p",
            name="obj",
            _digest="d",
            _extra=("attr", "foo"),
        )
        assert _collect_pending_digests(ref) == []


# ---------------------------------------------------------------------------
# Integration: under paused-server (the deadlock fixture from
# test_evaluation_performance), a basic op chain must complete cleanly at
# default executor parallelism. Master without the structural fix deadlocks
# here when the deferred `_save_nested_objects` is present.
# ---------------------------------------------------------------------------


class _BlockingTraceServer(tsi.TraceServerInterface):
    """Server proxy that holds a lock; while paused, all proxied calls block."""

    def __init__(self, inner: tsi.TraceServerInterface):
        self._inner = inner
        self._lock = threading.Lock()

    def pause(self) -> None:
        self._lock.acquire()

    def resume(self) -> None:
        self._lock.release()

    def __getattribute__(self, item: str) -> Any:
        if item in {"_inner", "_lock", "pause", "resume"}:
            return super().__getattribute__(item)
        inner = super().__getattribute__("_inner")
        if item in {"attribute_access_log", "remote_request_bytes_limit"}:
            return getattr(inner, item)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                return getattr(inner, item)(*args, **kwargs)

        return wrapper


@contextmanager
def _paused(client: WeaveClient):
    original = client.server
    client.set_autoflush(False)
    blocker = _BlockingTraceServer(original)
    client.server = blocker
    blocker.pause()
    try:
        yield client
    finally:
        blocker.resume()
        client.server = original
        client._flush()
        client.set_autoflush(True)


def test_paused_server_does_not_deadlock_on_finish(client: WeaveClient) -> None:
    """A traced op finishes while server is paused; flush drains cleanly.

    Reproduces the failure mode that motivated the structural fix: with the
    naive deferred `_save_nested_objects`, multiple concurrent `send_end_call`
    workers all end up blocking inside `to_json -> digest.result()`, exhausting
    the worker pool and deadlocking the post-resume flush. Here the chain is
    short (one op), but `_save_object_basic` for the input pydantic model
    builds the same digest-future dependency that the gate must release.
    """

    class Model(weave.Object):  # type: ignore[name-defined]
        x: int = 0

    @weave.op
    def step(m: Model) -> dict:
        return {"x": m.x}

    m = Model(x=1)
    with _paused(client) as c:
        out = step(m)
    assert out == {"x": 1}
    # The flush in `_paused.__exit__` must drain. If we got here, no deadlock.


@pytest.mark.asyncio
async def test_concurrent_finishes_drain(client: WeaveClient) -> None:
    """Many concurrent op finishes drain via the then-chain without deadlock.

    Stresses the `then(pending, finalize)` path: each op's input is a pydantic
    Object whose digest is pending while the server is paused; releasing the
    pause must let every pending finalize_send fire and `_flush()` return.
    """

    class Item(weave.Object):  # type: ignore[name-defined]
        i: int = 0

    @weave.op
    async def do(item: Item) -> int:
        return item.i * 2

    items = [Item(i=k) for k in range(20)]
    with _paused(client):
        results = await asyncio.gather(*(do(item) for item in items))
    assert results == [k * 2 for k in range(20)]


class _CallEndRaisingServer:
    """Server proxy that raises `RuntimeError` from `call_end`.

    Plain class (no `TraceServerInterface` subclass) so `__getattr__`
    forwards every other method to the inner server — subclassing the
    interface would resolve abstract methods via MRO and never reach
    `__getattr__`.
    """

    def __init__(self, inner: tsi.TraceServerInterface) -> None:
        self._inner = inner

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    def call_end(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("simulated call_end failure")


@pytest.mark.disable_logging_error_check
def test_call_end_error_is_logged(
    client: WeaveClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Errors raised by `server.call_end` in the deferred Phase 2 must surface
    as a "Task failed" log line via `_track_future`'s logger.

    Regression guard: an earlier draft tracked the barrier future with
    `log_exception=False`, which silently swallowed `call_end` errors. If
    that flips back, the assertion below fails.
    """

    @weave.op
    def f(x: int) -> int:
        return x + 1

    original = client.server
    client.server = _CallEndRaisingServer(original)
    try:
        with caplog.at_level(logging.ERROR):
            f(1)
            client._flush()
    finally:
        client.server = original

    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "Task failed" in m and "simulated call_end failure" in m for m in messages
    ), f"Expected 'Task failed' log with our error; got: {messages}"


def test_finish_call_returns_before_send(client: WeaveClient) -> None:
    """`finish_call` should not block on the deferred work.

    Verifies the perf goal: `_save_nested_objects` and `to_json` no longer
    run on the calling thread. We measure by holding the server lock and
    timing `finish_call`'s own return.
    """

    @weave.op
    def f(x: int) -> int:
        return x + 1

    blocker = _BlockingTraceServer(client.server)
    client.server = blocker
    client.set_autoflush(False)
    blocker.pause()
    try:
        t0 = time.perf_counter()
        f(1)  # full op: create_call + body + finish_call
        elapsed = time.perf_counter() - t0
        # Generous bound: the calling thread does sync work for create_call's
        # `_save_nested_objects(inputs)` plus the body, but finish_call should
        # have deferred everything else. 500ms is a sanity ceiling, not a perf
        # goal -- anything under "obviously waiting on the server" is enough.
        assert elapsed < 0.5, f"finish_call appears to block: {elapsed:.3f}s"
    finally:
        blocker.resume()
        client.server = blocker._inner
        client._flush()
        client.set_autoflush(True)


class _CapturingTraceServer:
    """Server proxy that captures `call_end` requests for inspection.

    Plain class (not a `TraceServerInterface` subclass) so `__getattr__`
    forwards every other method to the inner server, matching the pattern
    used by `_CallEndRaisingServer`.
    """

    def __init__(self, inner: tsi.TraceServerInterface) -> None:
        self._inner = inner
        self.captured: list[tsi.CallEndReq] = []

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    def call_end(self, req: tsi.CallEndReq) -> Any:
        self.captured.append(req)
        return self._inner.call_end(req)


def test_output_mutation_after_finish_is_not_recorded(client: WeaveClient) -> None:
    """Mutating a returned mutable output after `finish_call` must not change
    what the server records (regression for PR #6740 review concern).

    Output-side `_save_nested_objects` / `map_to_refs` / `to_json` are
    deferred to a worker, and the deferred walk reads `postprocessed_output`
    by reference. A caller that mutates the value between `finish_call`
    returning and the worker running would see their post-call mutation
    recorded as if it happened during the op:

        @weave.op
        def func(): return {"result": [1]}

        res = func()
        res["result"].append(2)   # should NOT change the recorded output

    To remove the timing race we gate `client._save_nested_objects` on the
    output-side call (call #2 -- call #1 is `create_call` for inputs, sync
    on the main thread). The mutation lands before the gate releases, so we
    deterministically observe what the deferred walk captures. Autoflush is
    disabled so the test-client's per-method `_flush` does not block on the
    gated worker.
    """

    @weave.op
    def func() -> dict:
        return {"result": [1]}

    # Capture call_end at the server boundary -- avoids depending on the
    # test fixture's caching/recorder stack to round-trip the value.
    capturing = _CapturingTraceServer(client.server)
    client.server = capturing

    gate = threading.Event()
    save_calls = {"n": 0}
    original_save = client._save_nested_objects

    def patched_save(obj: Any, name: str | None = None) -> Any:
        save_calls["n"] += 1
        if save_calls["n"] >= 2:  # output path inside `schedule_send`
            gate.wait()
        return original_save(obj, name=name)

    client._save_nested_objects = patched_save  # type: ignore[method-assign]
    client.set_autoflush(False)
    try:
        res = func()
        assert res == {"result": [1]}
        res["result"].append(2)
        gate.set()
        client._flush()
    finally:
        client.set_autoflush(True)
        client._save_nested_objects = original_save  # type: ignore[method-assign]
        client.server = capturing._inner

    assert len(capturing.captured) == 1
    recorded_output = capturing.captured[0].end.output
    assert recorded_output == {"result": [1]}, (
        "Deferred walk captured a post-finish_call mutation: "
        f"{recorded_output!r}"
    )
