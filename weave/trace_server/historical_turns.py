"""Durable commit coordination for idempotent historical turn ingest.

The commit store is deliberately separate from span storage. A span backend is
eligible only when it supplies a storage-level compare-and-set keyed by the
project and logical key. A replayed PUT invokes that same CAS after a crash;
GET status performs only a read-only evidence lookup and journal finalize.
Neither an expiring journal lease nor a query-before-insert check authorizes a
write. There is intentionally no best-effort ClickHouse fallback.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from weave.trace_server.agents.historical_turn_validation import (
    HISTORICAL_TURN_CAPABILITY_VERSION,
    HISTORICAL_TURN_SCHEMA_VERSION,
    MAX_HISTORICAL_TURN_ENVELOPE_BYTES,
    MAX_HISTORICAL_TURN_LOGICAL_KEY_BYTES,
    MAX_HISTORICAL_TURN_SPANS,
    HistoricalTurnCapabilityMismatchError,
    canonical_json_bytes,
    validate_prepared_turn,
)
from weave.trace_server.agents.types import (
    HistoricalTurnCapabilitiesReq,
    HistoricalTurnCapabilitiesRes,
    HistoricalTurnStatusReq,
    HistoricalTurnStatusRes,
    HistoricalTurnUpsertReq,
    HistoricalTurnUpsertRes,
    PreparedTurn,
)

DEFAULT_HISTORICAL_TURN_RECOVERY_LEASE_SECONDS = 30


class HistoricalTurnCommitError(RuntimeError):
    """A historical turn could not be committed safely."""


class HistoricalTurnUnsupportedError(HistoricalTurnCommitError):
    """The configured trace server lacks a durable historical-turn backend."""


@dataclass(frozen=True, slots=True)
class HistoricalTurnCommitRecord:
    project_id: str
    logical_key: str
    wire_sha256: str
    status: Literal["committing", "committed"]
    commit_id: str
    storage_row_key: str | None
    trace_ids: tuple[str, ...]
    root_span_ids: tuple[str, ...]
    span_count: int
    last_error: str | None


@dataclass(frozen=True, slots=True)
class HistoricalTurnClaim:
    outcome: Literal["acquired", "busy", "replayed", "conflict"]
    record: HistoricalTurnCommitRecord
    lease_token: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalTurnWriterResult:
    """Evidence returned by the span store's linearizable CAS."""

    outcome: Literal["created", "replayed", "conflict"]
    storage_row_key: str
    wire_sha256: str
    trace_ids: tuple[str, ...]
    root_span_ids: tuple[str, ...]
    span_count: int


@dataclass(frozen=True, slots=True)
class HistoricalTurnStoredRow:
    """Read-only evidence for an already-visible immutable storage row."""

    storage_row_key: str
    wire_sha256: str
    trace_ids: tuple[str, ...]
    root_span_ids: tuple[str, ...]
    span_count: int


class HistoricalTurnCommitStore(Protocol):
    """Linearizable logical-key journal required by historical ingest."""

    def claim(
        self,
        *,
        project_id: str,
        turn: PreparedTurn,
        lease_seconds: int,
    ) -> HistoricalTurnClaim: ...

    def mark_committed(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        lease_token: str,
        storage_row_key: str,
    ) -> HistoricalTurnCommitRecord: ...

    def note_error(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        lease_token: str,
        error_code: str,
    ) -> None: ...

    def reconcile_committed(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        storage_row_key: str,
    ) -> HistoricalTurnCommitRecord: ...

    def adopt_storage_commit(
        self,
        *,
        project_id: str,
        logical_key: str,
        stored_row: HistoricalTurnStoredRow,
    ) -> HistoricalTurnCommitRecord: ...

    def get(
        self, *, project_id: str, logical_key: str
    ) -> HistoricalTurnCommitRecord | None: ...


class HistoricalTurnWriter(Protocol):
    """Linearizable span-storage CAS used behind the commit journal.

    The unique immutable row key must be enforced by the storage engine. An
    existing row with the same digest returns ``replayed``; a different digest
    returns ``conflict``. The complete turn becomes visible atomically. This
    operation is the only write primitive. Status reconciliation uses the
    read-only evidence lookup and can never create a storage row.
    """

    def put_if_absent(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        complete_row: PreparedTurn,
        wb_user_id: str | None,
    ) -> HistoricalTurnWriterResult: ...

    def get_existing(
        self, *, project_id: str, logical_key: str
    ) -> HistoricalTurnStoredRow | None: ...


