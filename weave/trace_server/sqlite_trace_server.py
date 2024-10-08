# Sqlite Trace Server

import contextvars
import datetime
import hashlib
import json
import sqlite3
import threading
from typing import Any, Dict, Iterator, Optional, cast
from zoneinfo import ZoneInfo

import emoji

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.emoji_util import detone_emojis
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.ids import generate_id
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import Row, quote_json_path
from weave.trace_server.trace_server_common import (
    digest_is_version_like,
    empty_str_to_none,
    get_nested_key,
    hydrate_calls_with_feedback,
    make_derived_summary_fields,
    make_feedback_query_req,
    set_nested_key,
)
from weave.trace_server.trace_server_interface_util import (
    WILDCARD_ARTIFACT_VERSION_AND_PATH,
    assert_non_null_wb_user_id,
    bytes_digest,
    extract_refs_from_values,
    str_digest,
)
from weave.trace_server.validation import object_id_validator

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
        cursor.execute(TABLE_FEEDBACK.drop_sql())
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
                wb_run_id TEXT,
                deleted_at TEXT,
                display_name TEXT
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
                digest TEXT,
                version_index INTEGER,
                is_latest INTEGER,
                deleted_at TEXT,
                primary key (project_id, kind, object_id, digest)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tables (
                project_id TEXT,
                digest TEXT UNIQUE,
                row_digests STRING
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS table_rows (
                project_id TEXT,
                digest TEXT UNIQUE,
                val TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                project_id TEXT,
                digest TEXT,
                val BLOB,
                primary key (project_id, digest)
            )
            """
        )
        cursor.execute(TABLE_FEEDBACK.create_sql())

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
                    display_name,
                    started_at,
                    attributes,
                    inputs,
                    input_refs,
                    wb_user_id,
                    wb_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req.start.project_id,
                    req.start.id,
                    req.start.trace_id,
                    req.start.parent_id,
                    req.start.op_name,
                    req.start.display_name,
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
        calls = self.calls_query(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                limit=1,
                filter=tsi.CallsFilter(call_ids=[req.id]),
            )
        ).calls
        return tsi.CallReadRes(call=calls[0] if calls else None)

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

        if req.query:
            # This is the mongo-style query
            def process_operation(operation: tsi_query.Operation) -> str:
                cond = None

                if isinstance(operation, tsi_query.AndOperation):
                    lhs_part = process_operand(operation.and_[0])
                    rhs_part = process_operand(operation.and_[1])
                    cond = f"({lhs_part} AND {rhs_part})"
                elif isinstance(operation, tsi_query.OrOperation):
                    lhs_part = process_operand(operation.or_[0])
                    rhs_part = process_operand(operation.or_[1])
                    cond = f"({lhs_part} OR {rhs_part})"
                elif isinstance(operation, tsi_query.NotOperation):
                    operand_part = process_operand(operation.not_[0])
                    cond = f"(NOT ({operand_part}))"
                elif isinstance(operation, tsi_query.EqOperation):
                    lhs_part = process_operand(operation.eq_[0])
                    rhs_part = process_operand(operation.eq_[1])
                    cond = f"({lhs_part} = {rhs_part})"
                elif isinstance(operation, tsi_query.GtOperation):
                    lhs_part = process_operand(operation.gt_[0])
                    rhs_part = process_operand(operation.gt_[1])
                    cond = f"({lhs_part} > {rhs_part})"
                elif isinstance(operation, tsi_query.GteOperation):
                    lhs_part = process_operand(operation.gte_[0])
                    rhs_part = process_operand(operation.gte_[1])
                    cond = f"({lhs_part} >= {rhs_part})"
                elif isinstance(operation, tsi_query.InOperation):
                    lhs_part = process_operand(operation.in_[0])
                    rhs_part = ",".join(process_operand(op) for op in operation.in_[1])
                    cond = f"({lhs_part} IN ({rhs_part}))"
                elif isinstance(operation, tsi_query.ContainsOperation):
                    lhs_part = process_operand(operation.contains_.input)
                    rhs_part = process_operand(operation.contains_.substr)
                    if operation.contains_.case_insensitive:
                        lhs_part = f"LOWER({lhs_part})"
                        rhs_part = f"LOWER({rhs_part})"
                    cond = f"instr({lhs_part}, {rhs_part})"
                else:
                    raise ValueError(f"Unknown operation type: {operation}")

                return cond

            def process_operand(operand: tsi_query.Operand) -> str:
                if isinstance(operand, tsi_query.LiteralOperation):
                    return json.dumps(operand.literal_)
                elif isinstance(operand, tsi_query.GetFieldOperator):
                    field = _transform_external_calls_field_to_internal_calls_field(
                        operand.get_field_, None
                    )
                    return field
                elif isinstance(operand, tsi_query.ConvertOperation):
                    field = process_operand(operand.convert_.input)
                    convert_to = operand.convert_.to
                    if convert_to == "int":
                        sql_type = "INT"
                    elif convert_to == "double":
                        sql_type = "FLOAT"
                    elif convert_to == "bool":
                        sql_type = "BOOL"
                    elif convert_to == "string":
                        sql_type = "TEXT"
                    else:
                        raise ValueError(f"Unknown cast: {convert_to}")
                    return f"CAST({field} AS {sql_type})"
                elif isinstance(
                    operand,
                    (
                        tsi_query.AndOperation,
                        tsi_query.OrOperation,
                        tsi_query.NotOperation,
                        tsi_query.EqOperation,
                        tsi_query.GtOperation,
                        tsi_query.GteOperation,
                        tsi_query.InOperation,
                        tsi_query.ContainsOperation,
                    ),
                ):
                    return process_operation(operand)
                else:
                    raise ValueError(f"Unknown operand type: {operand}")

            filter_cond = process_operation(req.query.expr_)

            conds.append(filter_cond)

        required_columns = ["id", "trace_id", "project_id", "op_name", "started_at"]
        select_columns = list(tsi.CallSchema.model_fields.keys())
        if req.columns:
            # TODO(gst): allow json fields to be selected
            simple_columns = [x.split(".")[0] for x in req.columns]
            select_columns = [x for x in simple_columns if x in select_columns]
            # add required columns, preserving requested column order
            select_columns += [
                rcol for rcol in required_columns if rcol not in select_columns
            ]
        query = f"SELECT {', '.join(select_columns)} FROM calls WHERE deleted_at IS NULL AND project_id = '{req.project_id}'"

        conditions_part = " AND ".join(conds)

        if conditions_part:
            query += f" AND {conditions_part}"

        # Match the batch server:
        if req.sort_by is None:
            order_by = [("started_at", "asc")]
        elif len(req.sort_by) == 0:
            order_by = None
        else:
            order_by = [(s.field, s.direction) for s in req.sort_by]

        if order_by is not None:
            order_parts = []
            for field, direction in order_by:
                json_path: Optional[str] = None
                if field.startswith("inputs"):
                    field = "inputs" + field[len("inputs") :]
                    if field.startswith("inputs."):
                        json_path = field[len("inputs.") :]
                        field = "inputs"
                elif field.startswith("output"):
                    field = "output" + field[len("output") :]
                    if field.startswith("output."):
                        json_path = field[len("output.") :]
                        field = "output"
                elif field.startswith("attributes"):
                    field = "attributes_dump" + field[len("attributes") :]
                elif field.startswith("summary"):
                    field = "summary_dump" + field[len("summary") :]

                assert direction in [
                    "ASC",
                    "DESC",
                    "asc",
                    "desc",
                ], f"Invalid order_by direction: {direction}"
                if json_path:
                    field = f"json_extract({field}, '{quote_json_path(json_path)}')"
                order_parts.append(f"{field} {direction}")

            order_by_part = ", ".join(order_parts)
            query += f" ORDER BY {order_by_part}"

        limit = req.limit or -1
        if limit:
            query += f" LIMIT {limit}"
        if req.offset:
            if limit is None:
                query += " LIMIT -1"
            query += f" OFFSET {req.offset}"

        print("QUERY", query)

        cursor.execute(query)

        query_result = cursor.fetchall()
        calls = []
        for row in query_result:
            call_dict = {k: v for k, v in zip(select_columns, row)}
            # convert json dump fields into json
            for json_field in ["attributes", "summary", "inputs", "output"]:
                if call_dict.get(json_field):
                    # load json
                    data = json.loads(call_dict[json_field])
                    # do ref expansion
                    if req.expand_columns:
                        data = self._expand_refs(
                            {json_field: data}, req.expand_columns
                        )[json_field]
                    call_dict[json_field] = data
            # convert empty string display_names to None
            if "display_name" in call_dict:
                call_dict["display_name"] = empty_str_to_none(call_dict["display_name"])
            # fill in derived summary fields
            call_dict["summary"] = make_derived_summary_fields(
                summary=call_dict.get("summary") or {},
                op_name=call_dict["op_name"],
                started_at=datetime.datetime.fromisoformat(call_dict["started_at"]),
                ended_at=(
                    datetime.datetime.fromisoformat(call_dict["ended_at"])
                    if call_dict.get("ended_at")
                    else None
                ),
                exception=call_dict.get("exception"),
                display_name=call_dict.get("display_name"),
            )
            # fill in missing required fields with defaults
            for col, mfield in tsi.CallSchema.model_fields.items():
                if mfield.is_required() and col not in call_dict:
                    if isinstance(mfield.annotation, str):
                        call_dict[col] = ""
                    elif isinstance(
                        mfield.annotation, (datetime.datetime, datetime.date)
                    ):
                        raise ValueError(f"Field '{col}' is required for selection")
                    else:
                        call_dict[col] = {}
            calls.append(call_dict)

        if req.include_feedback:
            feedback_query_req = make_feedback_query_req(req.project_id, calls)
            feedback = self.feedback_query(feedback_query_req)
            hydrate_calls_with_feedback(calls, feedback)

        return tsi.CallsQueryRes(calls=[tsi.CallSchema(**call) for call in calls])

    def _expand_refs(
        self, data: Dict[str, Any], expand_columns: list[str]
    ) -> Dict[str, Any]:
        """
        Recursively expand refs in the data. Only expand refs if requested in the
        expand_columns list. expand_columns must be sorted by depth, shallowest first.
        """
        cols = sorted(expand_columns, key=lambda x: x.count("."))
        for col in cols:
            val = data.get(col)
            if not val:
                val = get_nested_key(data, col)
                if not val:
                    continue

            if not ri.any_will_be_interpreted_as_ref_str(val):
                continue

            if not isinstance(ri.parse_internal_uri(val), ri.InternalObjectRef):
                continue

            derefed_val = self.refs_read_batch(tsi.RefsReadBatchReq(refs=[val])).vals[0]
            set_nested_key(data, col, derefed_val)

        return data

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return iter(self.calls_query(req).calls)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        calls = self.calls_query(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=req.filter,
                query=req.query,
            )
        ).calls
        return tsi.CallsQueryStatsRes(
            count=len(calls),
        )

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        assert_non_null_wb_user_id(req)
        # update row with a deleted_at field set to now
        conn, cursor = get_conn_cursor(self.db_path)
        with self.lock:
            recursive_query = """
                WITH RECURSIVE Descendants AS (
                    SELECT id
                    FROM calls
                    WHERE project_id = ? AND
                        deleted_at IS NULL AND
                        parent_id IN (SELECT id FROM calls WHERE id IN ({}))

                    UNION ALL

                    SELECT c.id
                    FROM calls c
                    JOIN Descendants d ON c.parent_id = d.id
                    WHERE c.deleted_at IS NULL
                )
                SELECT id FROM Descendants;
            """.format(", ".join("?" * len(req.call_ids)))

            params = [req.project_id] + req.call_ids
            cursor.execute(recursive_query, params)
            all_ids = [x[0] for x in cursor.fetchall()] + req.call_ids

            # set deleted_at for all children and parents
            delete_query = """
                UPDATE calls
                SET deleted_at = CURRENT_TIMESTAMP
                WHERE deleted_at is NULL AND
                    id IN ({})
            """.format(", ".join("?" * len(all_ids)))
            print("MUTATION", delete_query)
            cursor.execute(delete_query, all_ids)
            conn.commit()

        return tsi.CallsDeleteRes()

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        assert_non_null_wb_user_id(req)
        if req.display_name is None:
            raise ValueError("One of [display_name] is required for call update")

        conn, cursor = get_conn_cursor(self.db_path)
        with self.lock:
            cursor.execute(
                "UPDATE calls SET display_name = ? WHERE id = ?",
                (req.display_name, req.call_id),
            )
            conn.commit()
        return tsi.CallUpdateRes()

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

        # Validate
        object_id_validator(req.obj.object_id)

        req_obj = req.obj
        # TODO: version index isn't right here, what if we delete stuff?
        with self.lock:
            cursor.execute("BEGIN TRANSACTION")
            # Mark all existing objects with such id as not latest
            cursor.execute(
                """UPDATE objects SET is_latest = 0 WHERE project_id = ? AND object_id = ?""",
                (req_obj.project_id, req_obj.object_id),
            )
            # first get version count
            cursor.execute(
                """SELECT COUNT(*) FROM objects WHERE project_id = ? AND object_id = ?""",
                (req_obj.project_id, req_obj.object_id),
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
        conds = [f"object_id = '{req.object_id}'"]
        if req.digest == "latest":
            conds.append("is_latest = 1")
        else:
            (is_version, version_index) = digest_is_version_like(req.digest)
            if is_version:
                conds.append(f"version_index = '{version_index}'")
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
        parameters: Dict[str, Any] = {}
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    conds.append("kind = 'op'")
                else:
                    conds.append("kind != 'op'")
            if req.filter.object_ids:
                placeholders = ",".join(["?" for _ in req.filter.object_ids])
                conds.append(f"object_id IN ({placeholders})")
                parameters["object_ids"] = req.filter.object_ids
            if req.filter.latest_only:
                conds.append("is_latest = 1")
            if req.filter.base_object_classes:
                placeholders = ",".join(["?" for _ in req.filter.base_object_classes])
                conds.append(f"base_object_class IN ({placeholders})")
                parameters["base_object_classes"] = req.filter.base_object_classes

        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
            parameters=parameters,
            metadata_only=req.metadata_only,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
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

        return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        conn, cursor = get_conn_cursor(self.db_path)
        # conds = ["project_id = {project_id: String}"]

        cursor.execute(
            """
            SELECT
                tables.row_digests
            FROM
                tables
            WHERE
                tables.project_id = ? AND
                tables.digest = ?
            """,
            (req.project_id, req.base_digest),
        )
        query_result = cursor.fetchall()
        final_row_digests: list[str] = json.loads(query_result[0][0])
        new_rows_needed_to_insert = []
        known_digests = set(final_row_digests)

        def add_new_row_needed_to_insert(row_data: Any) -> str:
            if not isinstance(row_data, dict):
                raise ValueError("All rows must be dictionaries")
            row_json = json.dumps(row_data)
            row_digest = str_digest(row_json)
            if row_digest not in known_digests:
                new_rows_needed_to_insert.append((req.project_id, row_digest, row_json))
                known_digests.add(row_digest)
            return row_digest

        updated_digests = []
        for update in req.updates:
            if isinstance(update, tsi.TableAppendSpec):
                new_digest = add_new_row_needed_to_insert(update.append.row)
                final_row_digests.append(new_digest)
                updated_digests.append(new_digest)
            elif isinstance(update, tsi.TablePopSpec):
                if update.pop.index >= len(final_row_digests) or update.pop.index < 0:
                    raise ValueError("Index out of range")
                popped_digest = final_row_digests.pop(update.pop.index)
                updated_digests.append(popped_digest)
            elif isinstance(update, tsi.TableInsertSpec):
                if (
                    update.insert.index > len(final_row_digests)
                    or update.insert.index < 0
                ):
                    raise ValueError("Index out of range")
                new_digest = add_new_row_needed_to_insert(update.insert.row)
                final_row_digests.insert(update.insert.index, new_digest)
                updated_digests.append(new_digest)
            else:
                raise ValueError("Unrecognized update", update)

        # Perform the actual DB inserts
        with self.lock:
            cursor.executemany(
                "INSERT OR IGNORE INTO table_rows (project_id, digest, val) VALUES (?, ?, ?)",
                new_rows_needed_to_insert,
            )

            table_hasher = hashlib.sha256()
            for row_digest in final_row_digests:
                table_hasher.update(row_digest.encode())
            digest = table_hasher.hexdigest()

            cursor.execute(
                "INSERT OR IGNORE INTO tables (project_id, digest, row_digests) VALUES (?, ?, ?)",
                (req.project_id, digest, json.dumps(final_row_digests)),
            )
            conn.commit()

        return tsi.TableUpdateRes(digest=digest, updated_row_digests=updated_digests)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        conds = []
        parameters: list[str] = []
        if req.filter:
            if req.filter.row_digests:
                conds.append(
                    "tr.digest IN ({})".format(
                        ",".join("?" * len(req.filter.row_digests))
                    )
                )
                parameters.extend(req.filter.row_digests)
        else:
            conds.append("1 = 1")

        predicate = " AND ".join(conds)

        # Construct the ORDER BY clause
        order_by = ""
        if req.sort_by:
            sort_parts = []
            for sort in req.sort_by:
                field = sort.field
                direction = sort.direction.upper()
                if "." in field:
                    # Handle nested fields
                    parts = field.split(".")
                    field = f"json_extract(tr.val, '$.{'.'.join(parts)}')"
                else:
                    field = f"json_extract(tr.val, '$.{field}')"
                sort_parts.append(f"{field} {direction}")
            order_by = f"ORDER BY {', '.join(sort_parts)}"
        else:
            order_by = "ORDER BY OrderedDigests.original_order"
        # First get the row IDs by querying tables
        query = f"""
        WITH OrderedDigests AS (
            SELECT
                json_each.value AS digest,
                json_each.id AS original_order
            FROM
                tables,
                json_each(tables.row_digests)
            WHERE
                tables.project_id = ? AND
                tables.digest = ?
        )
        SELECT
            tr.digest,
            tr.val
        FROM
            OrderedDigests
            JOIN table_rows tr ON OrderedDigests.digest = tr.digest
        WHERE {predicate}
        {order_by}
        """

        if req.limit is not None:
            query += f" LIMIT {req.limit}"
        if req.offset is not None:
            if req.limit is None:
                query += " LIMIT -1"
            query += f" OFFSET {req.offset}"

        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute(query, [req.project_id, req.digest] + list(parameters))
        query_result = cursor.fetchall()

        return tsi.TableQueryRes(
            rows=[
                tsi.TableRowSchema(digest=r[0], val=json.loads(r[1]))
                for r in query_result
            ]
        )

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        parameters: list[Any] = [req.project_id, req.digest]

        query = """
        SELECT json_array_length(row_digests)
        FROM
            tables
        WHERE
            tables.project_id = ? AND
            tables.digest = ?
        """

        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute(query, parameters)
        row = cursor.fetchone()
        count = 0
        if row is not None:
            count = row[0]

        return tsi.TableQueryStatsRes(count=count)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # TODO: This reads one ref at a time, it should read them in batches
        # where it can. Like it should group by object that we need to read.
        # And it should also batch into table refs (like when we are reading a bunch
        # of rows from a single Dataset)
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        parsed_refs = [ri.parse_internal_uri(r) for r in req.refs]
        if any(isinstance(r, ri.InternalTableRef) for r in parsed_refs):
            raise ValueError("Table refs not supported")
        parsed_obj_refs = cast(list[ri.InternalObjectRef], parsed_refs)

        def read_ref(r: ri.InternalObjectRef) -> Any:
            conds = [
                f"object_id = '{r.name}'",
                f"digest = '{r.version}'",
            ]
            objs = self._select_objs_query(
                r.project_id,
                conditions=conds,
            )
            if len(objs) == 0:
                raise NotFoundError(f"Obj {r.name}:{r.version} not found")
            obj = objs[0]
            val = obj.val
            extra = r.extra
            for extra_index in range(0, len(extra), 2):
                op, arg = extra[extra_index], extra[extra_index + 1]
                if op == ri.DICT_KEY_EDGE_NAME:
                    val = val[arg]
                elif op == ri.OBJECT_ATTR_EDGE_NAME:
                    val = val[arg]
                elif op == ri.LIST_INDEX_EDGE_NAME:
                    val = val[int(arg)]
                elif op == ri.TABLE_ROW_ID_EDGE_NAME:
                    weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"
                    if isinstance(val, str) and val.startswith(weave_internal_prefix):
                        table_ref = ri.parse_internal_uri(val)
                        if not isinstance(table_ref, ri.InternalTableRef):
                            raise ValueError(
                                "invalid data layout encountered, expected TableRef when resolving id"
                            )
                        row = self._table_row_read(
                            project_id=table_ref.project_id,
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

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        assert_non_null_wb_user_id(req)
        validate_feedback_create_req(req)

        # Augment emoji with alias.
        res_payload = {}
        if req.feedback_type == "wandb.reaction.1":
            em = req.payload["emoji"]
            if emoji.emoji_count(em) != 1:
                raise InvalidRequest(
                    "Value of emoji key in payload must be exactly one emoji"
                )
            req.payload["alias"] = emoji.demojize(em)
            detoned = detone_emojis(em)
            req.payload["detoned"] = detoned
            req.payload["detoned_alias"] = emoji.demojize(detoned)
            res_payload = req.payload

        feedback_id = generate_id()
        created_at = datetime.datetime.now(ZoneInfo("UTC"))
        # TODO: Any validation on weave_ref?
        payload = json.dumps(req.payload)
        MAX_PAYLOAD = 1024
        if len(payload) > MAX_PAYLOAD:
            raise InvalidRequest("Feedback payload too large")
        row: Row = {
            "id": feedback_id,
            "project_id": req.project_id,
            "weave_ref": req.weave_ref,
            "wb_user_id": req.wb_user_id,
            "creator": req.creator,
            "feedback_type": req.feedback_type,
            "payload": req.payload,
            "created_at": created_at,
        }
        conn, cursor = get_conn_cursor(self.db_path)
        with self.lock:
            prepared = TABLE_FEEDBACK.insert(row).prepare(database_type="sqlite")
            cursor.executemany(prepared.sql, prepared.data)
            conn.commit()
        return tsi.FeedbackCreateRes(
            id=feedback_id,
            created_at=created_at,
            wb_user_id=req.wb_user_id,
            payload=res_payload,
        )

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        conn, cursor = get_conn_cursor(self.db_path)
        query = TABLE_FEEDBACK.select()
        query = query.project_id(req.project_id)
        query = query.fields(req.fields)
        query = query.where(req.query)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="sqlite")
        r = cursor.execute(prepared.sql, prepared.parameters)
        result = TABLE_FEEDBACK.tuples_to_rows(r.fetchall(), prepared.fields)
        return tsi.FeedbackQueryRes(result=result)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        # TODO: Instead of passing conditions to DELETE FROM,
        #       should we select matching ids, and then DELETE FROM WHERE id IN (...)?
        #       This would allow us to return the number of rows deleted, and complain
        #       if too many things would be deleted.
        validate_feedback_purge_req(req)
        conn, cursor = get_conn_cursor(self.db_path)
        query = TABLE_FEEDBACK.purge()
        query = query.project_id(req.project_id)
        query = query.where(req.query)
        prepared = query.prepare(database_type="sqlite")
        with self.lock:
            cursor.execute(prepared.sql, prepared.parameters)
            conn.commit()
        return tsi.FeedbackPurgeRes()

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

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        print("COST CREATE is not implemented for local sqlite", req)
        return tsi.CostCreateRes()

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        print("COST QUERY is not implemented for local sqlite", req)
        return tsi.CostQueryRes()

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        print("COST PURGE is not implemented for local sqlite", req)
        return tsi.CostPurgeRes()

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
        parameters: Optional[Dict[str, Any]] = None,
        metadata_only: Optional[bool] = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[list[tsi.SortBy]] = None,
    ) -> list[tsi.ObjSchema]:
        conn, cursor = get_conn_cursor(self.db_path)
        pred = " AND ".join(conditions or ["1 = 1"])
        val_dump_part = "'{}' as val_dump" if metadata_only else "val_dump"
        query = f"""
            SELECT
                project_id,
                object_id,
                created_at,
                kind,
                base_object_class,
                {val_dump_part},
                digest,
                version_index,
                is_latest
            FROM objects
            WHERE deleted_at IS NULL AND
                project_id = ? AND {pred}
        """

        if sort_by:
            valid_sort_fields = {"object_id", "created_at"}
            sort_clauses = []
            for sort in sort_by:
                if sort.field in valid_sort_fields and sort.direction in {
                    "asc",
                    "desc",
                }:
                    sort_clauses.append(f"{sort.field} {sort.direction.upper()}")
            if sort_clauses:
                query += f" ORDER BY {', '.join(sort_clauses)}"
        else:
            query += " ORDER BY created_at ASC"

        if limit is not None:
            query += f" LIMIT {limit}"
        if offset is not None:
            query += f" OFFSET {offset}"

        params = [project_id]
        if parameters:
            for param_list in parameters.values():
                params.extend(param_list)

        cursor.execute(query, params)
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


def _transform_external_calls_field_to_internal_calls_field(
    field: str,
    cast: Optional[str] = None,
) -> str:
    json_path = None
    if field == "inputs" or field.startswith("inputs."):
        if field == "inputs":
            json_path = "$"
        else:
            json_path = quote_json_path(field[len("inputs.") :])
        field = "inputs"
    elif field == "output" or field.startswith("output."):
        if field == "output":
            json_path = "$"
        else:
            json_path = quote_json_path(field[len("output.") :])
        field = "output"
    elif field == "attributes" or field.startswith("attributes."):
        if field == "attributes":
            json_path = "$"
        else:
            json_path = quote_json_path(field[len("attributes.") :])
        field = "attributes"
    elif field == "summary" or field.startswith("summary."):
        if field == "summary":
            json_path = "$"
        else:
            json_path = quote_json_path(field[len("summary.") :])
        field = "summary"

    if json_path is not None:
        sql_type = "TEXT"
        if cast is not None:
            if cast == "int":
                sql_type = "INT"
            elif cast == "float":
                sql_type = "FLOAT"
            elif cast == "bool":
                sql_type = "BOOL"
            elif cast == "str":
                sql_type = "TEXT"
            else:
                raise ValueError(f"Unknown cast: {cast}")
        field = (
            "CAST(json_extract("
            + json.dumps(field)
            + ", '"
            + json_path
            + "') AS "
            + sql_type
            + ")"
        )

    return field
