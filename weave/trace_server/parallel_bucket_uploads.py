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
the same `(project_id, digest)` triggers
`if_generation_match=0 -> PreconditionFailed`, which `store_in_bucket`
wraps as `FileStorageWriteError`, which falls back to inline-CH chunks.
End state is content-addressable and consistent.

Circuit breaker: an isolated `FileStorageWriteError` falls back to inline-CH
chunks for that one file. But a dead bucket fails every file the same way,
and each upload independently burns `store_in_bucket`'s tenacity retries
(3 attempts, exponential backoff) before falling back, so a 100-file batch
grinds through ~N/workers serial waves of backoff for a backend that is
plainly down. After `max_failures` fallbacks in one batch, `flush()` stops
draining results, cancels the uploads that have not started, and raises so
the request fails fast instead of paying the full retry cost for every file.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import ddtrace

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

# Circuit-breaker threshold: how many per-file bucket failures we tolerate in
# one batch before declaring the storage backend down and failing the request.
# A live bucket fails the odd file (transient 5xx) and the inline-CH fallback
# absorbs it; a dead bucket fails every file, so a low ceiling bails after one
# wave of workers instead of retrying all N.
MAX_BUCKET_UPLOAD_FAILURES = 3


_UploadRows = list[FileChunkCreateCHInsertable]


@dataclass(slots=True)
class _Pending:
    req: tsi.FileCreateReq
    digest: str


@dataclass(slots=True)
class _FlushOutcome:
    """Running tally of one flush(): collected rows + per-file classification."""

    rows: _UploadRows = field(default_factory=list)
    bucket_success: int = 0
    ch_fallback: int = 0
    breaker_tripped: bool = False


class BucketUploadBatch:
    """Stages bucket uploads during a call_batch and flushes them in parallel.

    Single-threaded staging, parallel flush. Not thread-safe across threads.
    A bucket upload that fails with `FileStorageWriteError` falls back to
    inline ClickHouse chunks for that one file; other files are unaffected.
    Once `max_failures` files fall back in one batch the backend is treated as
    down and `flush()` raises instead of retrying the remainder.
    """

    def __init__(
        self,
        max_bytes: int = MAX_BUCKET_UPLOAD_BATCH_BYTES,
        max_failures: int = MAX_BUCKET_UPLOAD_FAILURES,
    ) -> None:
        self._max_bytes = max_bytes
        self._max_failures = max_failures
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

    @ddtrace.tracer.wrap(name="bucket_upload_batch.flush")
    def flush(
        self, client: FileStorageClient | None
    ) -> list[FileChunkCreateCHInsertable]:
        """Run staged uploads in parallel; return chunk rows for the caller to insert.

        Each pending upload becomes either a single bucket-URI chunk
        (success) or N inline ClickHouse chunks (FileStorageWriteError
        fallback). Order is not preserved.

        Raises `FileStorageWriteError` if `max_failures` uploads fall back in
        one batch: the storage backend looks down, so we cancel the not-yet-
        started uploads and fail the request instead of retrying every file.

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

        with ThreadPoolExecutor(
            max_workers=min(DEFAULT_BUCKET_UPLOAD_CONCURRENCY, len(pending)),
            thread_name_prefix="bucket-upload",
        ) as pool:
            futs = [pool.submit(_upload_one, p, client) for p in pending]
            try:
                outcome = self._collect(futs)
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
                "bucket_upload_batch.bucket_success": outcome.bucket_success,
                "bucket_upload_batch.ch_fallback": outcome.ch_fallback,
                "bucket_upload_batch.staged": len(pending),
                "bucket_upload_batch.breaker_tripped": outcome.breaker_tripped,
            }
        )
        if outcome.breaker_tripped:
            raise FileStorageWriteError(
                f"Bucket uploads failed {outcome.ch_fallback} times in a single "
                f"batch of {len(pending)} files; bailing instead of retrying the "
                "rest (storage backend appears unavailable)."
            )
        return outcome.rows

    def _collect(self, futs: list[Future[_UploadRows]]) -> _FlushOutcome:
        """Drain completed uploads, classifying each as bucket-URI or fallback.

        Trips the circuit breaker once `max_failures` files fall back: cancels
        the uploads that have not started so the rest of the batch doesn't each
        burn a full tenacity retry, and signals the caller to fail the request.
        """
        outcome = _FlushOutcome()
        for fut in as_completed(futs):
            fut_rows = fut.result()
            # Single bucket-URI row vs N inline-CH rows; URI presence
            # classifies the per-file outcome.
            if fut_rows and fut_rows[0].file_storage_uri is not None:
                outcome.bucket_success += 1
            else:
                outcome.ch_fallback += 1
            outcome.rows.extend(fut_rows)
            if outcome.ch_fallback >= self._max_failures:
                for f in futs:
                    f.cancel()
                outcome.breaker_tripped = True
                break
        return outcome


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
