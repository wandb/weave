"""Parallel fan-out for bucket uploads collected during a `call_batch`.

`ClickHouseTraceServer` accumulates `file_create` requests into a per-thread
buffer while `_flush_immediately=False` (see `call_batch()`). Without batching,
each bucket upload pays a serial round-trip to the storage provider; an
upsert_batch with M attachments paid `M * RTT` of wall time on a single
worker.

This module owns the deferred-upload buffer and the fan-out step:

    bucket_uploads = BucketUploadBatch()
    ...
    bucket_uploads.stage(req, digest)        # cheap, in-memory only
    ...
    rows = bucket_uploads.flush(client)      # parallel upload -> CH rows
    self._file_batch.extend(rows)

The `FileStorageClient` is supplied once at flush time rather than carried
on every staged item. The trace server's `file_storage_client` is per-
instance, so a batch only ever needs one.

`flush()` preserves per-file semantics from the original serial path: each
worker either uploads to the bucket or, on `FileStorageWriteError`, returns
inline ClickHouse chunks. The caller is responsible for inserting the
returned rows into the `files` table.

The batch is request-scoped (constructed and discarded per `call_batch`) so
the staging path needs no locking; only `flush()` spawns workers.

Partial-failure semantics: if a worker raises something other than
`FileStorageWriteError` (e.g. an unwrapped network error), `as_completed`
re-raises it and `flush()` logs a warning and re-raises. Peer workers
still complete via the `ThreadPoolExecutor.__exit__` join, so their
bucket objects may land without a corresponding `files` row. On retry,
the repeat write is an idempotent no-op (served from the per-pod
stored-key cache, or GCS `if_generation_match=0` swallows the duplicate)
and the worker re-inserts the missing `files` row. End state is
content-addressable and consistent.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import FileChunkCreateCHInsertable
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import RequestTooLarge
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageWriteError,
    key_for_project_digest,
    store_in_bucket,
)
from weave.trace_server.tracing import traced

logger = logging.getLogger(__name__)

# Hides GCS RTT (~60ms p50, ~150ms p95) without exhausting the per-pod
# google-cloud-storage HTTP session pool.
DEFAULT_BUCKET_UPLOAD_CONCURRENCY = 8

# Hard ceiling on bytes buffered in a single batch between stage() and
# flush(). The /call/* request-body cap is 32 MiB, so 256 MiB leaves 8x
# headroom for legitimate multi-attachment traffic while preventing a
# misbehaving client from OOMing the pod by stuffing one call_batch with
# huge file_create payloads.
MAX_BUCKET_UPLOAD_BATCH_BYTES = 256 * 1024 * 1024


@dataclass(slots=True)
class _Pending:
    req: tsi.FileCreateReq
    digest: str


class BucketUploadBatch:
    """Stages bucket uploads during a call_batch and flushes them in parallel.

    Single-threaded staging, parallel flush. Not thread-safe across threads.
    A bucket upload that fails with `FileStorageWriteError` falls back to
    inline ClickHouse chunks for that one file; other files are unaffected.
    """

    def __init__(self, max_bytes: int = MAX_BUCKET_UPLOAD_BATCH_BYTES) -> None:
        self._max_bytes = max_bytes
        self._pending: list[_Pending] = []
        self._seen: set[tuple[str, str]] = set()
        self._total_bytes = 0

    def stage(self, req: tsi.FileCreateReq, digest: str) -> None:
        """Defer a bucket upload until `flush()`.

        Caller computes the digest, validates `expected_digest`, and dedups
        against the in-flight ClickHouse chunk buffer. The caller MUST
        pre-check `has(project_id, digest)` and skip the call if it returns
        True; staging a duplicate would double-upload the same object and
        race on `if_generation_match=0`, so we raise instead of silently
        accepting it.

        Raises `RequestTooLarge` if accepting this item would push the
        batch over `max_bytes`. Bounds worst-case memory for a single
        call_batch so one client can't OOM the pod.
        """
        key = (req.project_id, digest)
        if key in self._seen:
            raise ValueError(
                f"BucketUploadBatch.stage() called twice for {key}; callers "
                "must pre-check via `has()` and skip duplicates."
            )
        size = len(req.content)
        if self._total_bytes + size > self._max_bytes:
            raise RequestTooLarge(
                f"BucketUploadBatch would exceed max_bytes={self._max_bytes}: "
                f"staged={self._total_bytes}, new={size}"
            )
        self._pending.append(_Pending(req=req, digest=digest))
        self._seen.add(key)
        self._total_bytes += size

    def has(self, project_id: str, digest: str) -> bool:
        """True if `(project_id, digest)` was already staged in this batch."""
        return (project_id, digest) in self._seen

    def __bool__(self) -> bool:
        return bool(self._pending)

    @traced(name="bucket_upload_batch.flush")
    def flush(
        self, client: FileStorageClient | None
    ) -> list[FileChunkCreateCHInsertable]:
        """Run staged uploads in parallel; return chunk rows for the caller to insert.

        Each pending upload becomes either a single bucket-URI chunk
        (success) or N inline ClickHouse chunks (FileStorageWriteError
        fallback). Order is not preserved.

        `client` must be non-None whenever items have been staged. The
        staging path is gated on a non-None client at the call site, so
        receiving None here would indicate a broken invariant rather than a
        valid empty-batch case.
        """
        if not self._pending:
            return []
        if client is None:
            raise RuntimeError(
                "BucketUploadBatch.flush() received None client but "
                f"{len(self._pending)} items were staged; staging is supposed "
                "to gate on a non-None client."
            )
        pending, self._pending = self._pending, []
        self._seen = set()
        self._total_bytes = 0

        rows: list[FileChunkCreateCHInsertable] = []
        bucket_success = 0
        ch_fallback = 0
        with ThreadPoolExecutor(
            max_workers=min(DEFAULT_BUCKET_UPLOAD_CONCURRENCY, len(pending)),
            thread_name_prefix="bucket-upload",
        ) as pool:
            futs = [pool.submit(_upload_one, p, client) for p in pending]
            try:
                for fut in as_completed(futs):
                    fut_rows = fut.result()
                    # Single bucket-URI row vs N inline-CH rows; we use the URI
                    # presence to classify the per-file outcome.
                    if fut_rows and fut_rows[0].file_storage_uri is not None:
                        bucket_success += 1
                    else:
                        ch_fallback += 1
                    rows.extend(fut_rows)
            except Exception:
                logger.warning(
                    "BucketUploadBatch worker raised an unwrapped exception; "
                    "peer uploads may have completed without a files row. "
                    "Retry will reconcile via if_generation_match=0.",
                    exc_info=True,
                )
                raise
        set_current_span_dd_tags(
            {
                "bucket_upload_batch.bucket_success": bucket_success,
                "bucket_upload_batch.ch_fallback": ch_fallback,
                "bucket_upload_batch.staged": len(pending),
            }
        )
        return rows


def _upload_one(
    p: _Pending, client: FileStorageClient
) -> list[FileChunkCreateCHInsertable]:
    try:
        uri = store_in_bucket(
            client, key_for_project_digest(p.req.project_id, p.digest), p.req.content
        )
    except FileStorageWriteError:
        return file_chunks_for(p.req, p.digest)
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


def file_chunks_for(
    req: tsi.FileCreateReq, digest: str
) -> list[FileChunkCreateCHInsertable]:
    """Split a file_create payload into inline ClickHouse chunk rows.

    Shared between the synchronous file_create path and the bucket-upload
    `FileStorageWriteError` fallback so the chunking shape stays in one place.
    """
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
