"""Unit tests for the BucketUploadBatch staging buffer.

Exercises the in-memory staging contract (dedup, size guard) without
spinning up the full ClickHouse server. The flush/fan-out path is covered
by the GCS-backed integration tests in tests/trace/test_server_file_storage.py.
"""

from __future__ import annotations

import threading
import time
from typing import cast

import pytest

from weave.trace_server import parallel_bucket_uploads as pbu
from weave.trace_server.clickhouse_schema import FileChunkCreateCHInsertable
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.file_storage import FileStorageClient, FileStorageWriteError
from weave.trace_server.parallel_bucket_uploads import BucketUploadBatch
from weave.trace_server.trace_server_interface import FileCreateReq

_FAKE_CLIENT = cast(FileStorageClient, object())


def _req(content: bytes, name: str = "f.bin") -> FileCreateReq:
    return FileCreateReq(project_id="entity/project", name=name, content=content)


def _success_row(p: pbu._Pending) -> list[FileChunkCreateCHInsertable]:
    """A bucket-upload success: one chunk row carrying a `file_storage_uri`."""
    return [
        FileChunkCreateCHInsertable(
            project_id=p.req.project_id,
            digest=p.digest,
            chunk_index=0,
            n_chunks=1,
            name=p.req.name,
            val_bytes=b"",
            bytes_stored=len(p.req.content),
            file_storage_uri="gs://bucket/key",
        )
    ]


def test_stage_dedup_raises_on_duplicate_key() -> None:
    batch = BucketUploadBatch()
    batch.stage(_req(b"hello"), digest="d1")
    with pytest.raises(ValueError, match="called twice"):
        batch.stage(_req(b"hello"), digest="d1")


def test_stage_rejects_when_total_exceeds_max_bytes() -> None:
    """One oversized payload trips the guard immediately."""
    batch = BucketUploadBatch(max_bytes=1024)
    with pytest.raises(RequestTooLarge, match="max_bytes=1024"):
        batch.stage(_req(b"x" * 2048), digest="d1")
    # Nothing was staged after the rejection.
    assert not batch
    assert not batch.has("entity/project", "d1")


def test_stage_rejects_when_cumulative_exceeds_max_bytes() -> None:
    """The guard accumulates across items, not just per-item."""
    batch = BucketUploadBatch(max_bytes=1024)
    batch.stage(_req(b"x" * 600), digest="d1")
    batch.stage(_req(b"y" * 400), digest="d2")
    with pytest.raises(RequestTooLarge):
        batch.stage(_req(b"z" * 100), digest="d3")
    # First two items remain staged; the rejected third is not.
    assert batch.has("entity/project", "d1")
    assert batch.has("entity/project", "d2")
    assert not batch.has("entity/project", "d3")


def test_duplicate_stage_does_not_consume_budget() -> None:
    """Dedup hits raise ValueError before incrementing the byte counter."""
    batch = BucketUploadBatch(max_bytes=1024)
    batch.stage(_req(b"x" * 600), digest="d1")
    with pytest.raises(ValueError, match="called twice"):
        batch.stage(_req(b"x" * 600), digest="d1")
    # Budget should still allow another 400 bytes.
    batch.stage(_req(b"y" * 400), digest="d2")


def test_flush_resets_byte_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """After flush(), staged bytes drop to zero so the next batch starts fresh."""
    monkeypatch.setattr(pbu, "_upload_one", lambda p, client: [])
    batch = BucketUploadBatch(max_bytes=1024)
    batch.stage(_req(b"x" * 900), digest="d1")
    batch.flush(client=_FAKE_CLIENT)
    batch.stage(_req(b"y" * 900), digest="d2")
    assert batch.has("entity/project", "d2")


def test_flush_trips_breaker_and_cancels_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead bucket (every upload falls back) bails after max_failures.

    Without the breaker each of the 100 files would burn a full tenacity
    retry before its inline-CH fallback. The breaker raises after the third
    fallback and cancels the uploads that have not started, so the vast
    majority of files are never attempted.
    """
    calls: list[str] = []
    lock = threading.Lock()

    def fake_upload(p: pbu._Pending, client: FileStorageClient) -> list:
        with lock:
            calls.append(p.digest)
        # Keep workers busy so cancel() has uploads left to cancel.
        time.sleep(0.02)
        return pbu.file_chunks_for(p.req, p.digest)  # inline-CH fallback

    monkeypatch.setattr(pbu, "_upload_one", fake_upload)
    batch = BucketUploadBatch(max_failures=3)
    for i in range(100):
        batch.stage(_req(b"x" * 8, name=f"f{i}.bin"), digest=f"d{i}")

    with pytest.raises(FileStorageWriteError, match="appears unavailable"):
        batch.flush(client=_FAKE_CLIENT)
    assert len(calls) < 100


def test_flush_below_threshold_falls_back_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolated failures under the ceiling still fall back inline, no raise."""

    def fake_upload(p: pbu._Pending, client: FileStorageClient) -> list:
        # Two files fail; the rest succeed -> under max_failures=3.
        if p.digest in {"d0", "d1"}:
            return pbu.file_chunks_for(p.req, p.digest)
        return _success_row(p)

    monkeypatch.setattr(pbu, "_upload_one", fake_upload)
    batch = BucketUploadBatch(max_failures=3)
    for i in range(10):
        batch.stage(_req(b"x" * 8, name=f"f{i}.bin"), digest=f"d{i}")

    rows = batch.flush(client=_FAKE_CLIENT)
    uris = [r for r in rows if r.file_storage_uri is not None]
    inline = [r for r in rows if r.file_storage_uri is None]
    assert len(uris) == 8
    assert len(inline) == 2
