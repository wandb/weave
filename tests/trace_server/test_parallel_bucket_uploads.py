"""Unit tests for the BucketUploadBatch staging buffer.

Exercises the in-memory staging contract (dedup, size guard) without
spinning up the full ClickHouse server. The flush/fan-out path is covered
by the GCS-backed integration tests in tests/trace/test_server_file_storage.py.
"""

from __future__ import annotations

from typing import cast

import pytest

from weave.trace_server import parallel_bucket_uploads as pbu
from weave.trace_server.clickhouse_schema import FileChunkCreateCHInsertable
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.file_storage import FileStorageClient
from weave.trace_server.parallel_bucket_uploads import BucketUploadBatch
from weave.trace_server.trace_server_interface import FileCreateReq


def _req(content: bytes, name: str = "f.bin") -> FileCreateReq:
    return FileCreateReq(project_id="entity/project", name=name, content=content)


def _bucket_row(p: pbu._Pending) -> FileChunkCreateCHInsertable:
    return FileChunkCreateCHInsertable(
        project_id=p.req.project_id,
        digest=p.digest,
        chunk_index=0,
        n_chunks=1,
        name=p.req.name,
        val_bytes=b"",
        bytes_stored=len(p.req.content),
        file_storage_uri="gs://bucket/x",
    )


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
    batch.flush(client=cast(FileStorageClient, object()))
    batch.stage(_req(b"y" * 900), digest="d2")
    assert batch.has("entity/project", "d2")


def test_pending_keys_reflects_staged_items() -> None:
    batch = BucketUploadBatch()
    batch.stage(_req(b"a"), digest="d1")
    batch.stage(_req(b"b"), digest="d2")
    assert batch.pending_keys() == [
        ("entity/project", "d1"),
        ("entity/project", "d2"),
    ]


def test_flush_skips_already_stored_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """already_stored keys are neither uploaded nor emit a chunk row; the rest
    upload normally.
    """
    uploaded: list[str] = []
    monkeypatch.setattr(
        pbu,
        "_upload_one",
        lambda p, client: uploaded.append(p.digest) or [_bucket_row(p)],
    )
    batch = BucketUploadBatch()
    batch.stage(_req(b"a"), digest="d1")
    batch.stage(_req(b"b"), digest="d2")
    rows = batch.flush(
        client=cast(FileStorageClient, object()),
        already_stored=frozenset({("entity/project", "d1")}),
    )
    assert uploaded == ["d2"]
    assert [r.digest for r in rows] == ["d2"]


def test_flush_all_already_stored_uploads_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When every staged key is already stored, flush uploads nothing and returns
    no rows (and must not build a zero-worker pool).
    """
    uploaded: list[str] = []
    monkeypatch.setattr(
        pbu,
        "_upload_one",
        lambda p, client: uploaded.append(p.digest) or [_bucket_row(p)],
    )
    batch = BucketUploadBatch()
    batch.stage(_req(b"a"), digest="d1")
    rows = batch.flush(
        client=cast(FileStorageClient, object()),
        already_stored=frozenset({("entity/project", "d1")}),
    )
    assert uploaded == []
    assert rows == []
