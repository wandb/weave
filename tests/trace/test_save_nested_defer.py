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
from typing import Any

import pytest

import weave
from tests.trace.conftest import BlockingTraceServer, paused
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, OpRef, TableRef
from weave.trace.weave_client import (
    WeaveClient,
    _collect_pending_digests,
    _snapshot_mutable_containers,
)
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
    with paused(client) as c:
        out = step(m)
    assert out == {"x": 1}
    # The flush in `paused.__exit__` must drain. If we got here, no deadlock.


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
    with paused(client):
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

    blocker = BlockingTraceServer(client.server)
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
        f"Deferred walk captured a post-finish_call mutation: {recorded_output!r}"
    )


# ---------------------------------------------------------------------------
# _snapshot_mutable_containers: type preservation. Subclasses of dict/list/
# set/tuple must be returned by identity — rebuilding them as the bare type
# would strip subclass information the serializer needs (namedtuple field
# names, dict-subclass dataclass types like HuggingFace ChatCompletionOutput).
# ---------------------------------------------------------------------------


class TestSnapshotPreservesSubclassTypes:
    def test_plain_containers_are_rebuilt(self) -> None:
        # Plain dict/list/set/tuple at the top level get fresh copies so
        # post-finish mutations can't reach the deferred walk.
        d = {"k": [1, 2]}
        snap = _snapshot_mutable_containers(d)
        assert snap == d
        assert snap is not d
        assert snap["k"] is not d["k"]

    def test_namedtuple_preserved(self) -> None:
        from typing import NamedTuple

        class Point(NamedTuple):
            x: int
            y: int

        snap = _snapshot_mutable_containers(Point(1, 2))
        assert type(snap) is Point
        assert snap._asdict() == {"x": 1, "y": 2}

    def test_dict_subclass_preserved(self) -> None:
        from collections import Counter, OrderedDict

        c = Counter({"a": 1, "b": 2})
        snap_c = _snapshot_mutable_containers(c)
        assert type(snap_c) is Counter
        assert snap_c is c

        od = OrderedDict([("a", 1), ("b", 2)])
        snap_od = _snapshot_mutable_containers(od)
        assert type(snap_od) is OrderedDict
        assert snap_od is od

    def test_list_subclass_preserved(self) -> None:
        class MyList(list):
            pass

        ml = MyList([1, 2, 3])
        snap = _snapshot_mutable_containers(ml)
        assert type(snap) is MyList
        assert snap is ml

    def test_namedtuple_nested_in_list_preserved(self) -> None:
        # Mirrors test_namedtuple_support: list containing a namedtuple
        # should round-trip with the named fields intact.
        from typing import NamedTuple

        class Point(NamedTuple):
            x: int
            y: int

        snap = _snapshot_mutable_containers([Point(1, 2), 3])
        assert isinstance(snap, list)
        assert type(snap[0]) is Point
        assert snap[0]._asdict() == {"x": 1, "y": 2}


class TestSnapshotSharedReferences:
    """Aliased mutable containers must be snapshotted, not deduped to the original.

    `_snapshot_mutable_containers` uses an `id(obj) in _seen` check for cycle
    protection. The same check also collapses non-cyclic shared references:
    the first occurrence of an aliased list/dict gets a fresh copy, but the
    second occurrence returns the ORIGINAL by identity. A caller mutating the
    returned value after `finish_call` then leaks into the deferred walk for
    every alias past the first — exactly the failure mode the snapshot is
    supposed to close.
    """

    def test_shared_list_aliased_in_dict_is_fully_snapshotted(self) -> None:
        shared = [1, 2]
        out = {"a": shared, "b": shared}
        snap = _snapshot_mutable_containers(out)

        # Caller mutates the value they got back from `finish_call`.
        shared.append(99)

        # Both aliases in the snapshot must reflect the pre-mutation value.
        # Today: `snap["a"]` is a fresh copy and stays `[1, 2]`, but
        # `snap["b"]` is the original (dedup'd via `_seen`) and is now
        # `[1, 2, 99]`.
        assert snap["a"] == [1, 2]
        assert snap["b"] == [1, 2], (
            "Aliased reference returned the original instead of a snapshot: "
            f"snap['b']={snap['b']!r}. The deferred walk would record a "
            "post-finish_call mutation under the second alias."
        )

    def test_shared_list_aliased_in_tuple_is_fully_snapshotted(self) -> None:
        shared = [1, 2]
        snap = _snapshot_mutable_containers((shared, shared))

        shared.append(99)

        assert snap[0] == [1, 2]
        assert snap[1] == [1, 2], (
            f"Aliased reference inside tuple leaked the mutation: snap[1]={snap[1]!r}"
        )

    def test_shared_dict_aliased_in_list_is_fully_snapshotted(self) -> None:
        shared = {"x": 1}
        snap = _snapshot_mutable_containers([shared, shared])

        shared["x"] = 99

        assert snap[0] == {"x": 1}
        assert snap[1] == {"x": 1}, (
            f"Aliased dict inside list leaked the mutation: snap[1]={snap[1]!r}"
        )

    def test_cycle_terminates_and_is_independent_of_original(self) -> None:
        # Snapshot must terminate on a cyclic structure AND the cycle in the
        # snapshot must not refer back to the original (otherwise post-snapshot
        # mutations of the original would leak into the cycle).
        a: list = [1]
        a.append(a)

        snap = _snapshot_mutable_containers(a)

        a.append("post-snapshot")
        assert snap[0] == 1
        assert snap[1] is snap, (
            "snapshot cycle should close on itself, not the original"
        )
        assert "post-snapshot" not in snap, (
            f"snapshot reflects post-snapshot mutation of the original: {snap!r}"
        )
