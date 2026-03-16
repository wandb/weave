"""SQLite storage implementation (Tier 1).

Raw data-access against a SQLite database. No business logic.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from typing import Any

from weave.trace_server.errors import NotFoundError
from weave.trace_server.v2.storage_interface import (
    CallCompleteRow,
    CallRow,
    FeedbackRow,
    FileRow,
    ObjectRow,
    QueryResult,
    StorageInterface,
    TableRowData,
)


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:  # type: ignore[type-arg]
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class SqliteStorage:
    """SQLite implementation of StorageInterface.

    All operations are synchronous, guarded by a threading lock.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._setup_tables()

    # ── Internal helpers ─────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = _dict_factory
        return conn

    def _setup_tables(self) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS calls (
                project_id TEXT NOT NULL,
                id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                parent_id TEXT,
                op_name TEXT,
                display_name TEXT,
                started_at TEXT,
                ended_at TEXT,
                inputs TEXT,
                output TEXT,
                summary TEXT,
                exception TEXT,
                wb_run_id TEXT,
                wb_user_id TEXT,
                PRIMARY KEY (project_id, id)
            );
            CREATE TABLE IF NOT EXISTS objects (
                project_id TEXT NOT NULL,
                object_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                digest TEXT NOT NULL,
                version_index INTEGER,
                val TEXT NOT NULL,
                wb_user_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (project_id, object_id, digest)
            );
            CREATE TABLE IF NOT EXISTS files (
                project_id TEXT NOT NULL,
                digest TEXT NOT NULL,
                content BLOB NOT NULL,
                PRIMARY KEY (project_id, digest)
            );
            CREATE TABLE IF NOT EXISTS feedback (
                project_id TEXT NOT NULL,
                id TEXT NOT NULL,
                weave_ref TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                wb_user_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (project_id, id)
            );
            CREATE TABLE IF NOT EXISTS table_rows (
                project_id TEXT NOT NULL,
                digest TEXT NOT NULL,
                val TEXT NOT NULL,
                PRIMARY KEY (project_id, digest)
            );
            CREATE TABLE IF NOT EXISTS costs (
                project_id TEXT NOT NULL,
                id TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (project_id, id)
            );
        """)
        conn.commit()
        conn.close()

    # ── Calls ────────────────────────────────────────────────────────

    def insert_call(self, row: CallRow) -> None:
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                """INSERT OR REPLACE INTO calls
                (project_id, id, trace_id, parent_id, op_name, display_name,
                 started_at, ended_at, inputs, output, summary, exception,
                 wb_run_id, wb_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.project_id,
                    row.id,
                    row.trace_id,
                    row.parent_id,
                    row.op_name,
                    row.display_name,
                    row.started_at,
                    row.ended_at,
                    json.dumps(row.inputs) if row.inputs else None,
                    json.dumps(row.output) if row.output else None,
                    json.dumps(row.summary) if row.summary else None,
                    row.exception,
                    row.wb_run_id,
                    row.wb_user_id,
                ),
            )
            conn.commit()
            conn.close()

    def insert_call_complete(self, row: CallCompleteRow) -> None:
        # SQLite doesn't have separate tables for complete calls.
        # Reuse insert_call via conversion.
        self.insert_call(
            CallRow(
                project_id=row.project_id,
                id=row.id,
                trace_id=row.trace_id,
                parent_id=row.parent_id,
                op_name=row.op_name,
                started_at=row.started_at,
                ended_at=row.ended_at,
                inputs=row.inputs,
                output=row.output,
                summary=row.summary,
                exception=row.exception,
                wb_run_id=row.wb_run_id,
                wb_user_id=row.wb_user_id,
            )
        )

    def insert_call_batch(self, rows: list[CallRow]) -> None:
        for row in rows:
            self.insert_call(row)

    def query_calls(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: list[dict[str, str]] | None = None,
    ) -> QueryResult:
        conn = self._get_conn()
        sql = "SELECT * FROM calls WHERE project_id = ?"
        params: list[Any] = [project_id]

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            sql += " OFFSET ?"
            params.append(offset)

        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return QueryResult(rows=rows)

    def query_calls_stream(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        sort_by: list[dict[str, str]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        result = self.query_calls(project_id, filters, limit)
        yield from result.rows

    def delete_calls(self, project_id: str, call_ids: list[str]) -> None:
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in call_ids)
        with self._lock:
            conn.execute(
                f"DELETE FROM calls WHERE project_id = ? AND id IN ({placeholders})",
                [project_id, *call_ids],
            )
            conn.commit()
            conn.close()

    def update_call(
        self, project_id: str, call_id: str, updates: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        set_clauses = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        with self._lock:
            conn.execute(
                f"UPDATE calls SET {set_clauses} WHERE project_id = ? AND id = ?",
                [*values, project_id, call_id],
            )
            conn.commit()
            conn.close()

    # ── Objects ──────────────────────────────────────────────────────

    def insert_object(self, row: ObjectRow) -> str:
        conn = self._get_conn()
        digest = row.digest or ""
        with self._lock:
            # Get next version index
            cursor = conn.execute(
                "SELECT MAX(version_index) FROM objects WHERE project_id = ? AND object_id = ?",
                (row.project_id, row.object_id),
            )
            result = cursor.fetchone()
            max_col = list(result.values())[0] if result else None
            version_index = (max_col + 1) if max_col is not None else 0

            conn.execute(
                """INSERT OR IGNORE INTO objects
                (project_id, object_id, kind, digest, version_index, val, wb_user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.project_id,
                    row.object_id,
                    row.kind,
                    digest,
                    version_index,
                    json.dumps(row.val),
                    row.wb_user_id,
                ),
            )
            conn.commit()
            conn.close()
        return digest

    def query_objects(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        metadata_only: bool = False,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        sql = "SELECT * FROM objects WHERE project_id = ?"
        params: list[Any] = [project_id]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows

    def read_object(
        self,
        project_id: str,
        object_id: str,
        digest: str | None = None,
        version_index: int | None = None,
    ) -> dict[str, Any] | None:
        conn = self._get_conn()
        sql = "SELECT * FROM objects WHERE project_id = ? AND object_id = ?"
        params: list[Any] = [project_id, object_id]
        if digest:
            sql += " AND digest = ?"
            params.append(digest)
        if version_index is not None:
            sql += " AND version_index = ?"
            params.append(version_index)
        sql += " ORDER BY version_index DESC LIMIT 1"
        row = conn.execute(sql, params).fetchone()
        conn.close()
        return row

    def delete_object(
        self, project_id: str, object_id: str, digests: list[str]
    ) -> None:
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in digests)
        with self._lock:
            conn.execute(
                f"DELETE FROM objects WHERE project_id = ? AND object_id = ? AND digest IN ({placeholders})",
                [project_id, object_id, *digests],
            )
            conn.commit()
            conn.close()

    # ── Tags & Aliases ───────────────────────────────────────────────
    # Simplified for SQLite — production uses separate tables.

    def insert_tags(
        self, project_id: str, object_id: str, tags: list[str]
    ) -> None:
        pass  # SQLite stub

    def remove_tags(
        self, project_id: str, object_id: str, tags: list[str]
    ) -> None:
        pass

    def insert_aliases(
        self, project_id: str, object_id: str, aliases: dict[str, str]
    ) -> None:
        pass

    def remove_aliases(
        self, project_id: str, object_id: str, aliases: list[str]
    ) -> None:
        pass

    def query_tags(self, project_id: str) -> list[str]:
        return []

    def query_aliases(self, project_id: str) -> list[dict[str, str]]:
        return []

    # ── Tables ───────────────────────────────────────────────────────

    def insert_table(
        self, project_id: str, rows: list[TableRowData]
    ) -> str:
        conn = self._get_conn()
        with self._lock:
            for row in rows:
                conn.execute(
                    "INSERT OR IGNORE INTO table_rows (project_id, digest, val) VALUES (?, ?, ?)",
                    (row.project_id, row.digest, json.dumps(row.val)),
                )
            conn.commit()
            conn.close()
        # Return a composite digest — simplified
        return "|".join(r.digest for r in rows) if rows else ""

    def update_table(
        self,
        project_id: str,
        base_digest: str,
        updates: list[dict[str, Any]],
    ) -> str:
        # Simplified — production handles diffing
        return base_digest

    def query_table(
        self,
        project_id: str,
        digest: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> QueryResult:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM table_rows WHERE project_id = ? AND digest = ?",
            (project_id, digest),
        ).fetchall()
        conn.close()
        return QueryResult(rows=rows)

    def query_table_stats(
        self, project_id: str, digest: str
    ) -> dict[str, Any]:
        result = self.query_table(project_id, digest)
        return {"count": len(result.rows)}

    # ── Refs ─────────────────────────────────────────────────────────

    def read_refs_batch(
        self, refs: list[str]
    ) -> list[dict[str, Any] | None]:
        # Simplified — production parses ref URIs
        return [None for _ in refs]

    # ── Files ────────────────────────────────────────────────────────

    def insert_file(self, row: FileRow) -> str:
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                "INSERT OR IGNORE INTO files (project_id, digest, content) VALUES (?, ?, ?)",
                (row.project_id, row.digest, row.content),
            )
            conn.commit()
            conn.close()
        return row.digest

    def read_file(self, project_id: str, digest: str) -> bytes:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content FROM files WHERE project_id = ? AND digest = ?",
            (project_id, digest),
        ).fetchone()
        conn.close()
        if row is None:
            raise NotFoundError(f"File {digest} not found")
        return row["content"]

    # ── Feedback ─────────────────────────────────────────────────────

    def insert_feedback(self, row: FeedbackRow) -> str:
        import uuid

        feedback_id = str(uuid.uuid4())
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                """INSERT INTO feedback
                (project_id, id, weave_ref, feedback_type, payload, wb_user_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    row.project_id,
                    feedback_id,
                    row.weave_ref,
                    row.feedback_type,
                    json.dumps(row.payload),
                    row.wb_user_id,
                ),
            )
            conn.commit()
            conn.close()
        return feedback_id

    def insert_feedback_batch(
        self, rows: list[FeedbackRow]
    ) -> list[str]:
        return [self.insert_feedback(row) for row in rows]

    def query_feedback(
        self,
        project_id: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM feedback WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        conn.close()
        return rows

    def purge_feedback(
        self, project_id: str, feedback_ids: list[str]
    ) -> None:
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in feedback_ids)
        with self._lock:
            conn.execute(
                f"DELETE FROM feedback WHERE project_id = ? AND id IN ({placeholders})",
                [project_id, *feedback_ids],
            )
            conn.commit()
            conn.close()

    # ── Costs ────────────────────────────────────────────────────────

    def insert_cost(
        self, project_id: str, cost: dict[str, Any]
    ) -> None:
        import uuid

        conn = self._get_conn()
        cost_id = str(uuid.uuid4())
        with self._lock:
            conn.execute(
                "INSERT INTO costs (project_id, id, data) VALUES (?, ?, ?)",
                (project_id, cost_id, json.dumps(cost)),
            )
            conn.commit()
            conn.close()

    def query_costs(
        self, project_id: str, filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM costs WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        conn.close()
        return rows

    def purge_costs(
        self, project_id: str, cost_ids: list[str]
    ) -> None:
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in cost_ids)
        with self._lock:
            conn.execute(
                f"DELETE FROM costs WHERE project_id = ? AND id IN ({placeholders})",
                [project_id, *cost_ids],
            )
            conn.commit()
            conn.close()
