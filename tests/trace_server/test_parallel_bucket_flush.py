"""Tests for the phase-0 parallel bucket-upload flush inside ``call_batch()``.

These tests exercise the deferred-PUT path added to ``ClickHouseTraceServer``:

  * ``_file_create_bucket`` queues an upload instead of running ``store_in_bucket``
    synchronously when we are inside a ``call_batch()`` (``_flush_immediately`` is
    ``False``).
  * ``_flush_pending_bucket_uploads`` fans the queued PUTs out across the
    shared ``ThreadPoolExecutor``, then appends a chunk record per success.
  * On per-digest failure the fallback re-routes that one digest through the
    ClickHouse-chunked write path, preserving the prior single-shot semantics.

Tests intentionally avoid the heavyweight ClickHouse fixtures — they patch
the low-level ``_mint_client`` and ``file_storage_client`` so they run as
plain unit tests without Docker.
"""

from __future__ import annotations

import base64
import threading
import time
from unittest.mock import MagicMock, patch

import ddtrace
import pytest

from weave.shared.digest import compute_file_digest
from weave.trace_server import clickhouse_trace_server_batched as cts_module
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import (
    _BUCKET_UPLOAD_POOL_MAX_WORKERS,
    ClickHouseTraceServer,
    _PendingBucketUpload,
)
from weave.trace_server.file_storage_uris import GCSFileStorageURI


def _make_project_id() -> str:
    return base64.b64encode(b"test_entity/test_project").decode("utf-8")


class _FakeStorageClient:
    """Minimal FileStorageClient stand-in: records every store call.

    Optionally sleeps to model GCS PUT latency (so parallel-vs-sequential
    tests are observable). The ``fail_paths`` set forces ``FileStorageWriteError``
    for any path in it, mirroring the wrapped exception ``store_in_bucket``
    raises in production.
    """

    def __init__(
        self,
        *,
        bucket: str = "wandb-weave-trace-prod",
        per_put_sleep: float = 0.0,
        fail_paths: set[str] | None = None,
    ):
        self.base_uri: GCSFileStorageURI = GCSFileStorageURI(bucket=bucket, path="")
        self._per_put_sleep = per_put_sleep
        self._fail_paths = fail_paths or set()
        self._store_lock = threading.Lock()
        self.store_calls: list[tuple[str, bytes]] = []

    def store(self, uri, data: bytes) -> None:
        with self._store_lock:
            self.store_calls.append((uri.path, data))
        if uri.path in self._fail_paths:
            raise RuntimeError(f"simulated bucket failure for {uri.path}")
        if self._per_put_sleep:
            time.sleep(self._per_put_sleep)


def _make_server(client: _FakeStorageClient) -> ClickHouseTraceServer:
    """Build a ClickHouseTraceServer with the heavy bits stubbed out.

    We need a real instance so the thread-local queues and the phase-0 flush
    behave like production; everything below that (ClickHouse insert, env
    lookups for ramp/allow-list) is mocked.
    """
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()
    mock_ch_client.query.return_value.result_rows = [[0, 1]]

    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        server = ClickHouseTraceServer(host="test_host")

    server._file_storage_client = client  # type: ignore[assignment]
    server._file_storage_client_initialized = True
    server._should_use_file_storage_for_writes = lambda project_id: True  # type: ignore[method-assign]
    # Pre-populate the thread-local CH client so `ch_client` doesn't try to
    # mint a real connection on first access.
    server._thread_local.ch_client = mock_ch_client
    server._mock_ch_client = mock_ch_client  # for inspection in tests
    return server


@pytest.fixture(autouse=True)
def _reset_pool() -> None:
    """The pool is process-wide and lazy-initialized; ensure a clean instance.

    Each test gets a fresh pool so ``thread_name_prefix`` and worker counts are
    deterministic and any future hot-path changes don't bleed between tests.
    """
    cts_module._bucket_upload_pool = None
    yield
    pool = cts_module._bucket_upload_pool
    if pool is not None:
        pool.shutdown(wait=True)
    cts_module._bucket_upload_pool = None


def test_pool_caps_workers_to_documented_default() -> None:
    """Regression guard: the documented default (8) must match the constant.

    The PR body claims an 8x speedup on the bucket phase based on this cap.
    If someone bumps the constant without coordinating the connection-pool
    bump, the speedup math no longer holds.
    """
    assert _BUCKET_UPLOAD_POOL_MAX_WORKERS == 8

    pool = cts_module._get_bucket_upload_pool()
    assert pool._max_workers == 8
    assert pool._thread_name_prefix == "bucket-put"


