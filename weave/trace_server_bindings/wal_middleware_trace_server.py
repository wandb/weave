from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from typing_extensions import Self

from weave.trace.settings import write_ahead_log_dir
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.delegating_trace_server import (
    DelegatingTraceServerMixin,
)

_DEFAULT_WAL_FILE = "write_ahead_log.sqlite3"


def _compute_table_digest(row_digests: list[str]) -> str:
    table_hasher = hashlib.sha256()
    for row_digest in row_digests:
        table_hasher.update(row_digest.encode())
    return table_hasher.hexdigest()


class DurableWriteAheadLog:
    """Durable on-disk WAL for write-intent events.

    Design goals for this phase:
    1. Preserve current request/response behavior.
    2. Ensure every write-intent is durably recorded before network I/O.
    3. Track acknowledgement and failure metadata for future replay.

    This implementation is intentionally minimal: append + ack + failure-marking.
    Replay and backoff behavior are planned for the next phase.
    """

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        # Use SQLite WAL mode so appends and updates are crash-resilient and
        # readers can observe state while writes continue.
        conn.execute("PRAGMA journal_mode=WAL")
        # FULL sync to minimize acknowledged-but-not-durable risk on power loss.
        conn.execute("PRAGMA synchronous=FULL")
        # Give concurrent callers time to obtain the write lock instead of failing
        # immediately with "database is locked".
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            # Each row is a durable write-intent event.
            # `status` starts as pending and transitions to acked after a
            # successful remote write.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wal_events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    acked_at TEXT,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )
            conn.execute(
                """
                -- Query pattern for replay workers is expected to be:
                -- WHERE status='pending' ORDER BY created_at
                CREATE INDEX IF NOT EXISTS wal_events_status_created_at_idx
                ON wal_events(status, created_at)
                """
            )
            conn.commit()

    def append_event(self, event_type: str, project_id: str, payload_json: str) -> str:
        # `event_id` is an internal WAL identifier (not server-side idempotency key).
        event_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO wal_events (
                    event_id, created_at, event_type, project_id, payload_json, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                # New events are always pending until remote success is observed.
                (event_id, created_at, event_type, project_id, payload_json, "pending"),
            )
            conn.commit()
        return event_id

    def ack_event(self, event_id: str) -> None:
        # Ack is write-after-success: only called after remote write returns.
        acked_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE wal_events
                SET status = ?, acked_at = ?
                WHERE event_id = ?
                """,
                ("acked", acked_at, event_id),
            )
            conn.commit()

    def mark_event_failed(self, event_id: str, error: Exception) -> None:
        # Keep status as pending so replay can retry later.
        last_error = f"{type(error).__name__}: {error}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE wal_events
                SET error_count = error_count + 1, last_error = ?
                WHERE event_id = ?
                """,
                (last_error, event_id),
            )
            conn.commit()


class WriteAheadLogMiddlewareTraceServer(
    DelegatingTraceServerMixin, TraceServerClientInterface
):
    """Middleware that durably logs write intents around remote writes.

    This sits in front of the remote trace server and wraps selected write methods:
    - obj_create
    - table_create
    - table_create_from_digests
    - file_create

    Flow per write:
    1. Append WAL event as `pending`.
    2. Execute underlying remote write.
    3. On success: mark `acked`.
    4. On failure: increment failure metadata and leave `pending`.
    """

    _next_trace_server: TraceServerClientInterface
    delegated_methods = DelegatingTraceServerMixin.delegated_methods | {"server_info"}
    optional_delegated_methods = frozenset(
        {
            "get_call_processor",
            "get_feedback_processor",
        }
    )

    def __init__(
        self,
        next_trace_server: TraceServerClientInterface,
        wal_db_path: str | Path | None = None,
    ):
        self._next_trace_server = next_trace_server
        if wal_db_path is None:
            wal_db_path = Path(write_ahead_log_dir()) / _DEFAULT_WAL_FILE
        self._wal = DurableWriteAheadLog(wal_db_path)

    @classmethod
    def from_env(cls, next_trace_server: TraceServerClientInterface) -> Self:
        wal_db_path = Path(write_ahead_log_dir()) / _DEFAULT_WAL_FILE
        return cls(next_trace_server, wal_db_path)

    @property
    def wal_db_path(self) -> Path:
        return self._wal.db_path

    def _with_wal(
        self,
        *,
        event_type: str,
        project_id: str,
        payload_json: str,
        write_fn: Callable[[], Any],
    ) -> Any:
        if event_type == "":
            raise ValueError("event_type must be non-empty")

        # Durability first: record intent before touching the network.
        event_id = self._wal.append_event(
            event_type=event_type,
            project_id=project_id,
            payload_json=payload_json,
        )
        try:
            result = write_fn()
        except Exception as exc:
            # Failure does not remove the event; it remains pending for replay.
            self._wal.mark_event_failed(event_id, exc)
            raise
        # Success path: mark event as acknowledged.
        self._wal.ack_event(event_id)
        return result

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._with_wal(
            event_type="obj_create",
            project_id=req.obj.project_id,
            payload_json=req.model_dump_json(),
            write_fn=lambda: self._next_trace_server.obj_create(req),
        )

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._with_wal(
            event_type="table_create",
            project_id=req.table.project_id,
            payload_json=req.model_dump_json(),
            write_fn=lambda: self._next_trace_server.table_create(req),
        )

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        # For this request type we log an enriched payload with deterministic digest
        # so replay tooling can validate intent vs server response.
        payload_json = json.dumps(
            {
                "event_type": "table_create_from_digests",
                "project_id": req.project_id,
                "row_digests": req.row_digests,
                "digest": _compute_table_digest(req.row_digests),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return self._with_wal(
            event_type="table_create_from_digests",
            project_id=req.project_id,
            payload_json=payload_json,
            write_fn=lambda: self._next_trace_server.table_create_from_digests(req),
        )

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self._with_wal(
            event_type="file_create",
            project_id=req.project_id,
            payload_json=req.model_dump_json(),
            write_fn=lambda: self._next_trace_server.file_create(req),
        )
