"""Unit tests for BucketUploadBatch.

These cover the contract the surrounding clickhouse_trace_server_batched
code relies on: staging dedup, parallel flush, per-file ClickHouse fallback,
and that a single hard failure is surfaced to the caller.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.file_storage import (
    FileStorageClient,
)
from weave.trace_server.file_storage_uris import GCSFileStorageURI
from weave.trace_server.parallel_bucket_uploads import BucketUploadBatch

PROJECT_ID = "u/p"


class _FakeClient(FileStorageClient):
    """Records uploads, optionally delays, optionally raises by path.

    `base_uri` is set on the abstract base. `store()` is what we observe.
    """

    def __init__(
        self,
        *,
        delay: float = 0.0,
        fail_paths: set[str] | None = None,
    ) -> None:
        super().__init__(GCSFileStorageURI("bucket", ""))
        self._delay = delay
        self._fail_paths = fail_paths or set()
        self._lock = threading.Lock()
        self.calls: list[tuple[str, bytes]] = []
        self.concurrent_peak = 0
        self._inflight = 0

    def store(self, uri, data: bytes) -> None:
        with self._lock:
            self._inflight += 1
            self.concurrent_peak = max(self.concurrent_peak, self._inflight)
        try:
            if uri.path in self._fail_paths:
                raise RuntimeError(f"injected failure for {uri.path}")
            if self._delay:
                time.sleep(self._delay)
            with self._lock:
                self.calls.append((uri.path, data))
        finally:
            with self._lock:
                self._inflight -= 1

    def read(self, uri):
        raise NotImplementedError


def _req(name: str, content: bytes) -> tsi.FileCreateReq:
    return tsi.FileCreateReq(project_id=PROJECT_ID, name=name, content=content)


@pytest.fixture
def client() -> Iterator[_FakeClient]:
    return _FakeClient()


def test_empty_flush_returns_no_rows() -> None:
    batch = BucketUploadBatch()
    assert batch.is_empty
    assert batch.flush() == []


def test_single_upload_emits_one_bucket_chunk(client: _FakeClient) -> None:
    batch = BucketUploadBatch()
    batch.stage(_req("a", b"data"), digest="d1", client=client)

    rows = batch.flush()

    assert len(rows) == 1
    row = rows[0]
    assert row.project_id == PROJECT_ID
    assert row.digest == "d1"
    assert row.chunk_index == 0
    assert row.n_chunks == 1
    assert row.val_bytes == b""
    assert row.bytes_stored == 4
    assert row.file_storage_uri is not None
    assert row.file_storage_uri.startswith("gs://bucket/")
    # batch is consumed
    assert batch.is_empty
    assert not batch.has(PROJECT_ID, "d1")


def test_has_tracks_staged_digests_for_dedup() -> None:
    batch = BucketUploadBatch()
    fc = _FakeClient()
    assert not batch.has(PROJECT_ID, "d")
    batch.stage(_req("a", b"x"), digest="d", client=fc)
    assert batch.has(PROJECT_ID, "d")
    assert not batch.has(PROJECT_ID, "other")


def test_flush_runs_uploads_in_parallel() -> None:
    # Each upload sleeps 100ms; with 5 uploads and max_workers=5, wall time
    # should be well under the 500ms a serial run would take.
    delay = 0.1
    n = 5
    client = _FakeClient(delay=delay)
    batch = BucketUploadBatch(max_workers=n)
    for i in range(n):
        batch.stage(_req(f"a{i}", f"v{i}".encode()), digest=f"d{i}", client=client)

    start = time.monotonic()
    rows = batch.flush()
    elapsed = time.monotonic() - start

    assert len(rows) == n
    assert client.concurrent_peak == n
    # A serial run would take >= n*delay (0.5s). Allow generous slack for CI.
    assert elapsed < (n * delay) * 0.6, f"flush was not parallel: {elapsed:.3f}s"


@pytest.mark.disable_logging_error_check
def test_failed_upload_falls_back_to_clickhouse_chunks() -> None:
    client = _FakeClient(fail_paths={f"weave/projects/{PROJECT_ID}/files/bad"})
    batch = BucketUploadBatch()
    batch.stage(_req("ok", b"ok-data"), digest="ok", client=client)
    batch.stage(_req("bad", b"bad-data"), digest="bad", client=client)

    rows_by_digest: dict[str, list] = {}
    for row in batch.flush():
        rows_by_digest.setdefault(row.digest, []).append(row)

    # Successful upload: one chunk with a bucket URI, no inline bytes.
    [ok] = rows_by_digest["ok"]
    assert ok.file_storage_uri is not None
    assert ok.val_bytes == b""

    # Failed upload: inline CH chunks, no URI.
    bad = rows_by_digest["bad"]
    assert all(r.file_storage_uri is None for r in bad)
    assert b"".join(r.val_bytes for r in bad) == b"bad-data"


@pytest.mark.disable_logging_error_check
def test_large_failed_upload_chunks_match_clickhouse_path() -> None:
    # Force the CH fallback path to actually chunk by exceeding FILE_CHUNK_SIZE.
    payload = b"x" * (ch_settings.FILE_CHUNK_SIZE * 2 + 7)
    failing = _FakeClient(fail_paths={f"weave/projects/{PROJECT_ID}/files/big"})
    batch = BucketUploadBatch()
    batch.stage(_req("big", payload), digest="big", client=failing)

    rows = batch.flush()
    rows.sort(key=lambda r: r.chunk_index)

    assert [r.chunk_index for r in rows] == [0, 1, 2]
    assert all(r.n_chunks == 3 for r in rows)
    assert b"".join(r.val_bytes for r in rows) == payload


def test_max_workers_capped_at_pending_count() -> None:
    # If the user picks an oversized worker count, we shouldn't allocate
    # more threads than pending tasks.
    client = _FakeClient()
    batch = BucketUploadBatch(max_workers=64)
    for i in range(2):
        batch.stage(_req(f"a{i}", b"v"), digest=f"d{i}", client=client)
    batch.flush()
    assert client.concurrent_peak <= 2


def test_flush_after_reset_is_independent() -> None:
    client = _FakeClient()
    batch = BucketUploadBatch()
    batch.stage(_req("a", b"v"), digest="d1", client=client)
    batch.flush()

    # Reusing the same batch should not double-process the prior staging.
    batch.stage(_req("b", b"v2"), digest="d2", client=client)
    rows = batch.flush()
    assert [r.digest for r in rows] == ["d2"]
