"""Unit tests for the BucketUploadBatch staging buffer.

Exercises the in-memory staging contract (dedup, size guard) without
spinning up the full ClickHouse server. The flush/fan-out path is covered
by the GCS-backed integration tests in tests/trace/test_server_file_storage.py.
"""

from __future__ import annotations

from typing import cast

import pytest

from weave.trace_server import parallel_bucket_uploads as pbu
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.file_storage import FileStorageClient
from weave.trace_server.parallel_bucket_uploads import BucketUploadBatch
from weave.trace_server.trace_server_interface import FileCreateReq


def _req(content: bytes, name: str = "f.bin") -> FileCreateReq:
    return FileCreateReq(project_id="entity/project", name=name, content=content)


def test_stage_size_guard_and_dedup() -> None:
    """stage() enforces dedup and the cumulative byte budget."""
    # Duplicate key raises and does not consume budget (raise precedes counter bump).
    batch = BucketUploadBatch(max_bytes=1024)
    batch.stage(_req(b"x" * 600), digest="d1")
    with pytest.raises(ValueError, match="called twice"):
        batch.stage(_req(b"x" * 600), digest="d1")
    batch.stage(_req(b"y" * 400), digest="d2")  # budget still allows 400 more

    # One oversized payload trips the guard immediately; nothing is staged.
    batch = BucketUploadBatch(max_bytes=1024)
    with pytest.raises(RequestTooLarge, match="max_bytes=1024"):
        batch.stage(_req(b"x" * 2048), digest="d1")
    assert not batch
    assert not batch.has("entity/project", "d1")

    # The guard accumulates across items, not just per-item.
    batch = BucketUploadBatch(max_bytes=1024)
    batch.stage(_req(b"x" * 600), digest="d1")
    batch.stage(_req(b"y" * 400), digest="d2")
    with pytest.raises(RequestTooLarge):
        batch.stage(_req(b"z" * 100), digest="d3")
    assert batch.has("entity/project", "d1")
    assert batch.has("entity/project", "d2")
    assert not batch.has("entity/project", "d3")


def test_flush_resets_byte_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """After flush(), staged bytes drop to zero so the next batch starts fresh."""
    monkeypatch.setattr(pbu, "_upload_one", lambda p, client: [])
    batch = BucketUploadBatch(max_bytes=1024)
    batch.stage(_req(b"x" * 900), digest="d1")
    batch.flush(client=cast(FileStorageClient, object()))
    batch.stage(_req(b"y" * 900), digest="d2")
    assert batch.has("entity/project", "d2")
