"""Stress tests for publish→ref.get() under the read-after-write race.

These tests exist to reproduce and diagnose the NotFoundError flake observed
on ClickHouse-backed CI runs (e.g. test_published_dataset_laziness).  They
are opt-in via `--run-stress` and assume the `client` fixture's underlying
trace server is a ClickHouseTraceServer.

Instrumentation:
- post_insert_probe: right after obj_create returns, count rows in
  object_versions for (project_id, object_id, digest).  If this is 0, the
  write-side is broken and retries on read will never help.
- on_not_found_probe: when obj_read is about to raise NotFoundError, capture
  counts by project / object / digest and a small sample of existing rows,
  plus a re-issue with a short sleep to see if the row becomes visible.

Tests bisect the race:
(a) sequential hammer — if this flakes, the race is single-threaded.
(b) concurrent per-thread — if (a) passes but this flakes, the race is at
    the CH container / HTTP-pool level.
(c) cross-thread handoff — if (b) passes but this flakes, read-side session
    sees a different view than write-side session.
(d) explicit flush — same as (a) but with client.flush() between publish
    and get.  If (a) flakes and (d) doesn't, autoflush isn't actually
    waiting for inserts.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import pytest

import weave
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import NotFoundError

logger = logging.getLogger(__name__)

# Sized so a full run finishes in roughly a minute even on a loaded runner,
# while still amortizing enough publish/get cycles to catch a rare race.
SEQUENTIAL_ITERATIONS = 500
CONCURRENT_THREADS = 8
CONCURRENT_ITERATIONS_PER_THREAD = 50
CROSS_THREAD_ITERATIONS = 200

# How long to wait before re-issuing obj_read inside the on-NotFound probe.
# Short enough that the test still finishes; long enough to distinguish a
# permanent miss from a transient visibility lag.
PROBE_RETRY_DELAY_SECONDS = 1.0


@dataclass
class StressMetrics:
    """Per-iteration record for post-run analysis."""

    iteration: int
    thread_id: int
    digest: str
    publish_ms: float
    get_ms: float
    post_insert_visible: int  # rows matching (project, object, digest) after obj_create
    failed: bool = False
    error: str = ""
    probe: dict[str, Any] = field(default_factory=dict)


def _find_clickhouse_server(client) -> ClickHouseTraceServer | None:
    """Walk the client.server chain to find the underlying ClickHouseTraceServer.

    Chain: ServerRecorder → CachingMiddlewareTraceServer → UserInjectingExternalTraceServer
           → ClickHouseTraceServer.  Attribute names differ at each layer.
    """
    seen: set[int] = set()
    candidates = [client.server]
    while candidates:
        node = candidates.pop()
        if id(node) in seen or node is None:
            continue
        seen.add(id(node))
        if isinstance(node, ClickHouseTraceServer):
            return node
        for attr in ("server", "_next_trace_server", "_internal_trace_server"):
            nxt = getattr(node, attr, None)
            if nxt is not None:
                candidates.append(nxt)
    return None


def _probe_count(
    ch: ClickHouseTraceServer, project_id: str, object_id: str, digest: str
) -> int:
    query = (
        "SELECT count() FROM object_versions "
        "WHERE project_id = {project_id: String} "
        "  AND object_id = {object_id: String} "
        "  AND digest = {digest: String}"
    )
    res = ch.ch_client.query(
        query,
        parameters={
            "project_id": project_id,
            "object_id": object_id,
            "digest": digest,
        },
    )
    return int(res.result_rows[0][0]) if res.result_rows else 0


def _probe_on_not_found(
    ch: ClickHouseTraceServer, project_id: str, object_id: str, digest: str
) -> dict[str, Any]:
    """Capture the state of object_versions at the moment of a NotFoundError."""
    query = (
        "SELECT "
        "countIf(project_id = {project_id: String}) AS all_project, "
        "countIf(project_id = {project_id: String} AND object_id = {object_id: String}) AS by_object, "
        "countIf(project_id = {project_id: String} AND object_id = {object_id: String} AND digest = {digest: String}) AS by_digest, "
        "countIf(object_id = {object_id: String} AND digest = {digest: String}) AS digest_any_project, "
        "arraySlice(groupArray((project_id, object_id, digest)), 1, 5) AS sample "
        "FROM object_versions "
        "WHERE project_id = {project_id: String} OR digest = {digest: String}"
    )
    rows = ch.ch_client.query(
        query,
        parameters={
            "project_id": project_id,
            "object_id": object_id,
            "digest": digest,
        },
    ).result_rows
    if not rows:
        return {"probe_error": "no rows from count query"}
    all_project, by_object, by_digest, digest_any_project, sample = rows[0]

    # Distinguish permanent misses from transient visibility lag.
    time.sleep(PROBE_RETRY_DELAY_SECONDS)
    retry_by_digest = _probe_count(ch, project_id, object_id, digest)

    return {
        "database": ch._database,
        "all_project": int(all_project),
        "by_object": int(by_object),
        "by_digest": int(by_digest),
        "digest_any_project": int(digest_any_project),
        "sample": list(sample)[:5],
        "retry_by_digest_after_sleep": retry_by_digest,
    }


@pytest.fixture
def ch_probe(client) -> Generator[dict[str, Any], None, None]:
    """Install post-insert and on-NotFound probes on the underlying CH server.

    Test-only.  Does not touch product code.  Captures per-call state so the
    test body can correlate a failing ref.get() back to what was (or wasn't)
    in the table at the moment of the failure.
    """
    ch = _find_clickhouse_server(client)
    if ch is None:
        pytest.skip("stress tests require ClickHouse backend")

    # Keyed by digest so threads don't step on each other.
    state: dict[str, Any] = {
        "last_insert_visible": {},  # digest → count
        "not_found_dumps": [],  # list of probe dicts
    }

    original_obj_create = ch.obj_create
    original_obj_read = ch.obj_read

    def probed_obj_create(req):
        res = original_obj_create(req)
        try:
            count = _probe_count(ch, req.obj.project_id, req.obj.object_id, res.digest)
            state["last_insert_visible"][res.digest] = count
            if count == 0:
                logger.error(
                    "POST_INSERT_PROBE miss: project=%s object=%s digest=%s count=0",
                    req.obj.project_id,
                    req.obj.object_id,
                    res.digest,
                )
        except Exception as exc:
            logger.warning("post_insert probe failed: %s", exc)
        return res

    def probed_obj_read(req):
        try:
            return original_obj_read(req)
        except NotFoundError:
            dump = _probe_on_not_found(ch, req.project_id, req.object_id, req.digest)
            dump.update(
                {
                    "project_id": req.project_id,
                    "object_id": req.object_id,
                    "digest": req.digest,
                    "thread_id": threading.get_ident(),
                }
            )
            state["not_found_dumps"].append(dump)
            logger.exception("ON_NOT_FOUND_PROBE %s", dump)
            raise

    ch.obj_create = probed_obj_create  # type: ignore[method-assign]
    ch.obj_read = probed_obj_read  # type: ignore[method-assign]
    try:
        yield state
    finally:
        ch.obj_create = original_obj_create  # type: ignore[method-assign]
        ch.obj_read = original_obj_read  # type: ignore[method-assign]


def _publish_one(index: int, thread_marker: str) -> tuple[Any, str, float, float]:
    """Publish a uniquely-contented Dataset and return (ref, digest, publish_ms, get_ms)."""
    # Unique content per iteration defeats the obj_create response cache and
    # keeps each run's digest distinct, so cross-iteration interference is
    # ruled out by construction.
    content_id = str(uuid.uuid4())
    dataset = weave.Dataset(rows=[{"i": index, "t": thread_marker, "id": content_id}])
    t0 = time.perf_counter()
    ref = weave.publish(dataset, name=f"stress_{thread_marker}_{index}")
    t1 = time.perf_counter()
    # Force digest materialization before timing the get.
    digest = ref.digest
    t2 = time.perf_counter()
    ref.get()
    t3 = time.perf_counter()
    return ref, digest, (t1 - t0) * 1000, (t3 - t2) * 1000


def _summarize(metrics: list[StressMetrics]) -> str:
    total = len(metrics)
    fails = [m for m in metrics if m.failed]
    lines = [f"stress summary: {len(fails)}/{total} failed"]
    for m in fails[:10]:
        lines.append(
            f"  iter={m.iteration} thread={m.thread_id} digest={m.digest[:12]} "
            f"post_insert={m.post_insert_visible} probe={m.probe} err={m.error[:200]}"
        )
    return "\n".join(lines)


@pytest.mark.stress
@pytest.mark.trace_server
def test_sequential_publish_get_hammer(client, ch_probe):
    """Bisect (a): single-threaded, unique content, autoflush on.

    Mirrors test_published_dataset_laziness' publish→get pattern but at scale.
    Failure here narrows the race to the main-thread flush path.
    """
    metrics: list[StressMetrics] = []
    for i in range(SEQUENTIAL_ITERATIONS):
        tid = threading.get_ident()
        try:
            _, digest, pub_ms, get_ms = _publish_one(i, "seq")
            metrics.append(
                StressMetrics(
                    iteration=i,
                    thread_id=tid,
                    digest=digest,
                    publish_ms=pub_ms,
                    get_ms=get_ms,
                    post_insert_visible=ch_probe["last_insert_visible"].get(digest, -1),
                )
            )
        except Exception as exc:
            probe = (
                ch_probe["not_found_dumps"][-1] if ch_probe["not_found_dumps"] else {}
            )
            metrics.append(
                StressMetrics(
                    iteration=i,
                    thread_id=tid,
                    digest="",
                    publish_ms=0.0,
                    get_ms=0.0,
                    post_insert_visible=-1,
                    failed=True,
                    error=repr(exc),
                    probe=probe,
                )
            )
    failures = [m for m in metrics if m.failed]
    assert not failures, _summarize(metrics)


@pytest.mark.stress
@pytest.mark.trace_server
def test_concurrent_publish_get_per_thread(client, ch_probe):
    """Bisect (b): N threads each do their own publish+get independently.

    Each thread has its own publish_one() call graph, so its publish and
    subsequent get both run on the same thread.  The shared state is the
    ClickHouse container (HTTP pool, server-side resources).
    """
    metrics: list[StressMetrics] = []
    lock = threading.Lock()

    def worker(thread_idx: int) -> None:
        for i in range(CONCURRENT_ITERATIONS_PER_THREAD):
            tid = threading.get_ident()
            try:
                _, digest, pub_ms, get_ms = _publish_one(i, f"ct{thread_idx}")
                with lock:
                    metrics.append(
                        StressMetrics(
                            iteration=i,
                            thread_id=tid,
                            digest=digest,
                            publish_ms=pub_ms,
                            get_ms=get_ms,
                            post_insert_visible=ch_probe["last_insert_visible"].get(
                                digest, -1
                            ),
                        )
                    )
            except Exception as exc:
                with lock:
                    probe = (
                        ch_probe["not_found_dumps"][-1]
                        if ch_probe["not_found_dumps"]
                        else {}
                    )
                    metrics.append(
                        StressMetrics(
                            iteration=i,
                            thread_id=tid,
                            digest="",
                            publish_ms=0.0,
                            get_ms=0.0,
                            post_insert_visible=-1,
                            failed=True,
                            error=repr(exc),
                            probe=probe,
                        )
                    )

    with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as ex:
        futures = [ex.submit(worker, i) for i in range(CONCURRENT_THREADS)]
        for f in as_completed(futures):
            f.result()

    failures = [m for m in metrics if m.failed]
    assert not failures, _summarize(metrics)


@pytest.mark.stress
@pytest.mark.trace_server
def test_cross_thread_publish_then_get(client, ch_probe):
    """Bisect (c): publish on thread A, ref.get() on thread B.

    If (b) passes and this fails, the read-side session (different thread,
    different thread-local ch_client) isn't seeing the write-side's commit
    promptly.  Uses a barrier so the get fires as close to the publish
    completion as possible.
    """
    metrics: list[StressMetrics] = []
    lock = threading.Lock()

    def run_one(i: int) -> None:
        content_id = str(uuid.uuid4())
        dataset = weave.Dataset(rows=[{"i": i, "id": content_id}])
        barrier = threading.Barrier(2)
        ref_box: dict[str, Any] = {}
        err_box: dict[str, Exception] = {}

        def publisher() -> None:
            try:
                ref = weave.publish(dataset, name=f"stress_xt_{i}")
                _ = ref.digest  # materialize digest future
                ref_box["ref"] = ref
            finally:
                barrier.wait()

        def getter() -> None:
            barrier.wait()
            try:
                ref_box["ref"].get()
            except Exception as exc:
                err_box["err"] = exc

        t_pub = threading.Thread(target=publisher)
        t_get = threading.Thread(target=getter)
        t_pub.start()
        t_get.start()
        t_pub.join()
        t_get.join()

        digest = ref_box.get("ref").digest if "ref" in ref_box else ""
        failed = "err" in err_box
        with lock:
            probe = (
                ch_probe["not_found_dumps"][-1]
                if failed and ch_probe["not_found_dumps"]
                else {}
            )
            metrics.append(
                StressMetrics(
                    iteration=i,
                    thread_id=threading.get_ident(),
                    digest=digest,
                    publish_ms=0.0,
                    get_ms=0.0,
                    post_insert_visible=ch_probe["last_insert_visible"].get(digest, -1),
                    failed=failed,
                    error=repr(err_box.get("err", "")) if failed else "",
                    probe=probe,
                )
            )

    for i in range(CROSS_THREAD_ITERATIONS):
        run_one(i)

    failures = [m for m in metrics if m.failed]
    assert not failures, _summarize(metrics)


@pytest.mark.stress
@pytest.mark.trace_server
def test_sequential_publish_flush_get(client, ch_probe):
    """Bisect (d): same as (a) but with explicit client.flush() between
    publish and get.

    If (a) flakes and this passes, autoflush isn't actually waiting for
    inserts.  If both flake, flush timing isn't the cause.
    """
    metrics: list[StressMetrics] = []
    for i in range(SEQUENTIAL_ITERATIONS):
        tid = threading.get_ident()
        content_id = str(uuid.uuid4())
        try:
            dataset = weave.Dataset(rows=[{"i": i, "id": content_id}])
            t0 = time.perf_counter()
            ref = weave.publish(dataset, name=f"stress_flush_{i}")
            digest = ref.digest
            client.flush()
            t1 = time.perf_counter()
            ref.get()
            t2 = time.perf_counter()
            metrics.append(
                StressMetrics(
                    iteration=i,
                    thread_id=tid,
                    digest=digest,
                    publish_ms=(t1 - t0) * 1000,
                    get_ms=(t2 - t1) * 1000,
                    post_insert_visible=ch_probe["last_insert_visible"].get(digest, -1),
                )
            )
        except Exception as exc:
            probe = (
                ch_probe["not_found_dumps"][-1] if ch_probe["not_found_dumps"] else {}
            )
            metrics.append(
                StressMetrics(
                    iteration=i,
                    thread_id=tid,
                    digest="",
                    publish_ms=0.0,
                    get_ms=0.0,
                    post_insert_visible=-1,
                    failed=True,
                    error=repr(exc),
                    probe=probe,
                )
            )
    failures = [m for m in metrics if m.failed]
    assert not failures, _summarize(metrics)
