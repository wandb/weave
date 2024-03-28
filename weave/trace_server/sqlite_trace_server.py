# Sqlite Trace Server

from typing import cast, Optional, Any, Union
import threading

import contextvars
import contextlib
import datetime
import json
import hashlib
import sqlite3


from .trace_server_interface_util import (
    extract_refs_from_values,
    str_digest,
    bytes_digest,
)
from . import trace_server_interface as tsi

from weave.trace import refs
from weave.trace_server.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
)

MAX_FLUSH_COUNT = 10000
MAX_FLUSH_AGE = 15


class NotFoundError(Exception):
    pass


_conn_cursor: contextvars.ContextVar[
    Optional[tuple[sqlite3.Connection, sqlite3.Cursor]]
] = contextvars.ContextVar("conn_cursor", default=None)


def get_conn_cursor(db_path: str) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    # conn_cursor = _conn_cursor.get()
    conn_cursor = None
    if conn_cursor is None:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        conn_cursor = (conn, cursor)
        _conn_cursor.set(conn_cursor)
    return conn_cursor


class SqliteTraceServer(tsi.TraceServerInterface):
    def __init__(self, db_path: str):
        self.lock = threading.Lock()
        self.db_path = db_path

    def drop_tables(self) -> None:
        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute("DROP TABLE IF EXISTS calls")
        cursor.execute("DROP TABLE IF EXISTS objects")
        cursor.execute("DROP TABLE IF EXISTS tables")
        cursor.execute("DROP TABLE IF EXISTS table_rows")

    def setup_tables(self) -> None:
        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                project_id TEXT,
                id TEXT PRIMARY KEY,
                trace_id TEXT,
                parent_id TEXT,
                name TEXT,
                start_datetime TEXT,
                end_datetime TEXT,
                exception TEXT,
                attributes TEXT,
                inputs TEXT,
                input_refs TEXT,
                outputs TEXT,
                output_refs TEXT,
                wb_user_id TEXT,
                wb_run_id TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                project_id TEXT,
                name TEXT,
                created_at TEXT,
                type TEXT,
                refs TEXT,
                val TEXT,
                digest TEXT UNIQUE,
                version_index INTEGER,
                is_latest INTEGER
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tables (
                project_id TEXT,
                digest TEXT UNIQUE,
                row_digests STRING)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS table_rows (
                project_id TEXT,
                digest TEXT UNIQUE,
                val TEXT)
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                project_id TEXT,
                digest TEXT UNIQUE,
                val BLOB)
            """
        )

    # Creates a new call
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        conn, cursor = get_conn_cursor(self.db_path)
        if req.start.trace_id is None:
            raise ValueError("trace_id is required")
        if req.start.id is None:
            raise ValueError("id is required")
        with self.lock:
            # Converts the user-provided call details into a clickhouse schema.
            # This does validation and conversion of the input data as well
            # as enforcing business rules and defaults
            cursor.execute(
                """INSERT INTO calls (
                    project_id,
                    id,
                    trace_id,
                    parent_id,
                    name,
                    start_datetime,
                    attributes,
                    inputs,
                    input_refs,
                    wb_user_id,
                    wb_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req.start.project_id,
                    req.start.id,
                    req.start.trace_id,
                    req.start.parent_id,
                    req.start.name,
                    req.start.start_datetime.isoformat(),
                    json.dumps(req.start.attributes),
                    json.dumps(req.start.inputs),
                    json.dumps(
                        extract_refs_from_values(list(req.start.inputs.values()))
                    ),
                    req.start.wb_user_id,
                    req.start.wb_run_id,
                ),
            )
            conn.commit()

        # Returns the id of the newly created call
        return tsi.CallStartRes(
            id=req.start.id,
            trace_id=req.start.trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        conn, cursor = get_conn_cursor(self.db_path)
        with self.lock:
            cursor.execute(
                """UPDATE calls SET
                    end_datetime = ?,
                    exception = ?,
                    outputs = ?,
                    output_refs = ?
                WHERE id = ?""",
                (
                    req.end.end_datetime.isoformat(),
                    req.end.exception,
                    json.dumps(req.end.outputs),
                    json.dumps(
                        extract_refs_from_values(list(req.end.outputs.values()))
                    ),
                    req.end.id,
                ),
            )
            conn.commit()
        return tsi.CallEndRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        raise NotImplementedError()

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        print("REQ", req)
        conn, cursor = get_conn_cursor(self.db_path)
        conds = []
        filter = req.filter
        if filter:
            if filter.op_version_refs:
                or_conditions: list[str] = []

                non_wildcarded_names: list[str] = []
                wildcarded_names: list[str] = []
                for name in filter.op_version_refs:
                    if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                        wildcarded_names.append(name)
                    else:
                        non_wildcarded_names.append(name)

                if non_wildcarded_names:
                    in_expr = ", ".join((f"'{x}'" for x in non_wildcarded_names))
                    or_conditions += [f"name IN ({', '.join({in_expr})})"]

                for name_ndx, name in enumerate(wildcarded_names):
                    like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + "%"
                    or_conditions.append(f"name LIKE '{like_name}'")

                if or_conditions:
                    conds.append("(" + " OR ".join(or_conditions) + ")")

            if filter.input_object_version_refs:
                or_conditions = []
                for ref in filter.input_object_version_refs:
                    or_conditions.append(f"input_refs LIKE '%{ref}%'")
                conds.append("(" + " OR ".join(or_conditions) + ")")
            if filter.output_object_version_refs:
                or_conditions = []
                for ref in filter.output_object_version_refs:
                    or_conditions.append(f"output_refs LIKE '%{ref}%'")
                conds.append("(" + " OR ".join(or_conditions) + ")")
            if filter.parent_ids:
                in_expr = ", ".join((f"'{x}'" for x in filter.parent_ids))
                conds += [f"parent_id IN ({in_expr})"]
            if filter.trace_ids:
                in_expr = ", ".join((f"'{x}'" for x in filter.trace_ids))
                conds += [f"trace_id IN ({in_expr})"]
            if filter.call_ids:
                in_expr = ", ".join((f"'{x}'" for x in filter.call_ids))
                conds += [f"id IN ({in_expr})"]
            if filter.trace_roots_only:
                conds.append("parent_id IS NULL")
            if filter.wb_run_ids:
                in_expr = ", ".join((f"'{x}'" for x in filter.wb_run_ids))
                conds += [f"wb_run_id IN ({in_expr})"]

        query = f"SELECT * FROM calls WHERE project_id = '{req.project_id}'"

        conditions_part = " AND ".join(conds)

        if conditions_part:
            query += f" AND {conditions_part}"

        limit = req.limit or -1
        if limit:
            query += f" LIMIT {limit}"
        if req.offset:
            query += f" OFFSET {req.offset}"
        print("QUERY", query)

        cursor.execute(query)

        query_result = cursor.fetchall()
        return tsi.CallsQueryRes(
            calls=[
                tsi.CallSchema(
                    project_id=row[0],
                    id=row[1],
                    trace_id=row[2],
                    parent_id=row[3],
                    name=row[4],
                    start_datetime=row[5],
                    end_datetime=row[6],
                    exception=row[7],
                    attributes=json.loads(row[8]),
                    inputs=json.loads(row[9]),
                    outputs=None if row[11] is None else json.loads(row[11]),
                    wb_user_id=row[13],
                    wb_run_id=row[14],
                )
                for row in query_result
            ]
        )

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise NotImplementedError()

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        raise NotImplementedError()

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        raise NotImplementedError()

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        conn, cursor = get_conn_cursor(self.db_path)
        json_val = json.dumps(req.obj.val)
        digest = str_digest(json_val)

        req_obj = req.obj
        # TODO: version index isn't right here, what if we delete stuff?
        with self.lock:
            cursor.execute("BEGIN TRANSACTION")
            # first get version count
            cursor.execute(
                """SELECT COUNT(*) FROM objects WHERE project_id = ? AND name = ?""",
                (req.obj.project_id, req_obj.name),
            )
            version_index = cursor.fetchone()[0]

            cursor.execute(
                """INSERT OR IGNORE INTO objects (
                    project_id,
                    name,
                    created_at,
                    type,
                    refs,
                    val,
                    digest,
                    version_index,
                    is_latest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req_obj.project_id,
                    req_obj.name,
                    datetime.datetime.now().isoformat(),
                    get_type(req_obj.val),
                    json.dumps([]),
                    json_val,
                    digest,
                    version_index,
                    1,
                ),
            )
            conn.commit()
        return tsi.ObjCreateRes(version_digest=digest)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        conds = [
            f"name = '{req.name}'",
        ]
        if req.version_digest == "latest":
            conds.append("is_latest = 1")
        else:
            conds.append(f"digest = '{req.version_digest}'")
        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.name}:{req.version_digest} not found")

        return tsi.ObjReadRes(obj=objs[0])

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conds: list[str] = []
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    conds.append("type = 'Op'")
                else:
                    conds.append("type != 'Op'")
            if req.filter.object_names:
                in_list = ", ".join([f"'{n}'" for n in req.filter.object_names])
                conds.append(f"name IN ({in_list})")
            if req.filter.latest_only:
                conds.append("is_latest = 1")

        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
        )

        return tsi.ObjQueryRes(objs=objs)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        conn, cursor = get_conn_cursor(self.db_path)
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise ValueError("All rows must be dictionaries")
            row_json = json.dumps(r)
            row_digest = str_digest(row_json)
            insert_rows.append((req.table.project_id, row_digest, row_json))
        with self.lock:
            cursor.executemany(
                "INSERT OR IGNORE INTO table_rows (project_id, digest, val) VALUES (?, ?, ?)",
                insert_rows,
            )

            row_digests = [r[1] for r in insert_rows]

            table_hasher = hashlib.sha256()
            for row_digest in row_digests:
                table_hasher.update(row_digest.encode())
            table_digest = table_hasher.hexdigest()

            cursor.execute(
                "INSERT OR IGNORE INTO tables (project_id, digest, row_digests) VALUES (?, ?, ?)",
                (req.table.project_id, table_digest, json.dumps(row_digests)),
            )
            conn.commit()

        return tsi.TableCreateRes(digest=table_digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        conds = []
        if req.filter:
            raise NotImplementedError("Table filter not implemented")
        else:
            conds.append("1 = 1")
        rows = self._table_query(req.project_id, req.table_digest, conditions=conds)

        return tsi.TableQueryRes(rows=rows)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # TODO: This reads one ref at a time, it should read them in batches
        # where it can. Like it should group by object that we need to read.
        # And it should also batch into table refs (like when we are reading a bunch
        # of rows from a single Dataset)
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        parsed_refs = [refs.parse_uri(r) for r in req.refs]
        if any(isinstance(r, refs.TableRef) for r in parsed_refs):
            raise ValueError("Table refs not supported")
        parsed_obj_refs = cast(list[refs.ObjectRef], parsed_refs)

        def read_ref(r: refs.ObjectRef) -> Any:
            conds = [
                f"name = '{r.name}'",
                f"digest = '{r.version}'",
            ]
            objs = self._select_objs_query(
                f"{r.entity}/{r.project}",
                conditions=conds,
            )
            if len(objs) == 0:
                raise NotFoundError(f"Obj {r.name}:{r.version} not found")
            obj = objs[0]
            val = obj.val
            extra = r.extra
            for extra_index in range(0, len(extra), 2):
                op, arg = extra[extra_index], extra[extra_index + 1]
                if op == "key":
                    val = val[arg]
                elif op == "atr":
                    val = val[arg]
                elif op == "ndx":
                    val = val[int(arg)]
                elif op == "id":
                    if isinstance(val, str) and val.startswith("weave://"):
                        table_ref = refs.parse_uri(val)
                        if not isinstance(table_ref, refs.TableRef):
                            raise ValueError(
                                "invalid data layout encountered, expected TableRef when resolving id"
                            )
                        row = self._table_row_read(
                            project_id=f"{table_ref.entity}/{table_ref.project}",
                            row_digest=arg,
                        )
                        val = row.val
                    else:
                        raise ValueError(
                            "invalid data layout encountered, expected TableRef when resolving id"
                        )
                else:
                    raise ValueError(f"Unknown ref type: {extra[extra_index]}")
            return val

        return tsi.RefsReadBatchRes(vals=[read_ref(r) for r in parsed_obj_refs])

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        conn, cursor = get_conn_cursor(self.db_path)
        digest = bytes_digest(req.content)
        with self.lock:
            cursor.execute(
                "INSERT OR IGNORE INTO files (project_id, digest, val) VALUES (?, ?, ?)",
                (
                    req.project_id,
                    digest,
                    req.content,
                ),
            )
            conn.commit()
        return tsi.FileCreateRes(digest=digest)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute(
            "SELECT val FROM files WHERE project_id = ? AND digest = ?",
            (req.project_id, req.digest),
        )
        query_result = cursor.fetchone()
        if query_result is None:
            raise NotFoundError(f"File {req.digest} not found")
        return tsi.FileContentReadRes(content=query_result[0])

    def _table_query(
        self,
        project_id: str,
        table_digest: str,
        conditions: Optional[list[str]] = None,
        limit: Optional[int] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> list[tsi.TableRowSchema]:
        conn, cursor = get_conn_cursor(self.db_path)
        conds = ["project_id = {project_id: String}"]
        if conditions:
            conds.extend(conditions)

        predicate = " AND ".join(conds)
        # First get the row IDs by querying tables
        cursor.execute(
            """
            WITH OrderedDigests AS (
                SELECT
                    json_each.value AS digest
                FROM
                    tables,
                    json_each(tables.row_digests)
                WHERE
                    tables.project_id = ? AND
                    tables.digest = ?
                ORDER BY
                    json_each.id
            )
            SELECT
                table_rows.digest,
                table_rows.val
            FROM
                OrderedDigests
                JOIN table_rows ON OrderedDigests.digest = table_rows.digest
            """,
            (project_id, table_digest),
        )
        query_result = cursor.fetchall()
        return [
            tsi.TableRowSchema(digest=r[0], val=json.loads(r[1])) for r in query_result
        ]

    def _table_row_read(self, project_id: str, row_digest: str) -> tsi.TableRowSchema:
        conn, cursor = get_conn_cursor(self.db_path)
        # Now get the rows
        cursor.execute(
            """
            SELECT digest, val FROM table_rows
            WHERE project_id = ? AND digest = ?
            """,
            [project_id, row_digest],
        )
        query_result = cursor.fetchone()
        if query_result is None:
            raise NotFoundError(f"Row {row_digest} not found")
        return tsi.TableRowSchema(
            digest=query_result[0], val=json.loads(query_result[1])
        )

    def _select_objs_query(
        self,
        project_id: str,
        conditions: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> list[tsi.ObjSchema]:
        conn, cursor = get_conn_cursor(self.db_path)
        pred = " AND ".join(conditions or ["1 = 1"])
        cursor.execute(
            """SELECT * FROM objects WHERE project_id = ? AND """ + pred,
            (project_id,),
        )
        query_result = cursor.fetchall()
        result: list[tsi.ObjSchema] = []
        for row in query_result:
            result.append(
                tsi.ObjSchema(
                    project_id=f"{row[0]}",
                    name=row[1],
                    created_at=row[2],
                    type=row[3],
                    val=json.loads(row[5]),
                    digest=row[6],
                    version_index=row[7],
                    is_latest=row[8],
                )
            )

        return result


def get_type(val: Any) -> str:
    if val == None:
        return "none"
    elif isinstance(val, dict):
        if "_type" in val:
            if "weave_type" in val:
                return val["weave_type"]["type"]
            return val["_type"]
        return "dict"
    elif isinstance(val, list):
        return "list"
    return "unknown"
