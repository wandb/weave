"""Storage interface (Tier 1) — ORM / data-access layer.

Operates on internal row types, NOT API request/response types.
Knows nothing about business logic, validation, or ID translation.

Methods are generic data operations:
  - insert_call, insert_call_complete, insert_call_batch
  - query_calls, query_calls_stream
  - insert_object, query_objects
  - insert_file, read_file
  - insert_feedback, query_feedback
  - execute_query, execute_query_stream  (escape hatch for raw SQL)

Implementations: ClickHouseStorage, SqliteStorage
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from pydantic import BaseModel


# ── Row types (internal representation, not API types) ──────────────
#
# These correspond to what ClickHouseTraceServer currently calls
# CallCHInsertable, CallCompleteCHInsertable, SelectableCHObjSchema, etc.
# Defined here as simple Pydantic models so the interface is self-contained.
# In a full implementation these would be richer and DB-specific subtypes
# would extend them.


class CallRow(BaseModel):
    """Internal row for a call start (maps to call_parts table)."""

    project_id: str
    id: str
    trace_id: str
    parent_id: str | None = None
    op_name: str | None = None
    display_name: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    inputs: dict[str, Any] | None = None
    output: Any | None = None
    summary: dict[str, Any] | None = None
    exception: str | None = None
    wb_run_id: str | None = None
    wb_user_id: str | None = None
    # ... additional columns omitted for brevity


class CallCompleteRow(BaseModel):
    """Internal row for a complete call (maps to calls_complete table)."""

    project_id: str
    id: str
    trace_id: str
    parent_id: str | None = None
    op_name: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    inputs: dict[str, Any] | None = None
    output: Any | None = None
    summary: dict[str, Any] | None = None
    exception: str | None = None
    wb_run_id: str | None = None
    wb_user_id: str | None = None


class ObjectRow(BaseModel):
    """Internal row for an object version."""

    project_id: str
    object_id: str
    kind: str  # "op", "object", etc.
    val: dict[str, Any]
    digest: str | None = None
    version_index: int | None = None
    wb_user_id: str | None = None


class FileRow(BaseModel):
    """Internal row for a file."""

    project_id: str
    name: str
    digest: str
    content: bytes


class FeedbackRow(BaseModel):
    """Internal row for feedback."""

    project_id: str
    weave_ref: str
    feedback_type: str
    payload: dict[str, Any]
    wb_user_id: str | None = None


class TableRowData(BaseModel):
    """Internal row for a table row."""

    project_id: str
    digest: str
    val: dict[str, Any]


class QueryResult(BaseModel):
    """Generic query result with rows and optional metadata."""

    rows: list[dict[str, Any]]
    total_count: int | None = None


# ── Storage Protocol ────────────────────────────────────────────────


class StorageInterface(Protocol):
    """Raw data-access layer. Operates on rows, not API requests.

    This is the pseudo-ORM. Implementations handle:
    - Connection management (CH client, SQLite connection)
    - Batching / flushing (CH async inserts)
    - Query building and execution
    - Table routing (call_parts vs calls_complete)

    Implementations do NOT handle:
    - Request validation or processing
    - ID translation (external ↔ internal)
    - Business logic (op_create orchestration, etc.)
    - Ref conversion
    """

    # ── Calls ────────────────────────────────────────────────────────

    def insert_call(self, row: CallRow) -> None: ...
    def insert_call_complete(self, row: CallCompleteRow) -> None: ...
    def insert_call_batch(self, rows: list[CallRow]) -> None: ...
    def query_calls(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: list[dict[str, str]] | None = None,
    ) -> QueryResult: ...
    def query_calls_stream(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        sort_by: list[dict[str, str]] | None = None,
    ) -> Iterator[dict[str, Any]]: ...
    def delete_calls(
        self, project_id: str, call_ids: list[str]
    ) -> None: ...
    def update_call(
        self, project_id: str, call_id: str, updates: dict[str, Any]
    ) -> None: ...

    # ── Objects ──────────────────────────────────────────────────────

    def insert_object(self, row: ObjectRow) -> str: ...  # returns digest
    def query_objects(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        metadata_only: bool = False,
    ) -> list[dict[str, Any]]: ...
    def read_object(
        self,
        project_id: str,
        object_id: str,
        digest: str | None = None,
        version_index: int | None = None,
    ) -> dict[str, Any] | None: ...
    def delete_object(
        self, project_id: str, object_id: str, digests: list[str]
    ) -> None: ...

    # ── Tags & Aliases ───────────────────────────────────────────────

    def insert_tags(
        self, project_id: str, object_id: str, tags: list[str]
    ) -> None: ...
    def remove_tags(
        self, project_id: str, object_id: str, tags: list[str]
    ) -> None: ...
    def insert_aliases(
        self,
        project_id: str,
        object_id: str,
        aliases: dict[str, str],
    ) -> None: ...
    def remove_aliases(
        self, project_id: str, object_id: str, aliases: list[str]
    ) -> None: ...
    def query_tags(self, project_id: str) -> list[str]: ...
    def query_aliases(self, project_id: str) -> list[dict[str, str]]: ...

    # ── Tables ───────────────────────────────────────────────────────

    def insert_table(
        self, project_id: str, rows: list[TableRowData]
    ) -> str: ...  # returns table digest
    def update_table(
        self,
        project_id: str,
        base_digest: str,
        updates: list[dict[str, Any]],
    ) -> str: ...  # returns new digest
    def query_table(
        self,
        project_id: str,
        digest: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryResult: ...
    def query_table_stats(
        self, project_id: str, digest: str
    ) -> dict[str, Any]: ...

    # ── Refs ─────────────────────────────────────────────────────────

    def read_refs_batch(
        self, refs: list[str]
    ) -> list[dict[str, Any] | None]: ...

    # ── Files ────────────────────────────────────────────────────────

    def insert_file(self, row: FileRow) -> str: ...  # returns digest
    def read_file(
        self, project_id: str, digest: str
    ) -> bytes: ...

    # ── Feedback ─────────────────────────────────────────────────────

    def insert_feedback(self, row: FeedbackRow) -> str: ...  # returns id
    def insert_feedback_batch(
        self, rows: list[FeedbackRow]
    ) -> list[str]: ...
    def query_feedback(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...
    def purge_feedback(
        self, project_id: str, feedback_ids: list[str]
    ) -> None: ...

    # ── Costs ────────────────────────────────────────────────────────

    def insert_cost(
        self, project_id: str, cost: dict[str, Any]
    ) -> None: ...
    def query_costs(
        self, project_id: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...
    def purge_costs(
        self, project_id: str, cost_ids: list[str]
    ) -> None: ...