class SQLiteHistoricalTurnCommitStore:
    """File-backed SQLite commit journal for local servers and tests.

    SQLite's ``BEGIN IMMEDIATE`` plus the composite primary key serializes
    claims across processes. The database is chmod 0600 because hashes and
    trace identifiers are user metadata. ``:memory:`` is rejected: opening a
    new connection per transaction is part of the cross-thread safety model,
    and an in-memory database would also defeat crash recovery.
    """

    _SCHEMA_VERSION = 2

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        if str(path) == ":memory:":
            raise ValueError("historical turn commit state must be file-backed")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def claim(
        self,
        *,
        project_id: str,
        turn: PreparedTurn,
        lease_seconds: int,
    ) -> HistoricalTurnClaim:
        now_ns = time.time_ns()
        lease_expires_ns = now_ns + lease_seconds * 1_000_000_000
        lease_token = secrets.token_hex(16)
        commit_id = _commit_id(project_id, turn.logical_key)
        trace_ids_json = _dump_ids([turn.trace_id])
        root_span_ids_json = _dump_ids([turn.root_span_id])
        with self._transaction() as conn:
            row = conn.execute(
                """
                SELECT project_id, logical_key, wire_sha256, status, commit_id,
                       storage_row_key, trace_ids_json, root_span_ids_json,
                       span_count, last_error, lease_expires_ns
                FROM historical_turn_commits
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, turn.logical_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO historical_turn_commits (
                        project_id, logical_key, wire_sha256, status, commit_id,
                        storage_row_key, trace_ids_json, root_span_ids_json,
                        span_count, last_error, lease_token,
                        lease_expires_ns, created_at_ns, updated_at_ns
                    ) VALUES (?, ?, ?, 'committing', ?, NULL, ?, ?, ?, NULL, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        turn.logical_key,
                        turn.wire_sha256,
                        commit_id,
                        trace_ids_json,
                        root_span_ids_json,
                        turn.span_count,
                        lease_token,
                        lease_expires_ns,
                        now_ns,
                        now_ns,
                    ),
                )
                record = HistoricalTurnCommitRecord(
                    project_id=project_id,
                    logical_key=turn.logical_key,
                    wire_sha256=turn.wire_sha256,
                    status="committing",
                    commit_id=commit_id,
                    storage_row_key=None,
                    trace_ids=(turn.trace_id,),
                    root_span_ids=(turn.root_span_id,),
                    span_count=turn.span_count,
                    last_error=None,
                )
                return HistoricalTurnClaim("acquired", record, lease_token)

            record = _record_from_row(row)
            if record.wire_sha256 != turn.wire_sha256:
                return HistoricalTurnClaim("conflict", record)
            if (
                record.trace_ids != (turn.trace_id,)
                or record.root_span_ids != (turn.root_span_id,)
                or record.span_count != turn.span_count
            ):
                return HistoricalTurnClaim("conflict", record)
            if record.status == "committed":
                return HistoricalTurnClaim("replayed", record)
            if int(row[10]) > now_ns:
                return HistoricalTurnClaim("busy", record)

            conn.execute(
                """
                UPDATE historical_turn_commits
                SET lease_token = ?, lease_expires_ns = ?, updated_at_ns = ?,
                    last_error = NULL
                WHERE project_id = ? AND logical_key = ? AND wire_sha256 = ?
                  AND status = 'committing'
                """,
                (
                    lease_token,
                    lease_expires_ns,
                    now_ns,
                    project_id,
                    turn.logical_key,
                    turn.wire_sha256,
                ),
            )
            return HistoricalTurnClaim("acquired", record, lease_token)

    def mark_committed(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        lease_token: str,
        storage_row_key: str,
    ) -> HistoricalTurnCommitRecord:
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE historical_turn_commits
                SET status = 'committed', lease_token = NULL,
                    lease_expires_ns = 0, last_error = NULL,
                    storage_row_key = ?, updated_at_ns = ?
                WHERE project_id = ? AND logical_key = ? AND wire_sha256 = ?
                  AND status = 'committing' AND lease_token = ?
                """,
                (
                    storage_row_key,
                    time.time_ns(),
                    project_id,
                    logical_key,
                    wire_sha256,
                    lease_token,
                ),
            )
            if cursor.rowcount != 1:
                raise HistoricalTurnCommitError(
                    "historical turn lease was lost before journal commit"
                )
            row = conn.execute(
                """
                SELECT project_id, logical_key, wire_sha256, status, commit_id,
                       storage_row_key, trace_ids_json, root_span_ids_json,
                       span_count, last_error, lease_expires_ns
                FROM historical_turn_commits
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
            if row is None:
                raise HistoricalTurnCommitError(
                    "historical turn journal row disappeared"
                )
            return _record_from_row(row)

    def note_error(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        lease_token: str,
        error_code: str,
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE historical_turn_commits
                SET last_error = ?, lease_expires_ns = 0, updated_at_ns = ?
                WHERE project_id = ? AND logical_key = ? AND wire_sha256 = ?
                  AND status = 'committing' AND lease_token = ?
                """,
                (
                    error_code,
                    time.time_ns(),
                    project_id,
                    logical_key,
                    wire_sha256,
                    lease_token,
                ),
            )

    def reconcile_committed(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        storage_row_key: str,
    ) -> HistoricalTurnCommitRecord:
        """Finalize a journal entry after a read-only storage verification."""
        with self._transaction() as conn:
            row = conn.execute(
                """
                SELECT project_id, logical_key, wire_sha256, status, commit_id,
                       storage_row_key, trace_ids_json, root_span_ids_json,
                       span_count, last_error, lease_expires_ns
                FROM historical_turn_commits
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
            if row is None:
                raise HistoricalTurnCommitError(
                    "historical turn journal row disappeared during reconciliation"
                )
            record = _record_from_row(row)
            if record.wire_sha256 != wire_sha256:
                raise HistoricalTurnCommitError(
                    "historical turn journal digest changed during reconciliation"
                )
            if record.status == "committed":
                if record.storage_row_key != storage_row_key:
                    raise HistoricalTurnCommitError(
                        "historical turn journal storage key changed during reconciliation"
                    )
                return record

            conn.execute(
                """
                UPDATE historical_turn_commits
                SET status = 'committed', lease_token = NULL,
                    lease_expires_ns = 0, last_error = NULL,
                    storage_row_key = ?, updated_at_ns = ?
                WHERE project_id = ? AND logical_key = ? AND wire_sha256 = ?
                  AND status = 'committing'
                """,
                (
                    storage_row_key,
                    time.time_ns(),
                    project_id,
                    logical_key,
                    wire_sha256,
                ),
            )
            committed_row = conn.execute(
                """
                SELECT project_id, logical_key, wire_sha256, status, commit_id,
                       storage_row_key, trace_ids_json, root_span_ids_json,
                       span_count, last_error, lease_expires_ns
                FROM historical_turn_commits
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
            if committed_row is None:
                raise HistoricalTurnCommitError(
                    "historical turn journal row disappeared during reconciliation"
                )
            return _record_from_row(committed_row)

    def adopt_storage_commit(
        self,
        *,
        project_id: str,
        logical_key: str,
        stored_row: HistoricalTurnStoredRow,
    ) -> HistoricalTurnCommitRecord:
        """Adopt authoritative immutable storage after conflict or recovery."""
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE historical_turn_commits
                SET wire_sha256 = ?, status = 'committed', lease_token = NULL,
                    lease_expires_ns = 0, last_error = NULL,
                    storage_row_key = ?, trace_ids_json = ?,
                    root_span_ids_json = ?, span_count = ?, updated_at_ns = ?
                WHERE project_id = ? AND logical_key = ? AND status = 'committing'
                """,
                (
                    stored_row.wire_sha256,
                    stored_row.storage_row_key,
                    _dump_ids(list(stored_row.trace_ids)),
                    _dump_ids(list(stored_row.root_span_ids)),
                    stored_row.span_count,
                    time.time_ns(),
                    project_id,
                    logical_key,
                ),
            )
            row = conn.execute(
                """
                SELECT project_id, logical_key, wire_sha256, status, commit_id,
                       storage_row_key, trace_ids_json, root_span_ids_json,
                       span_count, last_error, lease_expires_ns
                FROM historical_turn_commits
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
            if row is None:
                raise HistoricalTurnCommitError(
                    "historical turn journal row disappeared during conflict adoption"
                )
            record = _record_from_row(row)
            evidence_matches = (
                record.status == "committed"
                and record.wire_sha256 == stored_row.wire_sha256
                and record.storage_row_key == stored_row.storage_row_key
                and record.trace_ids == stored_row.trace_ids
                and record.root_span_ids == stored_row.root_span_ids
                and record.span_count == stored_row.span_count
            )
            if cursor.rowcount != 1 and not evidence_matches:
                raise HistoricalTurnCommitError(
                    "historical turn journal changed before conflict adoption"
                )
            if not evidence_matches:
                raise HistoricalTurnCommitError(
                    "historical turn conflict adoption returned inconsistent evidence"
                )
            return record

    def get(
        self, *, project_id: str, logical_key: str
    ) -> HistoricalTurnCommitRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT project_id, logical_key, wire_sha256, status, commit_id,
                       storage_row_key, trace_ids_json, root_span_ids_json,
                       span_count, last_error, lease_expires_ns
                FROM historical_turn_commits
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else _record_from_row(row)

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            schema_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if schema_version not in {0, self._SCHEMA_VERSION}:
                raise HistoricalTurnCommitError(
                    f"unsupported historical turn journal schema {schema_version}"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_turn_commits (
                    project_id TEXT NOT NULL,
                    logical_key TEXT NOT NULL,
                    wire_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('committing', 'committed')),
                    commit_id TEXT NOT NULL,
                    storage_row_key TEXT,
                    trace_ids_json TEXT NOT NULL,
                    root_span_ids_json TEXT NOT NULL,
                    span_count INTEGER NOT NULL,
                    last_error TEXT,
                    lease_token TEXT,
                    lease_expires_ns INTEGER NOT NULL,
                    created_at_ns INTEGER NOT NULL,
                    updated_at_ns INTEGER NOT NULL,
                    PRIMARY KEY (project_id, logical_key)
                )
                """
            )
            conn.execute(f"PRAGMA user_version = {self._SCHEMA_VERSION}")
        finally:
            conn.close()
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        return conn

    def _transaction(self) -> _SQLiteTransaction:
        return _SQLiteTransaction(self._connect())


class _SQLiteTransaction:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            self.conn.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            self.conn.close()


class SQLiteHistoricalTurnWriter:
    """File-backed atomic complete-turn storage for local development/tests.

    ``historical_agent_turns`` has one immutable row per project/logical key.
    ``BEGIN IMMEDIATE`` and the primary key make ``put_if_absent`` a storage
    CAS. ``get_existing`` is read-only evidence used to recover a journal
    finalize after the complete row is already visible; it never authorizes a
    storage write.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        if str(path) == ":memory:":
            raise ValueError("historical turn rows must be file-backed")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def put_if_absent(
        self,
        *,
        project_id: str,
        logical_key: str,
        wire_sha256: str,
        complete_row: PreparedTurn,
        wb_user_id: str | None,
    ) -> HistoricalTurnWriterResult:
        validate_prepared_turn(complete_row, project_id=project_id)
        if complete_row.logical_key != logical_key:
            raise HistoricalTurnCommitError(
                "storage CAS logical key does not match the complete row"
            )
        if complete_row.wire_sha256 != wire_sha256:
            raise HistoricalTurnCommitError(
                "storage CAS digest does not match the complete row"
            )

        storage_row_key = _storage_row_key(project_id, logical_key)
        envelope_json = canonical_json_bytes(complete_row.model_dump(mode="json"))
        with self._transaction() as conn:
            row = conn.execute(
                """
                SELECT storage_row_key, wire_sha256, envelope_json
                FROM historical_agent_turns
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO historical_agent_turns (
                        project_id, logical_key, storage_row_key, wire_sha256,
                        envelope_json, created_at_ns
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        logical_key,
                        storage_row_key,
                        wire_sha256,
                        envelope_json,
                        time.time_ns(),
                    ),
                )
                return _writer_result(
                    outcome="created",
                    storage_row_key=storage_row_key,
                    turn=complete_row,
                )

            existing_row_key = str(row[0])
            existing_wire_sha256 = str(row[1])
            existing_json = bytes(row[2])
            existing_turn = _parse_stored_turn(existing_json, project_id)
            if existing_wire_sha256 != wire_sha256 or existing_json != envelope_json:
                return _writer_result(
                    outcome="conflict",
                    storage_row_key=existing_row_key,
                    turn=existing_turn,
                )
            return _writer_result(
                outcome="replayed",
                storage_row_key=existing_row_key,
                turn=existing_turn,
            )

    def get_existing(
        self, *, project_id: str, logical_key: str
    ) -> HistoricalTurnStoredRow | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT storage_row_key, envelope_json
                FROM historical_agent_turns
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        turn = _parse_stored_turn(bytes(row[1]), project_id)
        return _stored_row(storage_row_key=str(row[0]), turn=turn)

    def read(self, *, project_id: str, logical_key: str) -> PreparedTurn | None:
        """Read a complete local row for verification; never a write authority."""
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT envelope_json
                FROM historical_agent_turns
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return _parse_stored_turn(bytes(row[0]), project_id)

    def row_count(self, *, project_id: str, logical_key: str) -> int:
        """Count a logical row for local verification; never a write authority."""
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT count(*)
                FROM historical_agent_turns
                WHERE project_id = ? AND logical_key = ?
                """,
                (project_id, logical_key),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise HistoricalTurnCommitError(
                "historical row count query returned no row"
            )
        return int(str(row[0]))

    def _initialize(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS historical_agent_turns (
                    project_id TEXT NOT NULL,
                    logical_key TEXT NOT NULL,
                    storage_row_key TEXT NOT NULL UNIQUE,
                    wire_sha256 TEXT NOT NULL,
                    envelope_json BLOB NOT NULL,
                    created_at_ns INTEGER NOT NULL,
                    PRIMARY KEY (project_id, logical_key)
                )
                """
            )
        finally:
            conn.close()
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        return conn

    def _transaction(self) -> _SQLiteTransaction:
        return _SQLiteTransaction(self._connect())


class HistoricalTurnService:
    """Backend-neutral implementation of the three trace-server methods."""

    def __init__(
        self,
        *,
        store: HistoricalTurnCommitStore,
        writer: HistoricalTurnWriter,
        recovery_lease_seconds: int = DEFAULT_HISTORICAL_TURN_RECOVERY_LEASE_SECONDS,
    ):
        if recovery_lease_seconds <= 0:
            raise ValueError("recovery_lease_seconds must be positive")
        self._store = store
        self._writer = writer
        self._recovery_lease_seconds = recovery_lease_seconds

    def historical_turn_capabilities(
        self, req: HistoricalTurnCapabilitiesReq
    ) -> HistoricalTurnCapabilitiesRes:
        return supported_historical_turn_capabilities(
            recovery_lease_seconds=self._recovery_lease_seconds
        )

    def historical_turn_status(
        self, req: HistoricalTurnStatusReq
    ) -> HistoricalTurnStatusRes:
        record = self._store.get(project_id=req.project_id, logical_key=req.logical_key)
        if record is None:
            return HistoricalTurnStatusRes(
                logical_key=req.logical_key,
                status="absent",
            )
        if record.status == "committing":
            record = self._reconcile_pending_status(req.project_id, record)
        return _status_response(record)

    def historical_turn_upsert(
        self, req: HistoricalTurnUpsertReq
    ) -> HistoricalTurnUpsertRes:
        # This must remain before the journal claim and writer lookup. An invalid
        # child is a whole-turn rejection, never a partial-write response.
        if (
            req.capability_version != HISTORICAL_TURN_CAPABILITY_VERSION
            or req.turn.capability_version != HISTORICAL_TURN_CAPABILITY_VERSION
            or req.capability_version != req.turn.capability_version
        ):
            raise HistoricalTurnCapabilityMismatchError(
                "historical turn capability mismatch: expected "
                f"{HISTORICAL_TURN_CAPABILITY_VERSION!r}, got request "
                f"{req.capability_version!r} and envelope "
                f"{req.turn.capability_version!r}"
            )
        validate_prepared_turn(req.turn, project_id=req.project_id)
        claim = self._store.claim(
            project_id=req.project_id,
            turn=req.turn,
            lease_seconds=self._recovery_lease_seconds,
        )
        if claim.outcome == "conflict":
            return HistoricalTurnUpsertRes(
                logical_key=req.turn.logical_key,
                wire_sha256=req.turn.wire_sha256,
                status="conflict",
                existing_wire_sha256=claim.record.wire_sha256,
            )
        if claim.outcome == "replayed":
            return _upsert_response(claim.record, status="replayed")
        if claim.outcome == "busy":
            return _upsert_response(claim.record, status="committing")

        lease_token = claim.lease_token
        if lease_token is None:
            raise HistoricalTurnCommitError("acquired claim did not contain a lease")
        return self._commit_claim(req, lease_token)

    def _commit_claim(
        self, req: HistoricalTurnUpsertReq, lease_token: str
    ) -> HistoricalTurnUpsertRes:
        try:
            return self._finish_acquired_claim(req, lease_token)
        except Exception:
            self._store.note_error(
                project_id=req.project_id,
                logical_key=req.turn.logical_key,
                wire_sha256=req.turn.wire_sha256,
                lease_token=lease_token,
                error_code="commit_attempt_failed",
            )
            raise

    def _reconcile_pending_status(
        self, project_id: str, record: HistoricalTurnCommitRecord
    ) -> HistoricalTurnCommitRecord:
        stored_row = self._writer.get_existing(
            project_id=project_id,
            logical_key=record.logical_key,
        )
        if stored_row is None:
            return record
        if stored_row.wire_sha256 != record.wire_sha256:
            _validate_authoritative_conflict_evidence(
                logical_key=record.logical_key,
                claimed_wire_sha256=record.wire_sha256,
                expected_trace_ids=record.trace_ids,
                expected_root_span_ids=record.root_span_ids,
                stored_row=stored_row,
            )
            return self._store.adopt_storage_commit(
                project_id=project_id,
                logical_key=record.logical_key,
                stored_row=stored_row,
            )
        if (
            stored_row.trace_ids != record.trace_ids
            or stored_row.root_span_ids != record.root_span_ids
            or stored_row.span_count != record.span_count
        ):
            raise HistoricalTurnCommitError(
                "historical turn storage evidence conflicts with the pending journal"
            )
        return self._store.reconcile_committed(
            project_id=project_id,
            logical_key=record.logical_key,
            wire_sha256=record.wire_sha256,
            storage_row_key=stored_row.storage_row_key,
        )

    def _finish_acquired_claim(
        self, req: HistoricalTurnUpsertReq, lease_token: str
    ) -> HistoricalTurnUpsertRes:
        writer_result = self._writer.put_if_absent(
            project_id=req.project_id,
            logical_key=req.turn.logical_key,
            wire_sha256=req.turn.wire_sha256,
            complete_row=req.turn,
            wb_user_id=req.wb_user_id,
        )
        if writer_result.outcome == "conflict":
            _validate_conflicting_writer_result(req.turn, writer_result)
            record = self._store.adopt_storage_commit(
                project_id=req.project_id,
                logical_key=req.turn.logical_key,
                stored_row=HistoricalTurnStoredRow(
                    storage_row_key=writer_result.storage_row_key,
                    wire_sha256=writer_result.wire_sha256,
                    trace_ids=writer_result.trace_ids,
                    root_span_ids=writer_result.root_span_ids,
                    span_count=writer_result.span_count,
                ),
            )
            return HistoricalTurnUpsertRes(
                logical_key=req.turn.logical_key,
                wire_sha256=req.turn.wire_sha256,
                status="conflict",
                storage_row_key=record.storage_row_key,
                existing_wire_sha256=record.wire_sha256,
            )
        _validate_writer_result(req.turn, writer_result)
        record = self._store.mark_committed(
            project_id=req.project_id,
            logical_key=req.turn.logical_key,
            wire_sha256=req.turn.wire_sha256,
            lease_token=lease_token,
            storage_row_key=writer_result.storage_row_key,
        )
        return _upsert_response(record, status="committed")


def supported_historical_turn_capabilities(
    *, recovery_lease_seconds: int = DEFAULT_HISTORICAL_TURN_RECOVERY_LEASE_SECONDS
) -> HistoricalTurnCapabilitiesRes:
    return HistoricalTurnCapabilitiesRes(
        supported=True,
        capability_version=HISTORICAL_TURN_CAPABILITY_VERSION,
        transport_encoding="canonical-json",
        content_encoding="identity",
        preview_compression="gzip-mtime-0",
        schema_versions=[HISTORICAL_TURN_SCHEMA_VERSION],
        max_envelope_bytes=MAX_HISTORICAL_TURN_ENVELOPE_BYTES,
        max_spans=MAX_HISTORICAL_TURN_SPANS,
        max_logical_key_bytes=MAX_HISTORICAL_TURN_LOGICAL_KEY_BYTES,
        atomic_turn_commit=True,
        durable_idempotency=True,
        status_lookup=True,
        content_refs="unsupported",
        recovery_lease_seconds=recovery_lease_seconds,
    )


def unsupported_historical_turn_capabilities(
    reason: str,
) -> HistoricalTurnCapabilitiesRes:
    return HistoricalTurnCapabilitiesRes(
        supported=False,
        capability_version=HISTORICAL_TURN_CAPABILITY_VERSION,
        transport_encoding="canonical-json",
        content_encoding="identity",
        preview_compression="gzip-mtime-0",
        schema_versions=[HISTORICAL_TURN_SCHEMA_VERSION],
        max_envelope_bytes=0,
        max_spans=0,
        max_logical_key_bytes=MAX_HISTORICAL_TURN_LOGICAL_KEY_BYTES,
        atomic_turn_commit=False,
        durable_idempotency=False,
        status_lookup=False,
        content_refs="unsupported",
        recovery_lease_seconds=0,
        reason=reason,
    )


def _commit_id(project_id: str, logical_key: str) -> str:
    digest = hashlib.sha256(
        b"weave-historical-turn-commit-v1\0"
        + project_id.encode("utf-8")
        + b"\0"
        + logical_key.encode("ascii")
    ).hexdigest()
    return f"htc1:{digest}"


def _storage_row_key(project_id: str, logical_key: str) -> str:
    digest = hashlib.sha256(
        b"weave-historical-turn-row-v1\0"
        + project_id.encode("utf-8")
        + b"\0"
        + logical_key.encode("ascii")
    ).hexdigest()
    return f"htr1:{digest}"


def _dump_ids(ids: list[str]) -> str:
    return json.dumps(ids, separators=(",", ":"))


def _record_from_row(
    row: sqlite3.Row | tuple[object, ...],
) -> HistoricalTurnCommitRecord:
    status = str(row[3])
    typed_status: Literal["committing", "committed"]
    if status == "committing":
        typed_status = "committing"
    elif status == "committed":
        typed_status = "committed"
    else:
        raise HistoricalTurnCommitError(f"invalid journal status {status!r}")
    return HistoricalTurnCommitRecord(
        project_id=str(row[0]),
        logical_key=str(row[1]),
        wire_sha256=str(row[2]),
        status=typed_status,
        commit_id=str(row[4]),
        storage_row_key=None if row[5] is None else str(row[5]),
        trace_ids=tuple(json.loads(str(row[6]))),
        root_span_ids=tuple(json.loads(str(row[7]))),
        span_count=int(str(row[8])),
        last_error=None if row[9] is None else str(row[9]),
    )


def _status_response(record: HistoricalTurnCommitRecord) -> HistoricalTurnStatusRes:
    return HistoricalTurnStatusRes(
        logical_key=record.logical_key,
        status=record.status,
        wire_sha256=record.wire_sha256,
        commit_id=record.commit_id,
        storage_row_key=record.storage_row_key,
        trace_ids=list(record.trace_ids),
        root_span_ids=list(record.root_span_ids),
        span_count=record.span_count,
        last_error=record.last_error,
    )


def _upsert_response(
    record: HistoricalTurnCommitRecord,
    *,
    status: Literal["committing", "committed", "replayed"],
) -> HistoricalTurnUpsertRes:
    return HistoricalTurnUpsertRes(
        logical_key=record.logical_key,
        wire_sha256=record.wire_sha256,
        status=status,
        commit_id=record.commit_id,
        storage_row_key=record.storage_row_key,
        trace_ids=list(record.trace_ids),
        root_span_ids=list(record.root_span_ids),
        span_count=record.span_count,
    )


def _validate_writer_result(
    turn: PreparedTurn, result: HistoricalTurnWriterResult
) -> None:
    if result.outcome not in {"created", "replayed"}:
        raise HistoricalTurnCommitError(
            f"unexpected historical turn writer outcome {result.outcome!r}"
        )
    if not result.storage_row_key:
        raise HistoricalTurnCommitError(
            "historical turn writer returned an empty storage row key"
        )
    if (
        result.wire_sha256 != turn.wire_sha256
        or result.trace_ids != (turn.trace_id,)
        or result.root_span_ids != (turn.root_span_id,)
        or result.span_count != turn.span_count
    ):
        raise HistoricalTurnCommitError(
            "historical turn writer returned inconsistent storage evidence"
        )


def _validate_conflicting_writer_result(
    turn: PreparedTurn, result: HistoricalTurnWriterResult
) -> None:
    if result.outcome != "conflict":
        raise HistoricalTurnCommitError(
            f"unexpected historical turn writer outcome {result.outcome!r}"
        )
    stored_row = HistoricalTurnStoredRow(
        storage_row_key=result.storage_row_key,
        wire_sha256=result.wire_sha256,
        trace_ids=result.trace_ids,
        root_span_ids=result.root_span_ids,
        span_count=result.span_count,
    )
    _validate_authoritative_conflict_evidence(
        logical_key=turn.logical_key,
        claimed_wire_sha256=turn.wire_sha256,
        expected_trace_ids=(turn.trace_id,),
        expected_root_span_ids=(turn.root_span_id,),
        stored_row=stored_row,
    )


def _validate_authoritative_conflict_evidence(
    *,
    logical_key: str,
    claimed_wire_sha256: str,
    expected_trace_ids: tuple[str, ...],
    expected_root_span_ids: tuple[str, ...],
    stored_row: HistoricalTurnStoredRow,
) -> None:
    invalid_evidence = any(
        (
            not stored_row.storage_row_key,
            not _is_sha256(stored_row.wire_sha256),
            stored_row.wire_sha256 == claimed_wire_sha256,
            stored_row.trace_ids != expected_trace_ids,
            stored_row.root_span_ids != expected_root_span_ids,
            stored_row.span_count < 1,
            stored_row.span_count > MAX_HISTORICAL_TURN_SPANS,
        )
    )
    if invalid_evidence:
        raise HistoricalTurnCommitError(
            "historical turn storage returned inconsistent conflict evidence for "
            f"logical key {logical_key}"
        )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _parse_stored_turn(envelope_json: bytes, project_id: str) -> PreparedTurn:
    try:
        turn = PreparedTurn.model_validate_json(envelope_json)
    except Exception as exc:
        raise HistoricalTurnCommitError(
            "stored historical turn envelope is unreadable"
        ) from exc
    validate_prepared_turn(turn, project_id=project_id)
    return turn


def _writer_result(
    *,
    outcome: Literal["created", "replayed", "conflict"],
    storage_row_key: str,
    turn: PreparedTurn,
) -> HistoricalTurnWriterResult:
    return HistoricalTurnWriterResult(
        outcome=outcome,
        storage_row_key=storage_row_key,
        wire_sha256=turn.wire_sha256,
        trace_ids=(turn.trace_id,),
        root_span_ids=(turn.root_span_id,),
        span_count=turn.span_count,
    )


def _stored_row(*, storage_row_key: str, turn: PreparedTurn) -> HistoricalTurnStoredRow:
    return HistoricalTurnStoredRow(
        storage_row_key=storage_row_key,
        wire_sha256=turn.wire_sha256,
        trace_ids=(turn.trace_id,),
        root_span_ids=(turn.root_span_id,),
        span_count=turn.span_count,
    )