def test_file_create_outside_batch_keeps_synchronous_path() -> None:
    """One-shot ``file_create`` must not pay the pool-handoff cost.

    Outside of ``call_batch()`` there is exactly one PUT to do; routing it
    through the pool would just add task-handoff overhead. The PUT must
    happen on the calling thread.
    """
    client = _FakeStorageClient()
    server = _make_server(client)
    project_id = _make_project_id()

    server.file_create(
        tsi.FileCreateReq(project_id=project_id, name="x.bin", content=b"hello")
    )

    assert len(client.store_calls) == 1
    assert client.store_calls[0][1] == b"hello"
    assert server._pending_bucket_uploads == []


def test_call_batch_queues_uploads_then_flushes_in_parallel() -> None:
    """N PUTs inside one ``call_batch()`` must run concurrently on the pool.

    With per-PUT sleep T and pool size W, sequential wall is N*T whereas
    parallel wall is ceil(N/W)*T plus a small handoff overhead. We assert a
    speedup well above the worst-case handoff so a regression to the
    sequential path is loud (the assertion accommodates CI jitter).
    """
    n = 16
    per_put = 0.08
    client = _FakeStorageClient(per_put_sleep=per_put)
    server = _make_server(client)
    project_id = _make_project_id()

    contents = [f"payload-{i}".encode() * 200 for i in range(n)]

    t0 = time.monotonic()
    with server.call_batch():
        for i, content in enumerate(contents):
            server.file_create(
                tsi.FileCreateReq(
                    project_id=project_id, name=f"f{i}.bin", content=content
                )
            )
        # Before flush, PUTs are queued, not yet executed.
        assert len(client.store_calls) == 0
        assert len(server._pending_bucket_uploads) == n
    elapsed = time.monotonic() - t0

    # All N PUTs eventually issued exactly once.
    assert len(client.store_calls) == n
    # Queue is drained on flush.
    assert server._pending_bucket_uploads == []

    sequential_wall = n * per_put
    # Pool has 8 workers; even with handoff and CI variance the parallel wall
    # should be well under half the sequential equivalent.
    assert elapsed < sequential_wall * 0.5, (
        f"Expected parallel flush to be well under {sequential_wall:.2f}s; "
        f"got {elapsed:.2f}s — bucket PUTs may have regressed to sequential."
    )


def test_chunk_records_use_deterministic_uri_matching_post_upload() -> None:
    """The pre-computed URI we write to ``files`` must match the PUT target.

    The whole point of computing the URI from ``(project_id, digest)`` up front
    is that readers can resolve ``file_storage_uri`` without waiting for the
    PUT to finish. This test pins that invariant so a future rename of
    ``key_for_project_digest`` cannot silently diverge the two paths.
    """
    client = _FakeStorageClient()
    server = _make_server(client)
    project_id = _make_project_id()
    content = b"deterministic-uri-content" * 32
    digest = compute_file_digest(content)
    expected_path = f"weave/projects/{project_id}/files/{digest}"
    expected_uri = client.base_uri.with_path(expected_path).to_uri_str()

    with server.call_batch():
        server.file_create(
            tsi.FileCreateReq(project_id=project_id, name="d.bin", content=content)
        )

    assert any(path == expected_path for path, _ in client.store_calls)
    # The chunk in _file_batch is cleared post-flush; capture by snapshotting
    # the actual `insert` call to the `files` table from the mock CH client.
    files_inserts = [
        c
        for c in server._mock_ch_client.insert.call_args_list
        if c.args and c.args[0] == "files"
    ]
    assert files_inserts, "expected at least one insert into the files table"
    inserted_rows = files_inserts[-1].kwargs["data"]
    column_names = files_inserts[-1].kwargs["column_names"]
    uri_col_idx = column_names.index("file_storage_uri")
    inserted_uris = [row[uri_col_idx] for row in inserted_rows]
    assert expected_uri in inserted_uris


