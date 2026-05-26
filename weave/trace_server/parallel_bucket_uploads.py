"""Parallel fan-out for bucket uploads collected during a `call_batch`.

`ClickHouseTraceServer` accumulates `file_create` requests into a per-thread
buffer while `_flush_immediately=False` (see `call_batch()`). Without batching,
each bucket upload pays a serial round-trip to the storage provider; an
upsert_batch with M attachments paid `M * RTT` of wall time on a single
worker.

This module owns the deferred-upload buffer and the fan-out step:

    bucket_uploads = BucketUploadBatch()
    ...
    bucket_uploads.stage(req, digest, client)   # cheap, in-memory only
    ...
    rows = bucket_uploads.flush()               # parallel upload -> CH rows
    self._file_batch.extend(rows)

`flush()` preserves per-file semantics from the original serial path: each
worker either uploads to the bucket or, on `FileStorageWriteError`, returns
inline ClickHouse chunks. The caller is responsible for inserting the
returned rows into the `files` table.

The batch is request-scoped (constructed and discarded per `call_batch`) so
the staging path needs no locking; only `flush()` spawns workers.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import ddtrace

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import FileChunkCreateCHInsertable
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageWriteError,
    key_for_project_digest,
    store_in_bucket,
)

# Hides GCS RTT (~60ms p50, ~150ms p95) without exhausting the per-pod
# google-cloud-storage HTTP session pool.
DEFAULT_BUCKET_UPLOAD_CONCURRENCY = 8


@dataclass(slots=True)
class _Pending:
    req: tsi.FileCreateReq
    digest: str
    client: FileStorageClient


class BucketUploadBatch:
    """Stages bucket uploads during a call_batch and flushes them in parallel.

    Single-threaded staging, parallel flush. Not thread-safe across threads.
    A bucket upload that fails with `FileStorageWriteError` falls back to
    inline ClickHouse chunks for that one file; other files are unaffected.
    """

    def __init__(self, max_workers: int = DEFAULT_BUCKET_UPLOAD_CONCURRENCY) -> None:
        self._max_workers = max_workers
        self._pending: list[_Pending] = []
        self._seen: set[tuple[str, str]] = set()

    def stage(
        self,
        req: tsi.FileCreateReq,
        digest: str,
        client: FileStorageClient,
    ) -> None:
        """Defer a bucket upload until `flush()`.

        Caller computes the digest, validates `expected_digest`, and dedups
        against the in-flight ClickHouse chunk buffer. Within-batch dedup
        across bucket uploads is tracked here via `has()`.
        """
        self._pending.append(_Pending(req=req, digest=digest, client=client))
        self._seen.add((req.project_id, digest))

    def has(self, project_id: str, digest: str) -> bool:
        """True if `(project_id, digest)` was already staged in this batch."""
        return (project_id, digest) in self._seen

    @property
    def is_empty(self) -> bool:
        return not self._pending

    @ddtrace.tracer.wrap(name="bucket_upload_batch.flush")
    def flush(self) -> list[FileChunkCreateCHInsertable]:
        """Run staged uploads in parallel; return chunk rows for the caller to insert.

        Each pending upload becomes either a single bucket-URI chunk
        (success) or N inline ClickHouse chunks (FileStorageWriteError
        fallback). Order is not preserved.
        """
        if not self._pending:
            return []
        pending, self._pending = self._pending, []
        self._seen = set()

        rows: list[FileChunkCreateCHInsertable] = []
        with ThreadPoolExecutor(
            max_workers=min(self._max_workers, len(pending)),
            thread_name_prefix="bucket-upload",
        ) as pool:
            futs = [pool.submit(_upload_one, p) for p in pending]
            for fut in as_completed(futs):
                rows.extend(fut.result())
        return rows


def _upload_one(p: _Pending) -> list[FileChunkCreateCHInsertable]:
    try:
        uri = store_in_bucket(
            p.client, key_for_project_digest(p.req.project_id, p.digest), p.req.content
        )
    except FileStorageWriteError:
        return _clickhouse_chunks(p.req, p.digest)
    return [
        FileChunkCreateCHInsertable(
            project_id=p.req.project_id,
            digest=p.digest,
            chunk_index=0,
            n_chunks=1,
            name=p.req.name,
            val_bytes=b"",
            bytes_stored=len(p.req.content),
            file_storage_uri=uri.to_uri_str(),
        )
    ]


def _clickhouse_chunks(
    req: tsi.FileCreateReq, digest: str
) -> list[FileChunkCreateCHInsertable]:
    pieces = [
        req.content[i : i + ch_settings.FILE_CHUNK_SIZE]
        for i in range(0, len(req.content), ch_settings.FILE_CHUNK_SIZE)
    ]
    return [
        FileChunkCreateCHInsertable(
            project_id=req.project_id,
            digest=digest,
            chunk_index=i,
            n_chunks=len(pieces),
            name=req.name,
            val_bytes=chunk,
            bytes_stored=len(chunk),
            file_storage_uri=None,
        )
        for i, chunk in enumerate(pieces)
    ]
