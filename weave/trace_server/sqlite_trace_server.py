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
from weave.trace_server.refs_internal import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
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
                op_name TEXT,
                started_at TEXT,
                ended_at TEXT,
                exception TEXT,
                attributes TEXT,
                inputs TEXT,
                input_refs TEXT,
                output TEXT,
                output_refs TEXT,
                summary TEXT,
                wb_user_id TEXT,
                wb_run_id TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                project_id TEXT,
                object_id TEXT,
                created_at TEXT,
                kind TEXT,
                base_object_class TEXT,
                refs TEXT,
                val_dump TEXT,
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
                    op_name,
                    started_at,
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
                    req.start.op_name,
                    req.start.started_at.isoformat(),
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
        parsable_output = req.end.output
        if not isinstance(parsable_output, dict):
            parsable_output = {"output": parsable_output}
        parsable_output = cast(dict, parsable_output)
        with self.lock:
            cursor.execute(
                """UPDATE calls SET
                    ended_at = ?,
                    exception = ?,
                    output = ?,
                    output_refs = ?,
                    summary = ?
                WHERE id = ?""",
                (
                    req.end.ended_at.isoformat(),
                    req.end.exception,
                    json.dumps(req.end.output),
                    json.dumps(
                        extract_refs_from_values(list(parsable_output.values()))
                    ),
                    json.dumps(req.end.summary),
                    req.end.id,
                ),
            )
            conn.commit()
        return tsi.CallEndRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return tsi.CallReadRes(
            call=self.calls_query(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    limit=1,
                    filter=tsi._CallsFilter(call_ids=[req.id]),
                )
            ).calls[0]
        )

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        print("REQ", req)
        conn, cursor = get_conn_cursor(self.db_path)
        conds = []
        filter = req.filter
        if filter:
            if filter.op_names:
                or_conditions: list[str] = []

                non_wildcarded_names: list[str] = []
                wildcarded_names: list[str] = []
                for name in filter.op_names:
                    if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                        wildcarded_names.append(name)
                    else:
                        non_wildcarded_names.append(name)

                if non_wildcarded_names:
                    in_expr = ", ".join((f"'{x}'" for x in non_wildcarded_names))
                    or_conditions += [f"op_name IN ({', '.join({in_expr})})"]

                for name_ndx, name in enumerate(wildcarded_names):
                    like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + "%"
                    or_conditions.append(f"op_name LIKE '{like_name}'")

                if or_conditions:
                    conds.append("(" + " OR ".join(or_conditions) + ")")

            if filter.input_refs:
                or_conditions = []
                for ref in filter.input_refs:
                    or_conditions.append(f"input_refs LIKE '%{ref}%'")
                conds.append("(" + " OR ".join(or_conditions) + ")")
            if filter.output_refs:
                or_conditions = []
                for ref in filter.output_refs:
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

        order_by = (
            None if not req.sort_by else [(s.field, s.direction) for s in req.sort_by]
        )
        if order_by is not None:
            order_parts = []
            for field, direction in order_by:
                json_path: Optional[str] = None
                if field.startswith("inputs"):
                    field = "inputs" + field[len("inputs") :]
                    if field.startswith("inputs."):
                        field = "inputs"
                        json_path = field[len("inputs.") :]
                elif field.startswith("output"):
                    field = "output" + field[len("output") :]
                    if field.startswith("output."):
                        field = "output"
                        json_path = field[len("output.") :]
                elif field.startswith("attributes"):
                    field = "attributes_dump" + field[len("attributes") :]
                elif field.startswith("summary"):
                    field = "summary_dump" + field[len("summary") :]
                elif field == ("latency"):
                    field = "ended_at - started_at"

                assert direction in [
                    "ASC",
                    "DESC",
                    "asc",
                    "desc",
                ], f"Invalid order_by direction: {direction}"
                if json_path:
                    field = f"json_extract({field}, '$.{json_path}')"
                order_parts.append(f"{field} {direction}")

            order_by_part = ", ".join(order_parts)
            query += f"ORDER BY {order_by_part}"

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
                    op_name=row[4],
                    started_at=row[5],
                    ended_at=row[6],
                    exception=row[7],
                    attributes=json.loads(row[8]),
                    inputs=json.loads(row[9]),
                    output=None if row[11] is None else json.loads(row[11]),
                    output_refs=None if row[12] is None else json.loads(row[12]),
                    summary=json.loads(row[13]) if row[13] else None,
                    wb_user_id=row[14],
                    wb_run_id=row[15],
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
                """SELECT COUNT(*) FROM objects WHERE project_id = ? AND object_id = ?""",
                (req.obj.project_id, req_obj.object_id),
            )
            version_index = cursor.fetchone()[0]

            cursor.execute(
                """INSERT OR IGNORE INTO objects (
                    project_id,
                    object_id,
                    created_at,
                    kind,
                    base_object_class,
                    refs,
                    val_dump,
                    digest,
                    version_index,
                    is_latest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req_obj.project_id,
                    req_obj.object_id,
                    datetime.datetime.now().isoformat(),
                    get_kind(req_obj.val),
                    get_base_object_class(req_obj.val),
                    json.dumps([]),
                    json_val,
                    digest,
                    version_index,
                    1,
                ),
            )
            conn.commit()
        return tsi.ObjCreateRes(digest=digest)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        conds = [
            f"object_id = '{req.object_id}'",
        ]
        if req.digest == "latest":
            conds.append("is_latest = 1")
        else:
            conds.append(f"digest = '{req.digest}'")
        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")

        return tsi.ObjReadRes(obj=objs[0])

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conds: list[str] = []
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    conds.append("kind = 'op'")
                else:
                    conds.append("kind != 'op'")
            if req.filter.object_ids:
                in_list = ", ".join([f"'{n}'" for n in req.filter.object_ids])
                conds.append(f"object_id IN ({in_list})")
            if req.filter.latest_only:
                conds.append("is_latest = 1")
            if req.filter.base_object_classes:
                in_list = ", ".join([f"'{t}'" for t in req.filter.base_object_classes])
                conds.append(f"base_object_class IN ({in_list})")

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
            digest = table_hasher.hexdigest()

            cursor.execute(
                "INSERT OR IGNORE INTO tables (project_id, digest, row_digests) VALUES (?, ?, ?)",
                (req.table.project_id, digest, json.dumps(row_digests)),
            )
            conn.commit()

        return tsi.TableCreateRes(digest=digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        conds = []
        if req.filter:
            raise NotImplementedError("Table filter not implemented")
        else:
            conds.append("1 = 1")
        rows = self._table_query(req.project_id, req.digest, conditions=conds)

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
                f"object_id = '{r.name}'",
                f"digest = '{r.digest}'",
            ]
            objs = self._select_objs_query(
                f"{r.entity}/{r.project}",
                conditions=conds,
            )
            if len(objs) == 0:
                raise NotFoundError(f"Obj {r.name}:{r.digest} not found")
            obj = objs[0]
            val = obj.val
            extra = r.extra
            for extra_index in range(0, len(extra), 2):
                op, arg = extra[extra_index], extra[extra_index + 1]
                if op == DICT_KEY_EDGE_NAME:
                    val = val[arg]
                elif op == OBJECT_ATTR_EDGE_NAME:
                    val = val[arg]
                elif op == LIST_INDEX_EDGE_NAME:
                    val = val[int(arg)]
                elif op == TABLE_ROW_ID_EDGE_NAME:
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
        digest: str,
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
            (project_id, digest),
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
                    object_id=row[1],
                    created_at=row[2],
                    kind=row[3],
                    base_object_class=row[4],
                    val=json.loads(row[6]),
                    digest=row[7],
                    version_index=row[8],
                    is_latest=row[9],
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


def get_kind(val: Any) -> str:
    val_type = get_type(val)
    if val_type == "Op":
        return "op"
    return "object"


def get_base_object_class(val: Any) -> Optional[str]:
    if isinstance(val, dict):
        if "_bases" in val:
            if isinstance(val["_bases"], list):
                if len(val["_bases"]) >= 2:
                    if val["_bases"][-1] == "BaseModel":
                        if val["_bases"][-2] == "Object":
                            if len(val["_bases"]) > 2:
                                return val["_bases"][-3]
                            elif "_class_name" in val:
                                return val["_class_name"]
    return None