@pytest.mark.disable_logging_error_check
def test_failed_put_falls_back_to_clickhouse_for_that_digest_only() -> None:
    """A single PUT failure must not break the whole batch.

    Two files go in: one whose path is in ``fail_paths`` (raising during
    ``client.store``) and one healthy. The failed one must end up written as
    ClickHouse chunks (``file_storage_uri=None``); the healthy one keeps its
    bucket URI. This preserves the per-call fallback that the previous
    synchronous code path implemented via ``try/except FileStorageWriteError``.

    The ``disable_logging_error_check`` mark is intentional: the fallback path
    deliberately logs at ERROR level via ``logger.exception`` so operators see
    when a PUT failed. That's the contract we want to keep.
    """
    project_id = _make_project_id()
    bad_content = b"bad-content" * 10
    good_content = b"good-content" * 10
    bad_digest = compute_file_digest(bad_content)
    good_digest = compute_file_digest(good_content)
    bad_path = f"weave/projects/{project_id}/files/{bad_digest}"

    client = _FakeStorageClient(fail_paths={bad_path})
    server = _make_server(client)

    with server.call_batch():
        server.file_create(
            tsi.FileCreateReq(project_id=project_id, name="bad.bin", content=bad_content)
        )
        server.file_create(
            tsi.FileCreateReq(
                project_id=project_id, name="good.bin", content=good_content
            )
        )

    files_inserts = [
        c
        for c in server._mock_ch_client.insert.call_args_list
        if c.args and c.args[0] == "files"
    ]
    assert files_inserts, "expected an insert into files table"
    rows = files_inserts[-1].kwargs["data"]
    column_names = files_inserts[-1].kwargs["column_names"]
    digest_idx = column_names.index("digest")
    uri_idx = column_names.index("file_storage_uri")

    digest_to_uri: dict[str, list] = {}
    for row in rows:
        digest_to_uri.setdefault(row[digest_idx], []).append(row[uri_idx])

    assert good_digest in digest_to_uri
    assert all(u is not None for u in digest_to_uri[good_digest]), (
        "healthy digest must keep its bucket URI"
    )
    assert bad_digest in digest_to_uri
    assert all(u is None for u in digest_to_uri[bad_digest]), (
        "failed digest must fall back to ClickHouse chunks (uri=None)"
    )


def test_duplicate_digest_within_batch_uploads_once() -> None:
    """Pre-existing dedup against ``_file_batch`` must also cover the queue.

    Before this PR, dedup looked only at ``_file_batch``. Now the bucket
    chunk row is appended only post-flush, so a duplicate ``file_create`` for
    the same digest within one batch would have re-enqueued without this
    additional check against ``_pending_bucket_uploads``.
    """
    client = _FakeStorageClient()
    server = _make_server(client)
    project_id = _make_project_id()
    content = b"same-content" * 50

    with server.call_batch():
        for _ in range(5):
            server.file_create(
                tsi.FileCreateReq(
                    project_id=project_id, name="dup.bin", content=content
                )
            )

    assert len(client.store_calls) == 1, (
        "duplicate digests in one batch should collapse to a single bucket PUT"
    )


def test_ddtrace_context_propagates_to_worker_threads() -> None:
    """Child spans created inside a pool worker must stay on the parent trace.

    ddtrace 4.x tracks the active span through a ``ContextVar``, and we copy
    the caller's context into each worker. If that wiring breaks, child
    spans of the PUT path get re-parented to a synthetic root and we lose
    the per-request trace continuity that the DDtrace evidence relied on.

    Direct parent of the worker-thread span is the intermediate
    ``_flush_pending_bucket_uploads`` span (that's how ``@tracer.wrap`` works),
    so we assert ``trace_id`` continuity rather than direct ``parent_id``.
    """
    captured: list[tuple[int, int | None]] = []

    class _SpanCapturingClient(_FakeStorageClient):
        def store(self, uri, data: bytes) -> None:
            with ddtrace.tracer.trace("bucket.put_simulated") as span:
                captured.append((span.trace_id, span.parent_id))
            super().store(uri, data)

    client = _SpanCapturingClient()
    server = _make_server(client)
    project_id = _make_project_id()

    with ddtrace.tracer.trace("upsert_batch_test") as root_span:
        root_trace_id = root_span.trace_id
        with server.call_batch():
            for i in range(4):
                server.file_create(
                    tsi.FileCreateReq(
                        project_id=project_id,
                        name=f"t{i}.bin",
                        content=f"payload-{i}".encode() * 10,
                    )
                )

    assert len(captured) == 4
    trace_ids = {trace_id for trace_id, _ in captured}
    parent_ids = [parent_id for _, parent_id in captured]
    assert trace_ids == {root_trace_id}, (
        f"child PUT spans drifted to a different trace_id: got {trace_ids}, "
        f"expected only {root_trace_id}"
    )
    assert all(p is not None for p in parent_ids), (
        f"child PUT spans lost their parent linkage: {parent_ids}"
    )


def test_pending_uploads_helper_dataclass_is_immutable() -> None:
    """Sanity check: the queue items must be hashable / immutable.

    Treating the queue items as immutable rules out a class of bugs where a
    worker mutates the item after it's been picked up.
    """
    client = _FakeStorageClient()
    project_id = _make_project_id()
    content = b"x" * 16
    digest = compute_file_digest(content)
    item = _PendingBucketUpload(
        client=client,
        project_id=project_id,
        digest=digest,
        name="x.bin",
        content=content,
        target_uri=client.base_uri.with_path(f"weave/projects/{project_id}/files/{digest}"),
    )
    with pytest.raises(dataclasses_error()):
        item.digest = "mutated"  # type: ignore[misc]


def dataclasses_error() -> type[Exception]:
    """Return the exception type raised by frozen-dataclass setattr."""
    import dataclasses

    return dataclasses.FrozenInstanceError
