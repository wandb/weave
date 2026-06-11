# In-Memory ("fake") Trace Server
#
# A pure-Python, dict/list-backed implementation of the full trace server
# interface, intended as a fast drop-in replacement for the ClickHouse trace
# server in tests. It lives parallel to `clickhouse_trace_server_batched.py`.
#
# Behavioral contract: this server replicates the *ClickHouse* trace server
# (the production backend) at the interface level, so tests written against
# ClickHouse behavior pass unmodified. That includes ClickHouse's observable
# semantics: JSON_VALUE string typing for dynamic fields ('' for missing keys,
# JSON nulls, and non-scalars), to*OrNull cast rules, NULLS-LAST ordering with
# existence-first sorting for dynamic fields, DateTime64 column comparisons,
# and the computed summary fields (status/latency_ms/trace_name).
# ClickHouse *internals* (SQL, table routing/residence, batching, bucket file
# storage) are out of scope; tests asserting those are ClickHouse-gated.

import datetime
import threading
from dataclasses import dataclass, field
from typing import Any

from weave.trace_server import trace_server_interface as tsi

# Completion request preparation (prompt resolution, provider/secret setup) is
# backend-agnostic business logic that currently lives in the ClickHouse
# module; import it rather than fork it.
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelDispatcher,
)


@dataclass(slots=True)
class _CallRec:
    project_id: str
    id: str
    trace_id: str | None
    parent_id: str | None
    thread_id: str | None
    turn_id: str | None
    op_name: str | None
    display_name: str | None
    started_at: datetime.datetime | None
    attributes: Any
    inputs: Any
    input_refs: list[str]
    wb_user_id: str | None
    wb_run_id: str | None
    wb_run_step: int | None
    otel_dump: Any
    expire_at: datetime.datetime
    attributes_len: int | None = None
    inputs_len: int | None = None
    output_len: int | None = None
    summary_len: int | None = None
    otel_dump_len: int | None = None
    ended_at: datetime.datetime | None = None
    exception: str | None = None
    output: Any = None
    output_refs: list[str] = field(default_factory=list)
    summary: Any = None
    wb_run_step_end: int | None = None
    deleted_at: datetime.datetime | None = None
    storage_size_bytes: int | None = None


@dataclass(slots=True)
class _ObjRec:
    project_id: str
    object_id: str
    created_at: datetime.datetime
    kind: str
    base_object_class: str | None
    leaf_object_class: str | None
    val: Any
    digest: str
    version_index: int
    is_latest: int
    wb_user_id: str | None
    val_dump_len: int = 0
    deleted_at: datetime.datetime | None = None


@dataclass(slots=True)
class _TableRowRec:
    project_id: str
    val: Any
    val_dump_len: int = 0


@dataclass(slots=True)
class _AliasRec:
    digest: str
    created_at: datetime.datetime


@dataclass(slots=True)
class _TtlRec:
    project_id: str
    retention_days: int
    updated_at: datetime.datetime
    updated_by: str


class InMemoryTraceServer(tsi.FullTraceServerInterface):
    """Pure in-memory trace server for tests, replicating ClickHouse semantics."""

    def __init__(
        self,
        evaluate_model_dispatcher: EvaluateModelDispatcher | None = None,
    ):
        self.lock = threading.RLock()
        self._evaluate_model_dispatcher = evaluate_model_dispatcher
        self._init_storage()

    def _init_storage(self) -> None:
        # Calls keyed by id (unique per call in practice; reads filter by
        # project_id, mirroring ClickHouse reads scoped by (project_id, id)).
        self._calls: dict[str, _CallRec] = {}
        # Objects keyed by (project_id, kind, object_id, digest), insertion
        # ordered (rowid order matters for version_index and tie-breaks).
        self._objs: dict[tuple[str, str, str, str], _ObjRec] = {}
        # Tables keyed by (project_id, digest) -> ordered row digests.
        self._tables: dict[tuple[str, str], list[str]] = {}
        # Table rows keyed by digest (content-addressed, first-writer-wins:
        # first writer wins, reads filter on project_id).
        self._table_rows: dict[str, _TableRowRec] = {}
        # Files keyed by (project_id, digest).
        self._files: dict[tuple[str, str], bytes] = {}
        # Tags keyed by (project_id, object_id, digest) -> set of tags.
        self._tags: dict[tuple[str, str, str], set[str]] = {}
        # Aliases keyed by (project_id, object_id, alias) -> digest record.
        self._aliases: dict[tuple[str, str, str], _AliasRec] = {}
        # Feedback rows: stored in the post-insert read shape (see
        # _feedback_row_for_storage), insertion ordered.
        self._feedback: list[dict[str, Any]] = []
        # LLM token price rows (plain dicts mirroring the table columns).
        self._llm_token_prices: list[dict[str, Any]] = []
        # Project TTL settings, append-only audit rows.
        self._ttl_settings: list[_TtlRec] = []
        # Annotation queues / items / per-annotator progress (one mutable
        # record per id, soft-deleted via deleted_at — mirrors the ClickHouse
        # lightweight-update model).
        self._annotation_queues: dict[str, dict[str, Any]] = {}
        self._annotation_queue_items: dict[str, dict[str, Any]] = {}
        self._annotation_progress: dict[str, dict[str, Any]] = {}
        # Agent spans keyed by span_id (ReplacingMergeTree semantics: a
        # re-insert with the same span_id replaces the row).
        self._agent_spans: dict[str, Any] = {}

    def close(self) -> None:
        pass

    def drop_tables(self) -> None:
        self._init_storage()

    def setup_tables(self) -> None:
        pass
