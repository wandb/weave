"""ClickHouse storage implementation (Tier 1).

Raw data-access against ClickHouse. Owns connection management,
batching/flushing, async insert settings, retry logic.
No business logic, no digesting, no ID translation.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.exceptions import DatabaseError
from clickhouse_connect.driver.query import QueryResult as CHQueryResult

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.errors import NotFoundError
from weave.trace_server.v2.storage_interface import (
    CallCompleteRow,
    CallRow,
    FeedbackRow,
    FileRow,
    ObjectRow,
    QueryResult,
    TableRowData,
)

logger = logging.getLogger(__name__)

# ── Column definitions ───────────────────────────────────────────────
# These define the column order for batch inserts into each CH table.

CALL_COLUMNS = [
    "project_id",
    "id",
    "trace_id",
    "parent_id",
    "op_name",
    "display_name",
    "started_at",
    "ended_at",
    "inputs",
    "output",
    "summary",
    "exception",
    "wb_run_id",
    "wb_user_id",
]

OBJECT_COLUMNS = [
    "project_id",
    "object_id",
    "kind",
    "digest",
    "version_index",
    "val",
    "wb_user_id",
]

FILE_COLUMNS = [
    "project_id",
    "digest",
    "chunk_index",
    "n_chunks",
    "name",
    "val_bytes",
]

FEEDBACK_COLUMNS = [
    "project_id",
    "id",
    "weave_ref",
    "feedback_type",
    "payload",
    "wb_user_id",
]


class ClickHouseStorage:
    """ClickHouse implementation of StorageInterface.

    Core primitives:
      - _insert(table, data, column_names) — batched INSERT with retry
      - _query(sql, params) — single-shot SELECT
      - _query_stream(sql, params) — streaming SELECT
    """

    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._use_async_insert = use_async_insert

        self._thread_local = threading.local()
        self._init_lock = threading.Lock()

        # In-memory batches for deferred inserts
        self._call_batch: list[list[Any]] = []
        self._call_complete_batch: list[list[Any]] = []
        self._file_batch: list[list[Any]] = []
        self._flush_immediately = True

    # ── Connection management ────────────────────────────────────────

    @property
    def _client(self) -> CHClient:
        """Thread-local ClickHouse client, lazily created."""
        client: CHClient | None = getattr(
            self._thread_local, "ch_client", None
        )
        if client is None:
            with self._init_lock:
                client = clickhouse_connect.get_client(
                    host=self._host,
                    port=self._port,
                    user=self._user,
                    password=self._password,
                    database=self._database,
                )
                self._thread_local.ch_client = client
        return client

    # ── Core primitives ──────────────────────────────────────────────

    def _insert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> None:
        if not data:
            return

        if self._use_async_insert and not do_sync_insert:
            settings = ch_settings.update_settings_for_async_insert(settings)

        for attempt in range(ch_settings.INSERT_MAX_RETRIES):
            try:
                self._client.insert(
                    table,
                    data=data,
                    column_names=column_names,
                    settings=settings,
                )
                return
            except DatabaseError as e:
                if attempt < ch_settings.INSERT_MAX_RETRIES - 1:
                    logger.warning(
                        "CH insert retry %d for %s: %s", attempt, table, e
                    )
                    continue
                raise

    def _query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> CHQueryResult:
        merged_settings = dict(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)
        if settings:
            merged_settings.update(settings)

        return self._client.query(
            sql,
            parameters=parameters or {},
            use_none=True,
            settings=merged_settings,
        )

    def _query_stream(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Iterator[tuple[Any, ...]]:
        merged_settings = dict(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)
        if settings:
            merged_settings.update(settings)

        with self._client.query_rows_stream(
            sql,
            parameters=parameters or {},
            use_none=True,
            settings=merged_settings,
        ) as stream:
            yield from stream

    @contextmanager
    def batch_context(self) -> Iterator[None]:
        """Accumulate inserts in memory, flush on exit."""
        prev = self._flush_immediately
        self._flush_immediately = False
        try:
            yield
        finally:
            self._flush_all()
            self._flush_immediately = prev

    def _flush_all(self) -> None:
        if self._call_batch:
            self._insert(
                "call_parts",
                data=self._call_batch,
                column_names=CALL_COLUMNS,
            )
            self._call_batch = []
        if self._call_complete_batch:
            self._insert(
                "calls_complete",
                data=self._call_complete_batch,
                column_names=CALL_COLUMNS,
            )
            self._call_complete_batch = []
        if self._file_batch:
            self._insert(
                "files",
                data=self._file_batch,
                column_names=FILE_COLUMNS,
            )
            self._file_batch = []

    # ── Calls ────────────────────────────────────────────────────────

    def insert_call(self, row: CallRow) -> None:
        data = self._call_row_to_list(row)
        self._call_batch.append(data)
        if self._flush_immediately:
            self._insert(
                "call_parts",
                data=[data],
                column_names=CALL_COLUMNS,
            )
            self._call_batch.pop()

    def insert_call_complete(self, row: CallCompleteRow) -> None:
        data = self._call_complete_row_to_list(row)
        self._call_complete_batch.append(data)
        if self._flush_immediately:
            self._insert(
                "calls_complete",
                data=[data],
                column_names=CALL_COLUMNS,
            )
            self._call_complete_batch.pop()

    def insert_call_batch(self, rows: list[CallRow]) -> None:
        data = [self._call_row_to_list(r) for r in rows]
        self._insert("call_parts", data=data, column_names=CALL_COLUMNS)

    def query_calls(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: list[dict[str, str]] | None = None,
    ) -> QueryResult:
        sql = "SELECT * FROM call_parts WHERE project_id = {project_id:String}"
        params: dict[str, Any] = {"project_id": project_id}

        if filters and "id" in filters:
            sql += " AND id = {call_id:String}"
            params["call_id"] = filters["id"]

        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"

        result = self._query(sql, params)
        columns = result.column_names
        rows = [dict(zip(columns, row)) for row in result.result_rows]
        return QueryResult(rows=rows, total_count=len(rows))

    def query_calls_stream(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        sort_by: list[dict[str, str]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM call_parts WHERE project_id = {project_id:String}"
        params: dict[str, Any] = {"project_id": project_id}

        if limit is not None:
            sql += f" LIMIT {limit}"

        # We need column names from schema; query once to get them
        result = self._query(
            f"SELECT name FROM system.columns WHERE table = 'call_parts' AND database = '{self._database}'"
        )
        col_names = [row[0] for row in result.result_rows]

        for row_tuple in self._query_stream(sql, params):
            yield dict(zip(col_names, row_tuple))

    def delete_calls(self, project_id: str, call_ids: list[str]) -> None:
        if not call_ids:
            return
        self._query(
            "ALTER TABLE call_parts DELETE WHERE project_id = {project_id:String} "
            "AND id IN {call_ids:Array(String)}",
            {"project_id": project_id, "call_ids": call_ids},
        )

    def update_call(
        self, project_id: str, call_id: str, updates: dict[str, Any]
    ) -> None:
        # ClickHouse uses INSERT for updates (last-write-wins with ReplacingMergeTree)
        # For now, re-insert the row. Production uses ALTER TABLE UPDATE.
        set_parts = ", ".join(
            f"{k} = {{{k}:String}}" for k in updates
        )
        params: dict[str, Any] = {
            "project_id": project_id,
            "call_id": call_id,
            **updates,
        }
        self._query(
            f"ALTER TABLE call_parts UPDATE {set_parts} "
            "WHERE project_id = {project_id:String} AND id = {call_id:String}",
            params,
        )

    # ── Objects ──────────────────────────────────────────────────────

    def insert_object(self, row: ObjectRow) -> str:
        data = [
            row.project_id,
            row.object_id,
            row.kind,
            row.digest or "",
            row.version_index or 0,
            row.val,
            row.wb_user_id,
        ]
        self._insert(
            "object_versions",
            data=[data],
            column_names=OBJECT_COLUMNS,
        )
        return row.digest or ""

    def query_objects(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        metadata_only: bool = False,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM object_versions WHERE project_id = {project_id:String}"
        params: dict[str, Any] = {"project_id": project_id}

        if filters and "object_id" in filters:
            sql += " AND object_id = {object_id:String}"
            params["object_id"] = filters["object_id"]

        if limit is not None:
            sql += f" LIMIT {limit}"

        result = self._query(sql, params)
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    def read_object(
        self,
        project_id: str,
        object_id: str,
        digest: str | None = None,
        version_index: int | None = None,
    ) -> dict[str, Any] | None:
        sql = (
            "SELECT * FROM object_versions "
            "WHERE project_id = {project_id:String} "
            "AND object_id = {object_id:String}"
        )
        params: dict[str, Any] = {
            "project_id": project_id,
            "object_id": object_id,
        }
        if digest is not None:
            sql += " AND digest = {digest:String}"
            params["digest"] = digest
        if version_index is not None:
            sql += " AND version_index = {vi:UInt64}"
            params["vi"] = version_index

        sql += " ORDER BY version_index DESC LIMIT 1"

        result = self._query(sql, params)
        if not result.result_rows:
            return None
        columns = result.column_names
        return dict(zip(columns, result.result_rows[0]))

    def delete_object(
        self, project_id: str, object_id: str, digests: list[str]
    ) -> None:
        self._query(
            "ALTER TABLE object_versions DELETE "
            "WHERE project_id = {project_id:String} "
            "AND object_id = {object_id:String} "
            "AND digest IN {digests:Array(String)}",
            {
                "project_id": project_id,
                "object_id": object_id,
                "digests": digests,
            },
        )

    # ── Tags & Aliases ───────────────────────────────────────────────

    def insert_tags(
        self, project_id: str, object_id: str, tags: list[str]
    ) -> None:
        if not tags:
            return
        data = [[project_id, object_id, tag] for tag in tags]
        self._insert(
            "object_tags",
            data=data,
            column_names=["project_id", "object_id", "tag"],
        )

    def remove_tags(
        self, project_id: str, object_id: str, tags: list[str]
    ) -> None:
        if not tags:
            return
        self._query(
            "ALTER TABLE object_tags DELETE "
            "WHERE project_id = {project_id:String} "
            "AND object_id = {object_id:String} "
            "AND tag IN {tags:Array(String)}",
            {"project_id": project_id, "object_id": object_id, "tags": tags},
        )

    def insert_aliases(
        self, project_id: str, object_id: str, aliases: dict[str, str]
    ) -> None:
        if not aliases:
            return
        data = [
            [project_id, object_id, alias, digest]
            for alias, digest in aliases.items()
        ]
        self._insert(
            "object_aliases",
            data=data,
            column_names=["project_id", "object_id", "alias", "digest"],
        )

    def remove_aliases(
        self, project_id: str, object_id: str, aliases: list[str]
    ) -> None:
        if not aliases:
            return
        self._query(
            "ALTER TABLE object_aliases DELETE "
            "WHERE project_id = {project_id:String} "
            "AND object_id = {object_id:String} "
            "AND alias IN {aliases:Array(String)}",
            {
                "project_id": project_id,
                "object_id": object_id,
                "aliases": aliases,
            },
        )

    def query_tags(self, project_id: str) -> list[str]:
        result = self._query(
            "SELECT DISTINCT tag FROM object_tags "
            "WHERE project_id = {project_id:String}",
            {"project_id": project_id},
        )
        return [row[0] for row in result.result_rows]

    def query_aliases(self, project_id: str) -> list[dict[str, str]]:
        result = self._query(
            "SELECT object_id, alias, digest FROM object_aliases "
            "WHERE project_id = {project_id:String}",
            {"project_id": project_id},
        )
        return [
            {"object_id": row[0], "alias": row[1], "digest": row[2]}
            for row in result.result_rows
        ]

    # ── Tables ───────────────────────────────────────────────────────

    def insert_table(
        self, project_id: str, rows: list[TableRowData]
    ) -> str:
        if not rows:
            return ""
        data = [[r.project_id, r.digest, r.val] for r in rows]
        self._insert(
            "table_rows",
            data=data,
            column_names=["project_id", "digest", "val"],
        )
        return rows[0].digest if rows else ""

    def update_table(
        self,
        project_id: str,
        base_digest: str,
        updates: list[dict[str, Any]],
    ) -> str:
        # Simplified — production handles row-level diffing
        return base_digest

    def query_table(
        self,
        project_id: str,
        digest: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryResult:
        sql = (
            "SELECT * FROM table_rows "
            "WHERE project_id = {project_id:String} "
            "AND digest = {digest:String}"
        )
        params: dict[str, Any] = {"project_id": project_id, "digest": digest}

        if limit is not None:
            sql += f" LIMIT {limit}"

        result = self._query(sql, params)
        columns = result.column_names
        rows = [dict(zip(columns, row)) for row in result.result_rows]
        return QueryResult(rows=rows)

    def query_table_stats(
        self, project_id: str, digest: str
    ) -> dict[str, Any]:
        result = self._query(
            "SELECT count() as cnt FROM table_rows "
            "WHERE project_id = {project_id:String} "
            "AND digest = {digest:String}",
            {"project_id": project_id, "digest": digest},
        )
        count = result.result_rows[0][0] if result.result_rows else 0
        return {"count": count}

    # ── Refs ─────────────────────────────────────────────────────────

    def read_refs_batch(
        self, refs: list[str]
    ) -> list[dict[str, Any] | None]:
        # Simplified — production parses weave:// URIs and resolves
        return [None for _ in refs]

    # ── Files ────────────────────────────────────────────────────────

    def insert_file(self, row: FileRow) -> str:
        # Store as a single chunk
        data = [
            [
                row.project_id,
                row.digest,
                0,  # chunk_index
                1,  # n_chunks
                row.name,
                row.content,
            ]
        ]
        if self._flush_immediately:
            self._insert("files", data=data, column_names=FILE_COLUMNS)
        else:
            self._file_batch.extend(data)
        return row.digest

    def read_file(self, project_id: str, digest: str) -> bytes:
        result = self._query(
            "SELECT val_bytes FROM files "
            "WHERE project_id = {project_id:String} "
            "AND digest = {digest:String} "
            "ORDER BY chunk_index",
            {"project_id": project_id, "digest": digest},
        )
        if not result.result_rows:
            raise NotFoundError(f"File {digest} not found")
        return b"".join(row[0] for row in result.result_rows)

    # ── Feedback ─────────────────────────────────────────────────────

    def insert_feedback(self, row: FeedbackRow) -> str:
        import uuid

        feedback_id = str(uuid.uuid4())
        data = [
            [
                row.project_id,
                feedback_id,
                row.weave_ref,
                row.feedback_type,
                row.payload,
                row.wb_user_id,
            ]
        ]
        self._insert(
            "feedback",
            data=data,
            column_names=FEEDBACK_COLUMNS,
            do_sync_insert=True,  # fast response times for feedback
        )
        return feedback_id

    def insert_feedback_batch(
        self, rows: list[FeedbackRow]
    ) -> list[str]:
        import uuid

        ids = []
        data = []
        for row in rows:
            fid = str(uuid.uuid4())
            ids.append(fid)
            data.append([
                row.project_id,
                fid,
                row.weave_ref,
                row.feedback_type,
                row.payload,
                row.wb_user_id,
            ])
        self._insert(
            "feedback",
            data=data,
            column_names=FEEDBACK_COLUMNS,
            do_sync_insert=True,
        )
        return ids

    def query_feedback(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = self._query(
            "SELECT * FROM feedback WHERE project_id = {project_id:String}",
            {"project_id": project_id},
        )
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    def purge_feedback(
        self, project_id: str, feedback_ids: list[str]
    ) -> None:
        self._query(
            "ALTER TABLE feedback DELETE "
            "WHERE project_id = {project_id:String} "
            "AND id IN {ids:Array(String)}",
            {"project_id": project_id, "ids": feedback_ids},
        )

    # ── Costs ────────────────────────────────────────────────────────

    def insert_cost(
        self, project_id: str, cost: dict[str, Any]
    ) -> None:
        import uuid

        data = [[project_id, str(uuid.uuid4()), cost]]
        self._insert(
            "costs",
            data=data,
            column_names=["project_id", "id", "data"],
        )

    def query_costs(
        self, project_id: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        result = self._query(
            "SELECT * FROM costs WHERE project_id = {project_id:String}",
            {"project_id": project_id},
        )
        columns = result.column_names
        return [dict(zip(columns, row)) for row in result.result_rows]

    def purge_costs(
        self, project_id: str, cost_ids: list[str]
    ) -> None:
        self._query(
            "ALTER TABLE costs DELETE "
            "WHERE project_id = {project_id:String} "
            "AND id IN {ids:Array(String)}",
            {"project_id": project_id, "ids": cost_ids},
        )

    # ── Row conversion helpers ───────────────────────────────────────

    @staticmethod
    def _call_row_to_list(row: CallRow) -> list[Any]:
        return [
            row.project_id,
            row.id,
            row.trace_id,
            row.parent_id,
            row.op_name,
            row.display_name,
            row.started_at,
            row.ended_at,
            row.inputs,
            row.output,
            row.summary,
            row.exception,
            row.wb_run_id,
            row.wb_user_id,
        ]

    @staticmethod
    def _call_complete_row_to_list(row: CallCompleteRow) -> list[Any]:
        return [
            row.project_id,
            row.id,
            row.trace_id,
            row.parent_id,
            row.op_name,
            row.started_at,
            row.ended_at,
            row.inputs,
            row.output,
            row.summary,
            row.exception,
            row.wb_run_id,
            row.wb_user_id,
        ]
