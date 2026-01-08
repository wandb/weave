# Sqlite Trace Server

import datetime
import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any, cast

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from weave.trace_server import constants, object_creation_utils
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    NotFoundError,
    ObjectDeletedError,
)
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    format_feedback_to_res,
    format_feedback_to_row,
    process_feedback_payload,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.ids import generate_id
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.feedback_types import RUNNABLE_FEEDBACK_TYPE_PREFIX
from weave.trace_server.methods.evaluation_status import evaluation_status
from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.orm import quote_json_path
from weave.trace_server.threads_query_builder import make_threads_query_sqlite
from weave.trace_server.trace_server_common import (
    assert_parameter_length_less_than_max,
    determine_call_status,
    digest_is_version_like,
    empty_str_to_none,
    get_nested_key,
    hydrate_calls_with_feedback,
    make_derived_summary_fields,
    make_feedback_query_req,
    op_name_matches,
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
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelArgs,
    EvaluateModelDispatcher,
)

_conn_cursor: ContextVar[tuple[sqlite3.Connection, sqlite3.Cursor] | None] = ContextVar(
    "conn_cursor", default=None
)


def get_conn_cursor(db_path: str) -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    # conn_cursor = _conn_cursor.get()
    conn_cursor = None
    if conn_cursor is None:
        # Use uri=True for URIs like "file::memory:?cache=shared"
        # This is required on Windows to properly handle URI paths
        is_uri = db_path.startswith("file:")
        conn = sqlite3.connect(db_path, uri=is_uri)
        # Create an array reverse function.
        conn.create_function("reverse", 1, lambda x: x[::-1])
        cursor = conn.cursor()
        conn_cursor = (conn, cursor)
        _conn_cursor.set(conn_cursor)
    return conn_cursor


class SqliteTraceServer(tsi.FullTraceServerInterface):
    def __init__(
        self,
        db_path: str,
        evaluate_model_dispatcher: EvaluateModelDispatcher | None = None,
    ):
        self.lock = threading.Lock()
        self.db_path = db_path
        self._evaluate_model_dispatcher = evaluate_model_dispatcher

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
                thread_id TEXT,
                turn_id TEXT,
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
                wb_run_step INTEGER,
                wb_run_step_end INTEGER,
                deleted_at TEXT,
                display_name TEXT,
                otel_dump TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                project_id TEXT,
                object_id TEXT,
                wb_user_id TEXT,
                created_at TEXT,
                kind TEXT,
                base_object_class TEXT,
                leaf_object_class TEXT,
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

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        res = []
        for item in req.batch:
            if item.mode == "start":
                res.append(self.call_start(item.req))
            elif item.mode == "end":
                res.append(self.call_end(item.req))
            else:
                raise ValueError("Invalid mode")
        return tsi.CallCreateBatchRes(res=res)

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
            otel_dump_str = None
            if hasattr(req.start, "otel_dump") and req.start.otel_dump is not None:
                otel_dump_str = json.dumps(req.start.otel_dump)

            cursor.execute(
                """INSERT INTO calls (
                    project_id,
                    id,
                    trace_id,
                    parent_id,
                    thread_id,
                    turn_id,
                    op_name,
                    display_name,
                    started_at,
                    attributes,
                    inputs,
                    input_refs,
                    wb_user_id,
                    wb_run_id,
                    wb_run_step,
                    otel_dump
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req.start.project_id,
                    req.start.id,
                    req.start.trace_id,
                    req.start.parent_id,
                    req.start.thread_id,
                    req.start.turn_id,
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
                    req.start.wb_run_step,
                    otel_dump_str,
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
                    summary = ?,
                    wb_run_step_end = ?
                WHERE id = ?""",
                (
                    req.end.ended_at.isoformat(),
                    req.end.exception,
                    json.dumps(req.end.output),
                    json.dumps(
                        extract_refs_from_values(list(parsable_output.values()))
                    ),
                    json.dumps(req.end.summary),
                    req.end.wb_run_step_end,
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
        conn, cursor = get_conn_cursor(self.db_path)
        conds = []
        filter = req.filter
        if filter:
            if filter.op_names:
                assert_parameter_length_less_than_max("op_names", len(filter.op_names))
                or_conditions: list[str] = []

                non_wildcarded_names: list[str] = []
                wildcarded_names: list[str] = []
                for name in filter.op_names:
                    if name.endswith(WILDCARD_ARTIFACT_VERSION_AND_PATH):
                        wildcarded_names.append(name)
                    else:
                        non_wildcarded_names.append(name)

                if non_wildcarded_names:
                    in_expr = ", ".join(f"'{x}'" for x in non_wildcarded_names)
                    or_conditions += [f"op_name IN ({', '.join({in_expr})})"]

                for _name_ndx, name in enumerate(wildcarded_names):
                    like_name = name[: -len(WILDCARD_ARTIFACT_VERSION_AND_PATH)] + "%"
                    or_conditions.append(f"op_name LIKE '{like_name}'")

                if or_conditions:
                    conds.append("(" + " OR ".join(or_conditions) + ")")

            if filter.input_refs:
                assert_parameter_length_less_than_max(
                    "input_refs", len(filter.input_refs)
                )
                or_conditions = []
                for ref in filter.input_refs:
                    or_conditions.append(f"input_refs LIKE '%{ref}%'")
                conds.append("(" + " OR ".join(or_conditions) + ")")
            if filter.output_refs:
                assert_parameter_length_less_than_max(
                    "output_refs", len(filter.output_refs)
                )
                or_conditions = []
                for ref in filter.output_refs:
                    or_conditions.append(f"output_refs LIKE '%{ref}%'")
                conds.append("(" + " OR ".join(or_conditions) + ")")
            if filter.parent_ids:
                assert_parameter_length_less_than_max(
                    "parent_ids", len(filter.parent_ids)
                )
                in_expr = ", ".join(f"'{x}'" for x in filter.parent_ids)
                conds += [f"parent_id IN ({in_expr})"]
            if filter.trace_ids:
                assert_parameter_length_less_than_max(
                    "trace_ids", len(filter.trace_ids)
                )
                in_expr = ", ".join(f"'{x}'" for x in filter.trace_ids)
                conds += [f"trace_id IN ({in_expr})"]
            if filter.call_ids:
                assert_parameter_length_less_than_max("call_ids", len(filter.call_ids))
                in_expr = ", ".join(f"'{x}'" for x in filter.call_ids)
                conds += [f"id IN ({in_expr})"]
            if filter.trace_roots_only:
                conds.append("parent_id IS NULL")
            if filter.wb_run_ids:
                in_expr = ", ".join(f"'{x}'" for x in filter.wb_run_ids)
                conds += [f"wb_run_id IN ({in_expr})"]
            if filter.wb_user_ids:
                in_expr = ", ".join(f"'{x}'" for x in filter.wb_user_ids)
                conds += [f"wb_user_id IN ({in_expr})"]

        if req.query:
            # This is the mongo-style query
            def process_operation(operation: tsi_query.Operation) -> str:
                cond = None

                if isinstance(operation, tsi_query.AndOperation):
                    if len(operation.and_) == 0:
                        raise ValueError("Empty AND operation")
                    elif len(operation.and_) == 1:
                        return process_operand(operation.and_[0])
                    parts = [process_operand(op) for op in operation.and_]
                    cond = f"({' AND '.join(parts)})"
                elif isinstance(operation, tsi_query.OrOperation):
                    if len(operation.or_) == 0:
                        raise ValueError("Empty OR operation")
                    elif len(operation.or_) == 1:
                        return process_operand(operation.or_[0])
                    parts = [process_operand(op) for op in operation.or_]
                    cond = f"({' OR '.join(parts)})"
                elif isinstance(operation, tsi_query.NotOperation):
                    operand_part = process_operand(operation.not_[0])
                    cond = f"(NOT ({operand_part}))"
                elif isinstance(operation, tsi_query.EqOperation):
                    lhs_part = process_operand(operation.eq_[0])
                    if (
                        isinstance(operation.eq_[1], tsi_query.LiteralOperation)
                        and operation.eq_[1].literal_ is None
                    ):
                        cond = f"({lhs_part} IS NULL)"
                    else:
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
                    raise TypeError(f"Unknown operation type: {operation}")

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
                    raise TypeError(f"Unknown operand type: {operand}")

            filter_cond = process_operation(req.query.expr_)

            conds.append(filter_cond)

        required_columns = ["id", "trace_id", "project_id", "op_name", "started_at"]
        select_columns = [
            key
            for key in tsi.CallSchema.model_fields.keys()
            if key not in ["storage_size_bytes", "total_storage_size_bytes"]
        ]
        if req.columns:
            # TODO(gst): allow json fields to be selected
            simple_columns = list({x.split(".")[0] for x in req.columns})
            if "summary" in simple_columns or req.include_costs:
                simple_columns += ["ended_at", "exception", "display_name"]

            select_columns = [x for x in simple_columns if x in select_columns]
            # add required columns, preserving requested column order
            select_columns += [
                rcol for rcol in required_columns if rcol not in select_columns
            ]

        select_columns_names = [*select_columns]

        # Always select otel_dump for backwards compatibility (injected into attributes)
        select_columns.append("otel_dump")
        select_columns_names.append("otel_dump")

        if req.include_storage_size:
            select_columns.append(
                "(COALESCE(length(attributes),0) + COALESCE(length(inputs),0) + COALESCE(length(output),0) + COALESCE(length(summary),0))"
            )
            select_columns_names.append("storage_size_bytes")

        join_clause = ""
        if req.include_total_storage_size:
            select_columns.append(
                """
                CASE
                    WHEN calls.parent_id IS NULL THEN trace_stats.total_storage_size_bytes
                    ELSE NULL
                END
            """
            )
            select_columns_names.append("total_storage_size_bytes")

            join_clause += """
                LEFT JOIN (SELECT
                    calls.trace_id as tid,
                    sum(COALESCE(length(attributes),0) + COALESCE(length(inputs),0) + COALESCE(length(output),0) + COALESCE(length(summary),0)) as total_storage_size_bytes
                FROM calls
                GROUP BY calls.trace_id) as trace_stats ON trace_stats.tid=calls.trace_id
            """

        query = f"SELECT {', '.join(select_columns)} FROM calls {join_clause} WHERE deleted_at IS NULL AND project_id = '{req.project_id}'"

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
                json_path: str | None = None
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
                    field = "attributes" + field[len("attributes") :]
                    if field.startswith("attributes."):
                        json_path = field[len("attributes.") :]
                        field = "attributes"
                elif field.startswith("summary"):
                    # Handle special summary fields that are calculated rather than stored directly
                    if field == "summary.weave.status":
                        # Create a CASE expression to properly determine the status
                        field = """
                            CASE
                                WHEN exception IS NOT NULL THEN 'error'
                                WHEN ended_at IS NULL THEN 'running'
                                WHEN json_extract(summary, '$.status_counts.error') > 0 THEN 'descendant_error'
                                ELSE 'success'
                            END
                        """
                        json_path = None
                    elif field == "summary.weave.latency_ms":
                        # Calculate latency directly using julianday for millisecond precision
                        field = """
                            CASE
                                WHEN ended_at IS NOT NULL THEN
                                    CAST((julianday(ended_at) - julianday(started_at)) * 86400000 AS FLOAT)
                                ELSE 0
                            END
                        """
                        json_path = None
                    elif field == "summary.weave.trace_name":
                        # Handle trace_name field similar to the ClickHouse implementation
                        # If display_name is present, use that
                        # Otherwise, check if op_name is an object reference and extract the name
                        # If not, just use op_name directly
                        field = """
                            CASE
                                WHEN display_name IS NOT NULL AND display_name != '' THEN display_name
                                WHEN op_name IS NOT NULL AND op_name LIKE 'weave-trace-internal:///%' THEN
                                    SUBSTR(
                                        op_name,
                                        LENGTH(op_name) - INSTR(REVERSE(op_name), '/') + 2,
                                        INSTR(SUBSTR(op_name, LENGTH(op_name) - INSTR(REVERSE(op_name), '/') + 2), ':') - 1
                                    )
                                ELSE op_name
                            END
                        """
                        json_path = None
                    else:
                        field = "summary" + field[len("summary") :]
                        if field.startswith("summary."):
                            json_path = field[len("summary.") :]
                            field = "summary"

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

        cursor.execute(query)

        query_result = cursor.fetchall()
        calls = []
        for row in query_result:
            call_dict = dict(zip(select_columns_names, row, strict=False))
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

            # For backwards/future compatibility: inject otel_dump into attributes if present
            # Legacy trace servers stored all otel info in attributes, clients expect it
            if call_dict.get("otel_dump"):
                otel_data = json.loads(call_dict["otel_dump"])
                if "attributes" not in call_dict:
                    call_dict["attributes"] = {}
                call_dict["attributes"]["otel_span"] = otel_data

            # Remove otel_dump from the result as it's not in CallSchema
            call_dict.pop("otel_dump", None)

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
        self, data: dict[str, Any], expand_columns: list[str]
    ) -> dict[str, Any]:
        """Recursively expand refs in the data. Only expand refs if requested in the
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
            ref_col = f"{col}._ref"
            set_nested_key(data, ref_col, val)

        return data

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return iter(self.calls_query(req).calls)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        if req.limit is not None and req.limit < 1:
            raise ValueError("Limit must be a positive integer")
        calls = self.calls_query(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=req.filter,
                query=req.query,
                limit=req.limit,
                include_total_storage_size=req.include_total_storage_size,
            )
        ).calls
        return tsi.CallsQueryStatsRes(
            count=len(calls),
            total_storage_size_bytes=sum(
                call.total_storage_size_bytes
                for call in calls
                if call.total_storage_size_bytes is not None
            ),
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

        return tsi.CallsDeleteRes(num_deleted=len(all_ids))

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

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        conn, cursor = get_conn_cursor(self.db_path)

        processed_result = process_incoming_object_val(
            req.obj.val, req.obj.builtin_object_class
        )
        processed_val = processed_result["val"]
        json_val = json.dumps(processed_val)
        digest = str_digest(json_val)
        project_id, object_id, wb_user_id = (
            req.obj.project_id,
            req.obj.object_id,
            req.obj.wb_user_id,
        )

        # Validate
        object_id_validator(object_id)

        with self.lock:
            if self._obj_exists(cursor, project_id, object_id, digest):
                return tsi.ObjCreateRes(digest=digest, object_id=object_id)

            # Use IMMEDIATE transaction to acquire write lock immediately, preventing
            # race conditions where concurrent transactions read stale version_index values
            cursor.execute("BEGIN IMMEDIATE TRANSACTION")
            self._mark_existing_objects_as_not_latest(cursor, project_id, object_id)
            version_index = self._get_obj_version_index(cursor, project_id, object_id)
            cursor.execute(
                """INSERT OR IGNORE INTO objects (
                    project_id,
                    object_id,
                    created_at,
                    kind,
                    base_object_class,
                    leaf_object_class,
                    refs,
                    val_dump,
                    digest,
                    version_index,
                    is_latest,
                    deleted_at,
                    wb_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, kind, object_id, digest) DO UPDATE SET
                    created_at = excluded.created_at,
                    kind = excluded.kind,
                    base_object_class = excluded.base_object_class,
                    leaf_object_class = excluded.leaf_object_class,
                    refs = excluded.refs,
                    val_dump = excluded.val_dump,
                    version_index = excluded.version_index,
                    is_latest = excluded.is_latest,
                    deleted_at = excluded.deleted_at
                """,
                (
                    project_id,
                    object_id,
                    datetime.datetime.now().isoformat(),
                    get_kind(processed_val),
                    processed_result["base_object_class"],
                    processed_result["leaf_object_class"],
                    json.dumps([]),
                    json_val,
                    digest,
                    version_index,
                    1,
                    None,
                    wb_user_id,
                ),
            )
            conn.commit()
        return tsi.ObjCreateRes(digest=digest, object_id=object_id)

    def _obj_exists(
        self, cursor: sqlite3.Cursor, project_id: str, object_id: str, digest: str
    ) -> bool:
        cursor.execute(
            "SELECT COUNT(*) FROM objects WHERE project_id = ? AND object_id = ? AND digest = ? AND deleted_at IS NULL",
            (project_id, object_id, digest),
        )
        return_row = cursor.fetchone()
        if return_row is None:
            return False
        return return_row[0] > 0

    def _mark_existing_objects_as_not_latest(
        self, cursor: sqlite3.Cursor, project_id: str, object_id: str
    ) -> None:
        """Mark all existing objects with such id as not latest.
        We are creating a new object with the same id, all existing ones are no longer latest.
        """
        cursor.execute(
            "UPDATE objects SET is_latest = 0 WHERE project_id = ? AND object_id = ?",
            (project_id, object_id),
        )

    def _get_obj_version_index(
        self, cursor: sqlite3.Cursor, project_id: str, object_id: str
    ) -> int:
        """Get the version index for a new object with such id."""
        cursor.execute(
            "SELECT COUNT(*) FROM objects WHERE project_id = ? AND object_id = ?",
            (project_id, object_id),
        )
        return_row = cursor.fetchone()
        if return_row is None:
            return 0
        return return_row[0]

    @staticmethod
    def _make_digest_condition(digest: str) -> str:
        if digest == "latest":
            return "is_latest = 1"
        else:
            (is_version, version_index) = digest_is_version_like(digest)
            if is_version:
                return f"version_index = '{version_index}'"
            else:
                return f"digest = '{digest}'"

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        conds = [f"object_id = '{req.object_id}'"]
        digest_condition = self._make_digest_condition(req.digest)
        conds.append(digest_condition)
        objs = self._select_objs_query(
            req.project_id,
            conditions=conds,
            include_deleted=True,
            metadata_only=req.metadata_only,
        )
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")
        if objs[0].deleted_at is not None:
            raise ObjectDeletedError(
                f"{req.object_id}:v{objs[0].version_index} was deleted at {objs[0].deleted_at}",
                deleted_at=objs[0].deleted_at,
            )
        return tsi.ObjReadRes(obj=objs[0])

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        conds: list[str] = []
        parameters: dict[str, Any] = {}
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
            if req.filter.exclude_base_object_classes:
                placeholders = ",".join(
                    ["?" for _ in req.filter.exclude_base_object_classes]
                )
                conds.append(f"base_object_class NOT IN ({placeholders})")
                parameters["exclude_base_object_classes"] = (
                    req.filter.exclude_base_object_classes
                )
            if req.filter.leaf_object_classes:
                placeholders = ",".join(["?" for _ in req.filter.leaf_object_classes])
                conds.append(f"leaf_object_class IN ({placeholders})")
                parameters["leaf_object_classes"] = req.filter.leaf_object_classes

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

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        max_objects_to_delete = 100
        if req.digests and len(req.digests) > max_objects_to_delete:
            raise ValueError(
                f"Object delete request contains {len(req.digests)} objects. Please delete {max_objects_to_delete} or fewer objects at a time."
            )

        # First, select the objects that match the query
        select_query = """
            SELECT digest FROM objects
            WHERE project_id = ? AND
                object_id = ? AND
                deleted_at IS NULL
        """
        parameters = [req.project_id, req.object_id]
        if req.digests:
            digest_conditions = [
                self._make_digest_condition(digest) for digest in req.digests
            ]
            digest_conditions_str = " OR ".join(digest_conditions)
            select_query += f"AND ({digest_conditions_str})"

        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute(select_query, parameters)
        matching_objects = cursor.fetchall()

        if len(matching_objects) == 0:
            raise NotFoundError(
                f"Object {req.object_id} ({req.digests}) not found when deleting."
            )
        found_digests = {obj[0] for obj in matching_objects}
        if req.digests:
            given_digests = set(req.digests)
            if len(given_digests) != len(found_digests):
                raise NotFoundError(
                    f"Delete request contains {len(req.digests)} digests, but found {len(found_digests)} objects to delete. Diff digests: {given_digests - found_digests}"
                )

        # Create a delete query that will set the deleted_at field to now
        delete_query = """
            UPDATE objects SET deleted_at = CURRENT_TIMESTAMP
            WHERE project_id = ? AND
                object_id = ? AND
                digest IN ({})
        """.format(", ".join("?" * len(found_digests)))
        delete_parameters = [req.project_id, req.object_id] + list(found_digests)

        with self.lock:
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute(delete_query, delete_parameters)
            conn.commit()

        return tsi.ObjDeleteRes(num_deleted=len(matching_objects))

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        conn, cursor = get_conn_cursor(self.db_path)
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise TypeError("All rows must be dictionaries")
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

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table by specifying row digests, instead actual rows."""
        conn, cursor = get_conn_cursor(self.db_path)

        # Calculate table digest from row digests
        table_hasher = hashlib.sha256()
        for row_digest in req.row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        with self.lock:
            cursor.execute(
                "INSERT OR IGNORE INTO tables (project_id, digest, row_digests) VALUES (?, ?, ?)",
                (req.project_id, digest, json.dumps(req.row_digests)),
            )
            conn.commit()

        return tsi.TableCreateFromDigestsRes(digest=digest)

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
                raise TypeError("All rows must be dictionaries")
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
                raise TypeError("Unrecognized update", update)

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

                # Validate sort field to prevent empty JSON paths
                if not field or not field.strip():
                    raise InvalidRequest("Sort field cannot be empty")

                # Check for invalid dot patterns that would create malformed JSON paths
                if field.startswith(".") or field.endswith(".") or ".." in field:
                    raise InvalidRequest(
                        f"Invalid sort field '{field}': field names cannot start/end with dots or contain consecutive dots"
                    )

                if "." in field:
                    # Handle nested fields
                    parts = field.split(".")
                    # Additional validation: ensure no empty path components
                    if any(not component.strip() for component in parts):
                        raise InvalidRequest(
                            f"Invalid sort field '{field}': field path components cannot be empty"
                        )
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
                CAST(json_each.key AS INTEGER) AS original_order
            FROM
                tables,
                json_each(tables.row_digests)
            WHERE
                tables.project_id = ? AND
                tables.digest = ?
        )
        SELECT
            tr.digest,
            tr.val,
            OrderedDigests.original_order
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
                tsi.TableRowSchema(
                    digest=r[0],
                    val=json.loads(r[1]),
                    original_index=r[2],  # Add the original index
                )
                for r in query_result
            ]
        )

    # This is a legacy endpoint, it should be removed once the client is mostly updated
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        batch_req = tsi.TableQueryStatsBatchReq(
            project_id=req.project_id, digests=[req.digest]
        )

        res = self.table_query_stats_batch(batch_req)

        if len(res.tables) != 1:
            raise RuntimeError("Unexpected number of results", res)

        count = res.tables[0].count
        return tsi.TableQueryStatsRes(count=count)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        parameters: list[Any] = [req.project_id] + list(req.digests or [])

        placeholders = ",".join(["?" for _ in (req.digests or [])])

        query = f"""
        SELECT digest, json_array_length(row_digests)
        FROM
            tables
        WHERE
            tables.project_id = ? AND
            tables.digest in ({placeholders})
        """

        conn, cursor = get_conn_cursor(self.db_path)
        cursor.execute(query, parameters)

        query_result = cursor.fetchall()

        tables = []

        for row in query_result:
            count = row[1]
            digest = row[0]
            tables.append(tsi.TableStatsRow(count=count, digest=digest))

        return tsi.TableQueryStatsBatchRes(tables=tables)

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
        if any(isinstance(r, ri.InternalCallRef) for r in parsed_refs):
            raise ValueError("Call refs not supported")
        parsed_obj_refs = cast(list[ri.InternalObjectRef], parsed_refs)

        def read_ref(r: ri.InternalObjectRef) -> Any:
            conds = [
                f"object_id = '{r.name}'",
                f"digest = '{r.version}'",
            ]
            objs = self._select_objs_query(
                r.project_id,
                conditions=conds,
                include_deleted=True,
            )
            if len(objs) == 0:
                raise NotFoundError(f"Obj {r.name}:{r.version} not found")
            obj = objs[0]
            if obj.deleted_at is not None:
                return None
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
        validate_feedback_create_req(req, self)

        processed_payload = process_feedback_payload(req)
        row = format_feedback_to_row(req, processed_payload)
        conn, cursor = get_conn_cursor(self.db_path)
        with self.lock:
            prepared = TABLE_FEEDBACK.insert(row).prepare(database_type="sqlite")
            cursor.executemany(prepared.sql, prepared.data)
            conn.commit()

        return format_feedback_to_res(row)

    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        """Create multiple feedback items in a batch efficiently."""
        rows_to_insert = []
        results = []

        for feedback_req in req.batch:
            assert_non_null_wb_user_id(feedback_req)
            validate_feedback_create_req(feedback_req, self)

            processed_payload = process_feedback_payload(feedback_req)
            row = format_feedback_to_row(feedback_req, processed_payload)
            rows_to_insert.append(row)
            results.append(format_feedback_to_res(row))

        # Batch insert all rows at once
        if rows_to_insert:
            conn, cursor = get_conn_cursor(self.db_path)
            with self.lock:
                # Insert each row individually but in a single transaction
                for row in rows_to_insert:
                    prepared = TABLE_FEEDBACK.insert(row).prepare(
                        database_type="sqlite"
                    )
                    cursor.executemany(prepared.sql, prepared.data)
                conn.commit()

        return tsi.FeedbackCreateBatchRes(res=results)

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

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        purge_request = tsi.FeedbackPurgeReq(
            project_id=req.project_id,
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "id"},
                        {"$literal": req.feedback_id},
                    ],
                }
            },
        )
        self.feedback_purge(purge_request)
        create_req = tsi.FeedbackCreateReq(**req.model_dump(exclude={"feedback_id"}))
        create_result = self.feedback_create(create_req)

        return tsi.FeedbackReplaceRes(
            id=create_result.id,
            created_at=create_result.created_at,
            wb_user_id=create_result.wb_user_id,
            payload=create_result.payload,
        )

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        raise NotImplementedError(
            "actions_execute_batch is not implemented for SQLite trace server"
        )

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

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        print("files_stats is not implemented for SQLite trace server", req)
        return tsi.FilesStatsRes(total_size_bytes=-1)

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        print("COST CREATE is not implemented for local sqlite", req)
        return tsi.CostCreateRes()

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        print("COST QUERY is not implemented for local sqlite", req)
        return tsi.CostQueryRes()

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        print("COST PURGE is not implemented for local sqlite", req)
        return tsi.CostPurgeRes()

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        # TODO: This is not implemented for the sqlite trace server
        # Currently, this will only be called from the weave file, so we return an empty dict for now
        return tsi.CompletionsCreateRes(response={})

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        # TODO: This is not implemented for the sqlite trace server
        # Fall back to non-streaming completion
        response = self.completions_create(req)
        yield {"response": response.response, "weave_call_id": response.weave_call_id}

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        # TODO: This is not implemented for the sqlite trace server
        # Currently, this will only be called from the weave file, so we return an empty dict for now
        return tsi.ImageGenerationCreateRes(response={})

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        if not isinstance(req.traces, ExportTraceServiceRequest):
            raise TypeError(
                "Expected traces as ExportTraceServiceRequest, got {type(req.traces)}"
            )

        calls: list[dict[str, object]] = []
        rejected_spans = 0
        error_messages: list[str] = []
        for proto_resource_spans in req.traces.resource_spans:
            resource = Resource.from_proto(proto_resource_spans.resource)
            for proto_scope_spans in proto_resource_spans.scope_spans:
                for proto_span in proto_scope_spans.spans:
                    try:
                        span = Span.from_proto(proto_span, resource)
                        start_call, end_call = span.to_call(req.project_id)
                        calls.extend(
                            [
                                {
                                    "mode": "start",
                                    "req": tsi.CallStartReq(start=start_call),
                                },
                                {"mode": "end", "req": tsi.CallEndReq(end=end_call)},
                            ]
                        )
                    except AttributePathConflictError as e:
                        rejected_spans += 1
                        try:
                            trace_id = proto_span.trace_id.hex()
                            span_id = proto_span.span_id.hex()
                            name = getattr(proto_span, "name", "")
                        except Exception:
                            trace_id = ""
                            span_id = ""
                            name = ""
                        span_ident = (
                            f"name='{name}' trace_id='{trace_id}' span_id='{span_id}'"
                        )
                        error_messages.append(f"Rejected span ({span_ident}): {e!s}")
        res = self.call_start_batch(tsi.CallCreateBatchReq(batch=calls))
        # Return spec-compliant response; include partial_success if needed
        if rejected_spans > 0:
            return tsi.OtelExportRes(
                partial_success=tsi.ExportTracePartialSuccess(
                    rejected_spans=rejected_spans,
                    error_message=(
                        "; ".join(error_messages[:20])
                        + ("; ..." if len(error_messages) > 20 else "")
                    ),
                )
            )
        return tsi.OtelExportRes()

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        raise NotImplementedError(
            "project_stats is not implemented for SQLite trace server"
        )

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Stream threads with aggregated statistics sorted by last activity."""
        conn, cursor = get_conn_cursor(self.db_path)

        # Extract filter values
        after_datetime = None
        before_datetime = None
        thread_ids = None
        if req.filter is not None:
            after_datetime = req.filter.after_datetime
            before_datetime = req.filter.before_datetime
            thread_ids = req.filter.thread_ids

        # Use the dedicated query builder
        query, parameters = make_threads_query_sqlite(
            project_id=req.project_id,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
            sortable_datetime_after=after_datetime,
            sortable_datetime_before=before_datetime,
            thread_ids=thread_ids,
        )

        cursor.execute(query, parameters)
        query_result = cursor.fetchall()

        # Use iter() as requested for SQLite implementation
        for row in iter(query_result):
            (
                thread_id,
                turn_count,
                start_time_str,
                last_updated_str,
                first_turn_id,
                last_turn_id,
                p50_turn_duration_ms,
                p99_turn_duration_ms,
            ) = row

            # Parse the datetime strings if present
            if start_time_str and last_updated_str:
                try:
                    # SQLite stores datetime as string, parse it
                    start_time = datetime.datetime.fromisoformat(
                        start_time_str.replace("Z", "+00:00")
                    )
                    last_updated = datetime.datetime.fromisoformat(
                        last_updated_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    # Skip threads without valid timestamps
                    continue
            else:
                # Skip threads without valid timestamps
                continue

            yield tsi.ThreadSchema(
                thread_id=thread_id,
                turn_count=turn_count,
                start_time=start_time,
                last_updated=last_updated,
                first_turn_id=first_turn_id,
                last_turn_id=last_turn_id,
                p50_turn_duration_ms=p50_turn_duration_ms,
                p99_turn_duration_ms=p99_turn_duration_ms,
            )

    # Annotation Queue API - Stub implementations (not supported in SQLite)
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        """Annotation queues not supported in SQLite."""
        raise NotImplementedError("Annotation queues are not supported in SQLite")

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        """Annotation queues not supported in SQLite."""
        raise NotImplementedError("Annotation queues are not supported in SQLite")

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        """Annotation queues not supported in SQLite."""
        raise NotImplementedError("Annotation queues are not supported in SQLite")

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Annotation queues not supported in SQLite."""
        raise NotImplementedError("Annotation queues are not supported in SQLite")

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        """Annotation queues not supported in SQLite."""
        raise NotImplementedError("Annotation queues are not supported in SQLite")

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        """Annotation queues not supported in SQLite."""
        raise NotImplementedError("Annotation queues are not supported in SQLite")

    def evaluate_model(self, req: tsi.EvaluateModelReq) -> tsi.EvaluateModelRes:
        if self._evaluate_model_dispatcher is None:
            raise ValueError("Evaluate model dispatcher is not set")
        if req.wb_user_id is None:
            raise ValueError("wb_user_id is required")
        call_id = generate_id()
        self._evaluate_model_dispatcher.dispatch(
            EvaluateModelArgs(
                project_id=req.project_id,
                evaluation_ref=req.evaluation_ref,
                model_ref=req.model_ref,
                wb_user_id=req.wb_user_id,
                evaluation_call_id=call_id,
            )
        )
        return tsi.EvaluateModelRes(call_id=call_id)

    def evaluation_status(
        self, req: tsi.EvaluationStatusReq
    ) -> tsi.EvaluationStatusRes:
        return evaluation_status(self, req)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create an op object by delegating to obj_create.

        Args:
            req: OpCreateReq containing project_id, name, description, and source_code

        Returns:
            OpCreateRes with digest, object_id, version_index, and op_ref
        """
        # Store source code as a file (use placeholder if not provided)
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        # Build the op object value structure with the file digest
        # Note: We store just the digest string, matching SDK's to_json output
        op_val = object_creation_utils.build_op_val(source_file_res.digest)
        object_id = object_creation_utils.make_object_id(req.name, "Op")

        # Create the object
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=op_val,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        return tsi.OpCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Get a specific op object by delegating to obj_read with op filtering.

        Returns the actual source code of the op.
        """
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
            metadata_only=False,  # We need the full val to extract file references
        )
        result = self.obj_read(obj_req)

        # Extract code from the file storage
        val = result.obj.val
        code = ""

        # Check if this is a file-based op
        if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
            files = val.get("files", {})
            if object_creation_utils.OP_SOURCE_FILE_NAME in files:
                # Files dict maps filename to digest string
                file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]

                # Load the actual source code
                try:
                    file_content_res = self.file_content_read(
                        tsi.FileContentReadReq(
                            project_id=req.project_id, digest=file_digest
                        )
                    )
                    code = file_content_res.content.decode("utf-8")
                except Exception:
                    # If we can't read the file, leave code empty
                    pass

        return tsi.OpReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            code=code,
        )

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        """List op objects by delegating to objs_query with op filtering."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                is_op=True,
                latest_only=True,
            ),
            limit=req.limit,
            offset=req.offset,
            metadata_only=False,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            code = ""

            # Extract file reference from the val if it's a file-based op
            try:
                val = obj.val
                if isinstance(val, dict) and val.get("_type") == "CustomWeaveType":
                    files = val.get("files", {})
                    if object_creation_utils.OP_SOURCE_FILE_NAME in files:
                        file_digest = files[object_creation_utils.OP_SOURCE_FILE_NAME]

                        # Load the actual source code
                        try:
                            file_content_res = self.file_content_read(
                                tsi.FileContentReadReq(
                                    project_id=req.project_id, digest=file_digest
                                )
                            )
                            code = file_content_res.content.decode("utf-8")
                        except Exception:
                            # If we can't read the file, leave code empty
                            pass
            except Exception:
                pass  # If parsing fails, leave code empty

            yield tsi.OpReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                code=code,
            )

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        """Delete op objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.OpDeleteRes(num_deleted=result.num_deleted)

    def dataset_create(self, req: tsi.DatasetCreateReq) -> tsi.DatasetCreateRes:
        """Create a dataset object by first creating a table for rows, then creating the dataset object.

        The dataset object references the table containing the actual row data.
        """
        # Create a safe ID for the dataset
        dataset_id = object_creation_utils.make_object_id(req.name, "Dataset")

        # Create a table and get its ref
        table_req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=req.project_id,
                rows=req.rows,
            )
        )
        table_res = self.table_create(table_req)
        table_ref = ri.InternalTableRef(
            project_id=req.project_id,
            digest=table_res.digest,
        ).uri()

        # Create the dataset object
        dataset_val = object_creation_utils.build_dataset_val(
            name=req.name,
            description=req.description,
            table_ref=table_ref,
        )
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=dataset_id,
                val=dataset_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query the object back to get its version index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=dataset_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        return tsi.DatasetCreateRes(
            digest=obj_result.digest,
            object_id=dataset_id,
            version_index=obj_read_res.obj.version_index,
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        """Get a dataset object by delegating to obj_read.

        Returns the rows reference as a string.
        """
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        # Extract name, description, and rows ref from val data
        name = val.get("name")
        description = val.get("description")
        rows_ref = val.get("rows", "")

        # Create the response with all required fields
        return tsi.DatasetReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            rows=rows_ref,
        )

    def dataset_list(self, req: tsi.DatasetListReq) -> Iterator[tsi.DatasetReadRes]:
        """List dataset objects by delegating to objs_query with Dataset filtering.

        Returns the rows reference as a string.
        """
        # Query the objects
        dataset_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Dataset"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=dataset_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        # Yield back a descriptive metadata object for each dataset
        for obj in obj_res.objs:
            if not hasattr(obj, "val") or not obj.val:
                continue

            val = obj.val
            if not isinstance(val, dict):
                continue

            name = val.get("name")
            description = val.get("description")
            rows_ref = val.get("rows", "")

            yield tsi.DatasetReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                rows=rows_ref,
            )

    def dataset_delete(self, req: tsi.DatasetDeleteReq) -> tsi.DatasetDeleteRes:
        """Delete dataset objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.DatasetDeleteRes(num_deleted=result.num_deleted)

    def scorer_create(self, req: tsi.ScorerCreateReq) -> tsi.ScorerCreateRes:
        """Create a scorer object by first creating its score op, then creating the scorer object.

        The scorer object references the op that implements the scoring logic.
        """
        # Generate a safe ID for the scorer
        scorer_id = object_creation_utils.make_object_id(req.name, "Scorer")

        # Create the score op first
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_score",
            source_code=req.op_source_code,
        )
        score_op_res = self.op_create(score_op_req)
        score_op_ref = score_op_res.digest

        # Create the default summarize op
        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{scorer_id}_summarize",
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_op_ref = summarize_op_res.digest

        # Create the scorer object using shared utility for val
        scorer_val = object_creation_utils.build_scorer_val(
            name=req.name,
            description=req.description,
            score_op_ref=score_op_ref,
            summarize_op_ref=summarize_op_ref,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=scorer_id,
                val=scorer_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=scorer_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        # Construct the scorer reference using InternalObjectRef
        scorer_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=scorer_id,
            version=obj_result.digest,
        ).uri()

        return tsi.ScorerCreateRes(
            digest=obj_result.digest,
            object_id=scorer_id,
            version_index=obj_read_res.obj.version_index,
            scorer=scorer_ref,
        )

    def scorer_read(self, req: tsi.ScorerReadReq) -> tsi.ScorerReadRes:
        """Get scorer objects by delegating to obj_read."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name", result.obj.object_id)
        description = val.get("description")

        # Create the response with all required fields
        return tsi.ScorerReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            score_op=val.get("score", ""),
        )

    def scorer_list(self, req: tsi.ScorerListReq) -> Iterator[tsi.ScorerReadRes]:
        """List scorer objects by delegating to objs_query with Scorer filtering."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(base_object_classes=["Scorer"], is_op=False),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            # Extract name, description, and score_op from val data
            name = obj.object_id  # fallback to object_id
            description = None
            score_op = ""

            if hasattr(obj, "val") and obj.val:
                val = obj.val
                if isinstance(val, dict):
                    name = val.get("name", obj.object_id)
                    description = val.get("description")
                    score_op = val.get("score", "")

            yield tsi.ScorerReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                score_op=score_op,
            )

    def scorer_delete(self, req: tsi.ScorerDeleteReq) -> tsi.ScorerDeleteRes:
        """Delete scorer objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ScorerDeleteRes(num_deleted=result.num_deleted)

    def evaluation_create(
        self, req: tsi.EvaluationCreateReq
    ) -> tsi.EvaluationCreateRes:
        """Create an evaluation object.

        Creates placeholder ops for evaluate, predict_and_score, and summarize methods.
        """
        # Generate a safe ID for the evaluation
        evaluation_id = object_creation_utils.make_object_id(req.name, "Evaluation")

        # Create placeholder evaluate op
        evaluate_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.evaluate",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATE_OP_SOURCE,
        )
        evaluate_op_res = self.op_create(evaluate_op_req)
        evaluate_ref = evaluate_op_res.digest

        # Create placeholder predict_and_score op
        predict_and_score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.predict_and_score",
            source_code=object_creation_utils.PLACEHOLDER_PREDICT_AND_SCORE_OP_SOURCE,
        )
        predict_and_score_op_res = self.op_create(predict_and_score_op_req)
        predict_and_score_ref = predict_and_score_op_res.digest

        # Create placeholder summarize op
        summarize_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=f"{evaluation_id}.summarize",
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE,
        )
        summarize_op_res = self.op_create(summarize_op_req)
        summarize_ref = summarize_op_res.digest

        # Build the evaluation object using shared utility
        evaluation_val = object_creation_utils.build_evaluation_val(
            name=req.name,
            dataset_ref=req.dataset,
            trials=req.trials,
            description=req.description,
            scorer_refs=req.scorers,
            evaluation_name=req.evaluation_name,
            metadata=None,
            preprocess_model_input=None,
            eval_attributes=req.eval_attributes,
            evaluate_ref=evaluate_ref,
            predict_and_score_ref=predict_and_score_ref,
            summarize_ref=summarize_ref,
        )

        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=evaluation_id,
                val=evaluation_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=evaluation_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        # Build evaluation reference - external adapter will convert to external format
        evaluation_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=evaluation_id,
            version=obj_result.digest,
        ).uri()

        return tsi.EvaluationCreateRes(
            digest=obj_result.digest,
            object_id=evaluation_id,
            version_index=obj_read_res.obj.version_index,
            evaluation_ref=evaluation_ref,
        )

    def evaluation_read(self, req: tsi.EvaluationReadReq) -> tsi.EvaluationReadRes:
        """Get evaluation objects by delegating to obj_read."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self.obj_read(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name", result.obj.object_id)
        description = val.get("description")

        # Create the response with all required fields
        return tsi.EvaluationReadRes(
            object_id=result.obj.object_id,
            digest=result.obj.digest,
            version_index=result.obj.version_index,
            created_at=result.obj.created_at,
            name=name,
            description=description,
            dataset=val.get("dataset", ""),
            scorers=val.get("scorers", []),
            trials=val.get("trials", 1),
            evaluation_name=val.get("evaluation_name"),
            evaluate_op=val.get("evaluate", ""),
            predict_and_score_op=val.get("predict_and_score", ""),
            summarize_op=val.get("summarize", ""),
        )

    def evaluation_list(
        self, req: tsi.EvaluationListReq
    ) -> Iterator[tsi.EvaluationReadRes]:
        """List evaluation objects by delegating to objs_query."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["Evaluation"], is_op=False
            ),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        for obj in result.objs:
            val = obj.val if hasattr(obj, "val") and obj.val else {}

            # Extract name and description from val data
            name = (
                val.get("name", obj.object_id)
                if isinstance(val, dict)
                else obj.object_id
            )
            description = val.get("description") if isinstance(val, dict) else None

            yield tsi.EvaluationReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                dataset=val.get("dataset", "") if isinstance(val, dict) else "",
                scorers=val.get("scorers", []) if isinstance(val, dict) else [],
                trials=val.get("trials", 1) if isinstance(val, dict) else 1,
                evaluation_name=val.get("evaluation_name")
                if isinstance(val, dict)
                else None,
                evaluate_op=val.get("evaluate", "") if isinstance(val, dict) else "",
                predict_and_score_op=val.get("predict_and_score", "")
                if isinstance(val, dict)
                else "",
                summarize_op=val.get("summarize", "") if isinstance(val, dict) else "",
            )

    def evaluation_delete(
        self, req: tsi.EvaluationDeleteReq
    ) -> tsi.EvaluationDeleteRes:
        """Delete evaluation objects by delegating to obj_delete."""
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.EvaluationDeleteRes(num_deleted=result.num_deleted)

    # Model V2 API

    def model_create(self, req: tsi.ModelCreateReq) -> tsi.ModelCreateRes:
        """Create a model object.

        Args:
            req: ModelCreateReq containing project_id, name, description, source_code, and attributes

        Returns:
            ModelCreateRes with digest, object_id, version_index, and model_ref
        """
        # Store source code as a file
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=req.source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        # Build the model object value structure
        model_val = object_creation_utils.build_model_val(
            name=req.name,
            description=req.description,
            source_file_digest=source_file_res.digest,
            attributes=req.attributes,
        )

        # Generate object_id based on name
        object_id = object_creation_utils.make_object_id(req.name, "Model")

        # Create the object
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=model_val,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query back to get version_index
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        # Build model reference - external adapter will convert to external format
        model_ref = ri.InternalObjectRef(
            project_id=req.project_id,
            name=object_id,
            version=obj_result.digest,
        ).uri()

        return tsi.ModelCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
            model_ref=model_ref,
        )

    def model_read(self, req: tsi.ModelReadReq) -> tsi.ModelReadRes:
        """Read a model object.

        Args:
            req: ModelReadReq containing project_id, object_id, and digest

        Returns:
            ModelReadRes with all model details
        """
        # Read the object
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        obj_read_res = self.obj_read(obj_read_req)

        # Extract model properties from the val dict
        val = obj_read_res.obj.val
        name = val.get("name", req.object_id)
        description = val.get("description")

        # Get source code from file
        files = val.get("files", {})
        source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
        if not source_file_digest:
            raise ValueError(f"Model {req.object_id} has no source file")

        file_content_req = tsi.FileContentReadReq(
            project_id=req.project_id,
            digest=source_file_digest,
        )
        file_content_res = self.file_content_read(file_content_req)
        source_code = file_content_res.content.decode("utf-8")

        # Extract additional attributes (exclude system fields)
        excluded_fields = {
            "_type",
            "_class_name",
            "_bases",
            "name",
            "description",
            "files",
        }
        attributes = {k: v for k, v in val.items() if k not in excluded_fields}

        return tsi.ModelReadRes(
            object_id=req.object_id,
            digest=req.digest,
            version_index=obj_read_res.obj.version_index,
            created_at=obj_read_res.obj.created_at,
            name=name,
            description=description,
            source_code=source_code,
            attributes=attributes if attributes else None,
        )

    def model_list(self, req: tsi.ModelListReq) -> Iterator[tsi.ModelReadRes]:
        """List model objects by delegating to objs_query with Model filtering."""
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(base_object_classes=["Model"], is_op=False),
            limit=req.limit,
            offset=req.offset,
        )
        obj_query_res = self.objs_query(obj_query_req)

        for obj in obj_query_res.objs:
            # Build ModelReadRes from each object
            val = obj.val
            name = val.get("name", obj.object_id)
            description = val.get("description")

            # Get source code from file
            files = val.get("files", {})
            source_file_digest = files.get(object_creation_utils.OP_SOURCE_FILE_NAME)
            if source_file_digest:
                file_content_req = tsi.FileContentReadReq(
                    project_id=req.project_id,
                    digest=source_file_digest,
                )
                file_content_res = self.file_content_read(file_content_req)
                source_code = file_content_res.content.decode("utf-8")
            else:
                source_code = ""

            # Extract additional attributes
            excluded_fields = {
                "_type",
                "_class_name",
                "_bases",
                "name",
                "description",
                "files",
            }
            attributes = {k: v for k, v in val.items() if k not in excluded_fields}

            yield tsi.ModelReadRes(
                object_id=obj.object_id,
                digest=obj.digest,
                version_index=obj.version_index,
                created_at=obj.created_at,
                name=name,
                description=description,
                source_code=source_code,
                attributes=attributes if attributes else None,
            )

    def model_delete(self, req: tsi.ModelDeleteReq) -> tsi.ModelDeleteRes:
        """Delete model objects by delegating to obj_delete.

        Args:
            req: ModelDeleteReq containing project_id, object_id, and optional digests

        Returns:
            ModelDeleteRes with the number of deleted versions
        """
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )
        result = self.obj_delete(obj_delete_req)
        return tsi.ModelDeleteRes(num_deleted=result.num_deleted)

    def evaluation_run_create(
        self, req: tsi.EvaluationRunCreateReq
    ) -> tsi.EvaluationRunCreateRes:
        """Create an evaluation run as a call with special attributes."""
        evaluation_run_id = generate_id()

        # Start a call to represent the evaluation run
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=evaluation_run_id,
                trace_id=evaluation_run_id,
                op_name=constants.EVALUATION_RUN_OP_NAME,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={
                    constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                        constants.EVALUATION_RUN_ATTR_KEY: "true",
                        constants.EVALUATION_RUN_EVALUATION_ATTR_KEY: req.evaluation,
                        constants.EVALUATION_RUN_MODEL_ATTR_KEY: req.model,
                    }
                },
                inputs={
                    "self": req.evaluation,
                    "model": req.model,
                },
            )
        )
        self.call_start(call_start_req)

        return tsi.EvaluationRunCreateRes(evaluation_run_id=evaluation_run_id)

    def evaluation_run_read(
        self, req: tsi.EvaluationRunReadReq
    ) -> tsi.EvaluationRunReadRes:
        """Read an evaluation run by reading the underlying call."""
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        # Determine status
        status = determine_call_status(call)

        return tsi.EvaluationRunReadRes(
            evaluation_run_id=call.id,
            evaluation=attributes.get(constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""),
            model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
            status=status,
            started_at=call.started_at,
            finished_at=call.ended_at,
            summary=call.summary,
        )

    def evaluation_run_list(
        self, req: tsi.EvaluationRunListReq
    ) -> Iterator[tsi.EvaluationRunReadRes]:
        """List evaluation runs by querying calls with evaluation_run attribute."""
        # Build query conditions to filter at database level
        conditions: list[tsi_query.Operand] = []

        # Filter for calls with evaluation_run attribute set to true
        # Note: Use string "true" for ClickHouse compatibility (JSON booleans are extracted as strings)
        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        # Apply additional filters if specified
        if req.filter:
            if req.filter.evaluations:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(
                                get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_EVALUATION_ATTR_KEY}"
                            ),
                            tsi_query.LiteralOperation(literal_=req.filter.evaluations),
                        ]
                    )
                )
            if req.filter.models:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(
                                get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.EVALUATION_RUN_MODEL_ATTR_KEY}"
                            ),
                            tsi_query.LiteralOperation(literal_=req.filter.models),
                        ]
                    )
                )
            if req.filter.evaluation_run_ids:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(get_field_="id"),
                            tsi_query.LiteralOperation(
                                literal_=req.filter.evaluation_run_ids
                            ),
                        ]
                    )
                )

        # Combine all conditions with AND
        query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        # Query for calls that have the evaluation_run attribute
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        # Use calls_query_stream to avoid loading all calls into memory
        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
            status = determine_call_status(call)

            yield tsi.EvaluationRunReadRes(
                evaluation_run_id=call.id,
                evaluation=attributes.get(
                    constants.EVALUATION_RUN_EVALUATION_ATTR_KEY, ""
                ),
                model=attributes.get(constants.EVALUATION_RUN_MODEL_ATTR_KEY, ""),
                status=status,
                started_at=call.started_at,
                finished_at=call.ended_at,
                summary=call.summary,
            )

    def evaluation_run_delete(
        self, req: tsi.EvaluationRunDeleteReq
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation runs by deleting the underlying calls."""
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.evaluation_run_ids,
            wb_user_id=req.wb_user_id,
        )
        self.calls_delete(calls_delete_req)
        return tsi.EvaluationRunDeleteRes(num_deleted=len(req.evaluation_run_ids))

    def evaluation_run_finish(
        self, req: tsi.EvaluationRunFinishReq
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run by ending the underlying call.

        This creates a summarize call as a child of the evaluation run,
        then ends both the summarize call and the evaluation run.

        Args:
            req: EvaluationRunFinishReq containing project_id, evaluation_run_id, and optional summary

        Returns:
            EvaluationRunFinishRes with success status
        """
        summary = req.summary or {}

        # Read the evaluation run call to get the evaluation reference
        evaluation_run_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.evaluation_run_id,
        )
        evaluation_run_read_res = self.call_read(evaluation_run_read_req)
        evaluation_run_call = evaluation_run_read_res.call
        evaluation_ref = None
        if evaluation_run_call and evaluation_run_call.inputs:
            evaluation_ref = evaluation_run_call.inputs.get("self")

        # Query all predict_and_score children to compute means
        # (Do this first so we can use the same data for both summarize and evaluation_run)
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[req.evaluation_run_id],
            ),
            columns=["output", "op_name"],
        )
        predict_and_score_calls = self.calls_query_stream(calls_query_req)

        # Collect outputs and scores from all predict_and_score calls
        model_outputs = []
        scorer_outputs_by_name: dict[str, list[float]] = {}

        for call in predict_and_score_calls:
            # Check if this is a predict_and_score call
            if not op_name_matches(
                call.op_name, constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME
            ):
                continue

            if not call.output or not isinstance(call.output, dict):
                continue

            # Extract model output
            if "output" in call.output and call.output["output"] is not None:
                model_outputs.append(call.output["output"])

            # Extract scores
            scores = call.output.get("scores", {})
            if not isinstance(scores, dict):
                continue

            for scorer_name, score_value in scores.items():
                if scorer_name not in scorer_outputs_by_name:
                    scorer_outputs_by_name[scorer_name] = []
                # Only add numeric scores for mean calculation
                if isinstance(score_value, (int, float)):
                    scorer_outputs_by_name[scorer_name].append(float(score_value))

        # Build the evaluation run output with means
        eval_output = {}

        # Add scorer means first (before output)
        for scorer_name, scores in scorer_outputs_by_name.items():
            if scores:
                eval_output[scorer_name] = {"mean": sum(scores) / len(scores)}

        # Add model output mean last
        if model_outputs:
            # If outputs are numeric, compute mean
            try:
                numeric_outputs = [
                    float(o) for o in model_outputs if isinstance(o, (int, float))
                ]
                if numeric_outputs:
                    eval_output["output"] = {
                        "mean": sum(numeric_outputs) / len(numeric_outputs)
                    }
            except (ValueError, TypeError):
                pass

        # Create a summarize call as a child of the evaluation run
        summarize_id = generate_id()
        summarize_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=summarize_id,
                trace_id=req.evaluation_run_id,
                parent_id=req.evaluation_run_id,
                op_name=constants.EVALUATION_SUMMARIZE_OP_NAME,
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={},
                inputs={
                    "self": evaluation_ref,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(summarize_start_req)

        # End the summarize call with the same output as evaluation_run
        summarize_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=summarize_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=eval_output,
                summary={},
            )
        )
        self.call_end(summarize_end_req)

        # End the evaluation run call
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.evaluation_run_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=eval_output,
                summary=summary,
            )
        )
        self.call_end(call_end_req)
        return tsi.EvaluationRunFinishRes(success=True)

    # Prediction V2 API

    def prediction_create(
        self, req: tsi.PredictionCreateReq
    ) -> tsi.PredictionCreateRes:
        """Create a prediction as a call with special attributes.

        Args:
            req: PredictionCreateReq containing project_id, model, inputs, and output

        Returns:
            PredictionCreateRes with the prediction_id
        """
        prediction_id = generate_id()

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, create a predict_and_score parent call
            trace_id = req.evaluation_run_id
            predict_and_score_id = generate_id()

            # Read the evaluation run call to get the evaluation reference
            evaluation_run_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=req.evaluation_run_id,
            )
            evaluation_run_call = self.call_read(evaluation_run_read_req)
            evaluation_ref = (
                evaluation_run_call.call.inputs.get("self")
                if evaluation_run_call.call
                else None
            )

            # Create the predict_and_score op
            predict_and_score_op_req = tsi.OpCreateReq(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                source_code=object_creation_utils.PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE,
            )
            predict_and_score_op_res = self.op_create(predict_and_score_op_req)

            # Build the predict_and_score op ref
            predict_and_score_op_ref = ri.InternalOpRef(
                project_id=req.project_id,
                name=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                version=predict_and_score_op_res.digest,
            )

            # Create the predict_and_score call as a child of the evaluation run
            predict_and_score_start_req = tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=req.project_id,
                    id=predict_and_score_id,
                    trace_id=trace_id,
                    parent_id=req.evaluation_run_id,
                    op_name=predict_and_score_op_ref.uri(),
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={
                        constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                            constants.EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY: prediction_id,
                        }
                    },
                    inputs={
                        "self": evaluation_ref,
                        "model": req.model,
                        "example": req.inputs,
                    },
                    wb_user_id=req.wb_user_id,
                )
            )
            self.call_start(predict_and_score_start_req)

            # The prediction will be a child of predict_and_score
            parent_id = predict_and_score_id
        else:
            # Standalone prediction (not part of an evaluation)
            trace_id = prediction_id
            parent_id = None

        # Parse the model ref to get the model name
        try:
            model_ref = ri.parse_internal_uri(req.model)
            if isinstance(model_ref, (ri.InternalObjectRef, ri.InternalOpRef)):
                model_name = model_ref.name
            else:
                # Fallback to default if not an object/op ref
                model_name = "Model"
        except ri.InvalidInternalRef:
            # Fallback to default if parsing fails
            model_name = "Model"

        # Create the predict op with the model-specific name
        predict_op_name = f"{model_name}.predict"
        predict_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=predict_op_name,
            source_code=object_creation_utils.PLACEHOLDER_MODEL_PREDICT_OP_SOURCE,
        )
        predict_op_res = self.op_create(predict_op_req)

        # Build the predict op ref
        predict_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=predict_op_name,
            version=predict_op_res.digest,
        )

        # Start a call to represent the prediction
        prediction_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.PREDICTION_ATTR_KEY: "true",
                constants.PREDICTION_MODEL_ATTR_KEY: req.model,
            }
        }
        # Store evaluation_run_id as attribute if provided
        if req.evaluation_run_id:
            prediction_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=predict_op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=prediction_attributes,
                inputs={
                    "self": req.model,
                    "inputs": req.inputs,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        # End the call immediately with the output
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.output,
                summary={},
            )
        )
        self.call_end(call_end_req)

        return tsi.PredictionCreateRes(prediction_id=prediction_id)

    def prediction_read(self, req: tsi.PredictionReadReq) -> tsi.PredictionReadRes:
        """Read a prediction by reading the underlying call.

        Args:
            req: PredictionReadReq containing project_id and prediction_id

        Returns:
            PredictionReadRes with all prediction details

        Raises:
            NotFoundError: If the prediction is not found
        """
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
        evaluation_run_id = attributes.get(
            constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
        )
        if evaluation_run_id is None and call.parent_id:
            # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
            parent_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=call.parent_id,
            )
            parent_res = self.call_read(parent_read_req)
            if parent_res.call and op_name_matches(
                parent_res.call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            ):
                evaluation_run_id = parent_res.call.parent_id

        return tsi.PredictionReadRes(
            prediction_id=call.id,
            model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
            inputs=call.inputs.get("inputs") if call.inputs else {},
            output=call.output,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def prediction_list(
        self, req: tsi.PredictionListReq
    ) -> Iterator[tsi.PredictionReadRes]:
        """List predictions by querying calls with prediction attribute.

        Args:
            req: PredictionListReq containing project_id, limit, and offset

        Yields:
            PredictionReadRes for each prediction found
        """
        # Build query conditions to filter at database level
        conditions: list[tsi_query.Operand] = []

        # Filter for calls with prediction attribute set to true
        # Note: Use string "true" for ClickHouse compatibility (JSON booleans are extracted as strings)
        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        # Filter by evaluation_run_id if provided
        if req.evaluation_run_id:
            conditions.append(
                tsi_query.EqOperation(
                    eq_=[
                        tsi_query.GetFieldOperator(
                            get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY}"
                        ),
                        tsi_query.LiteralOperation(literal_=req.evaluation_run_id),
                    ]
                )
            )

        # Combine all conditions with AND (or use single condition if only one)
        if len(conditions) == 1:
            query = tsi.Query(expr_=conditions[0])
        else:
            query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        # Query for calls that have the prediction attribute
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        # Yield predictions
        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

            # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
            evaluation_run_id = attributes.get(
                constants.PREDICTION_EVALUATION_RUN_ID_ATTR_KEY
            )
            if evaluation_run_id is None and call.parent_id:
                # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
                parent_read_req = tsi.CallReadReq(
                    project_id=req.project_id,
                    id=call.parent_id,
                )
                parent_res = self.call_read(parent_read_req)
                if parent_res.call and op_name_matches(
                    parent_res.call.op_name,
                    constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                ):
                    evaluation_run_id = parent_res.call.parent_id

            yield tsi.PredictionReadRes(
                prediction_id=call.id,
                model=attributes.get(constants.PREDICTION_MODEL_ATTR_KEY, ""),
                inputs=call.inputs.get("inputs") if call.inputs else {},
                output=call.output,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def prediction_delete(
        self, req: tsi.PredictionDeleteReq
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions by deleting the underlying calls.

        Args:
            req: PredictionDeleteReq containing project_id and prediction_ids

        Returns:
            PredictionDeleteRes with the number of deleted predictions
        """
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.prediction_ids,
            wb_user_id=req.wb_user_id,
        )
        self.calls_delete(calls_delete_req)
        return tsi.PredictionDeleteRes(num_deleted=len(req.prediction_ids))

    def prediction_finish(
        self, req: tsi.PredictionFinishReq
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction by ending the underlying call.

        If the prediction is part of an evaluation (has a predict_and_score parent),
        this will also finish the predict_and_score parent call.

        Args:
            req: PredictionFinishReq containing project_id and prediction_id

        Returns:
            PredictionFinishRes with success status
        """
        # Read the prediction to check if it has a parent (predict_and_score call)
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        # Finish the prediction call
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=req.prediction_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=None,
                summary={},
            )
        )
        self.call_end(call_end_req)

        # If this prediction has a parent (predict_and_score call), finish that too
        prediction_call = prediction_res.call
        if not prediction_call or not prediction_call.parent_id:
            return tsi.PredictionFinishRes(success=True)

        # Check if the parent is a predict_and_score call (not the evaluation_run itself)
        parent_id = prediction_call.parent_id
        parent_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=parent_id,
        )
        parent_res = self.call_read(parent_read_req)

        if not parent_res.call or not op_name_matches(
            parent_res.call.op_name,
            constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        ):
            return tsi.PredictionFinishRes(success=True)

        # Build the scores dict by querying all score children of predict_and_score
        scores_dict = {}

        # Build query to filter for score calls at database level
        score_query = tsi.Query(
            expr_=tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[parent_id],
            ),
            query=score_query,
            columns=[
                "output",
                "attributes",
            ],
        )

        for score_call in self.calls_query_stream(calls_query_req):
            if score_call.output is None:
                continue

            # Get scorer name from the scorer ref in attributes
            weave_attrs = score_call.attributes.get(
                constants.WEAVE_ATTRIBUTES_NAMESPACE, {}
            )
            scorer_ref = weave_attrs.get(constants.SCORE_SCORER_ATTR_KEY)

            # Extract scorer name from ref (e.g., "weave:///entity/project/Scorer:digest" -> "Scorer")
            scorer_name = "unknown"
            if scorer_ref and isinstance(scorer_ref, str):
                # Parse the weave:// URI to get the object name
                parts = scorer_ref.split("/")
                if parts:
                    # Get the last part which should be like "Scorer:digest"
                    name_and_digest = parts[-1]
                    if ":" in name_and_digest:
                        scorer_name = name_and_digest.split(":")[0]

            scores_dict[scorer_name] = score_call.output

        # Calculate model latency from the prediction call's timestamps
        model_latency = None
        if prediction_call.started_at and prediction_call.ended_at:
            latency_seconds = (
                prediction_call.ended_at - prediction_call.started_at
            ).total_seconds()
            model_latency = {"mean": latency_seconds}

        # Finish the predict_and_score parent call with proper output
        parent_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=parent_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output={
                    "output": prediction_call.output,
                    "scores": scores_dict,
                    "model_latency": model_latency,
                },
                summary={},
            )
        )
        self.call_end(parent_end_req)

        return tsi.PredictionFinishRes(success=True)

    # Score V2 API

    def score_create(self, req: tsi.ScoreCreateReq) -> tsi.ScoreCreateRes:
        """Create a score as a call with special attributes.

        Args:
            req: ScoreCreateReq containing project_id, prediction_id, scorer, and value

        Returns:
            ScoreCreateRes with the score_id
        """
        score_id = generate_id()

        # Read the prediction to get its inputs and output
        prediction_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.prediction_id,
        )
        prediction_res = self.call_read(prediction_read_req)

        # Extract inputs and output from the prediction call
        prediction_inputs = {}
        prediction_output = None
        if prediction_res.call:
            # The prediction call has inputs structured as {"self": model_ref, "inputs": actual_inputs}
            # We want just the actual_inputs part
            if isinstance(prediction_res.call.inputs, dict):
                prediction_inputs = prediction_res.call.inputs.get("inputs", {})
            prediction_output = prediction_res.call.output

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, find the prediction's parent (predict_and_score call)
            # and make this score a sibling of the prediction
            trace_id = req.evaluation_run_id

            if prediction_res.call and prediction_res.call.parent_id:
                # Use the prediction's parent as this score's parent
                parent_id = prediction_res.call.parent_id
            else:
                # Fallback: make it a direct child of the evaluation_run
                parent_id = req.evaluation_run_id
        else:
            # Standalone score (not part of an evaluation)
            trace_id = score_id
            parent_id = None

        # Parse the scorer ref to get the scorer name
        scorer_ref = ri.parse_internal_uri(req.scorer)
        if not isinstance(scorer_ref, ri.InternalObjectRef):
            raise TypeError(f"Invalid scorer ref: {req.scorer}")
        scorer_name = scorer_ref.name

        # Create the score op with scorer-specific name
        score_op_name = f"{scorer_name}.score"
        score_op_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=score_op_name,
            source_code=object_creation_utils.PLACEHOLDER_SCORER_SCORE_OP_SOURCE,
        )
        score_op_res = self.op_create(score_op_req)

        # Build the score op ref
        score_op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=score_op_name,
            version=score_op_res.digest,
        )

        # Start a call to represent the score
        score_attributes = {
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.SCORE_ATTR_KEY: "true",
                constants.SCORE_PREDICTION_ID_ATTR_KEY: req.prediction_id,
                constants.SCORE_SCORER_ATTR_KEY: req.scorer,
            }
        }
        # Store evaluation_run_id as attribute if provided
        if req.evaluation_run_id:
            score_attributes[constants.WEAVE_ATTRIBUTES_NAMESPACE][
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            ] = req.evaluation_run_id

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name=score_op_ref.uri(),
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes=score_attributes,
                inputs={
                    "self": req.scorer,
                    "inputs": prediction_inputs,
                    "output": prediction_output,
                },
                wb_user_id=req.wb_user_id,
            )
        )
        self.call_start(call_start_req)

        # End the call immediately with the score value
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=req.project_id,
                id=score_id,
                ended_at=datetime.datetime.now(datetime.timezone.utc),
                output=req.value,
                summary={},
            )
        )
        self.call_end(call_end_req)

        # Also create feedback on the prediction (Model.predict) call
        # This makes the score visible in the UI attached to the prediction
        prediction_call_ref = ri.InternalCallRef(
            project_id=req.project_id,
            id=req.prediction_id,
        )

        # Get wb_user_id from request or fall back to prediction's wb_user_id or default
        wb_user_id = (
            req.wb_user_id
            or (prediction_res.call.wb_user_id if prediction_res.call else None)
            or "unknown"
        )

        feedback_req = tsi.FeedbackCreateReq(
            project_id=req.project_id,
            weave_ref=prediction_call_ref.uri(),
            feedback_type=f"{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{scorer_name}",
            payload={"output": req.value},
            runnable_ref=req.scorer,
            wb_user_id=wb_user_id,
        )
        self.feedback_create(feedback_req)

        return tsi.ScoreCreateRes(score_id=score_id)

    def score_read(self, req: tsi.ScoreReadReq) -> tsi.ScoreReadRes:
        """Read a score by reading the underlying call.

        Args:
            req: ScoreReadReq containing project_id and score_id

        Returns:
            ScoreReadRes with all score details

        Raises:
            NotFoundError: If the score is not found
        """
        call_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=req.score_id,
        )
        call_res = self.call_read(call_read_req)

        if call_res.call is None:
            raise NotFoundError(f"Score {req.score_id} not found")

        call = call_res.call
        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

        # Extract score value from output
        # The output is stored directly as the numeric value
        value = call.output if call.output is not None else 0.0

        # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
        evaluation_run_id = attributes.get(constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY)
        if evaluation_run_id is None and call.parent_id:
            # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
            parent_read_req = tsi.CallReadReq(
                project_id=req.project_id,
                id=call.parent_id,
            )
            parent_res = self.call_read(parent_read_req)
            if parent_res.call and op_name_matches(
                parent_res.call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            ):
                evaluation_run_id = parent_res.call.parent_id

        return tsi.ScoreReadRes(
            score_id=call.id,
            scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
            value=value,
            evaluation_run_id=evaluation_run_id,
            wb_user_id=call.wb_user_id,
        )

    def score_list(self, req: tsi.ScoreListReq) -> Iterator[tsi.ScoreReadRes]:
        """List scores by querying calls with score attribute.

        Args:
            req: ScoreListReq containing project_id, limit, and offset

        Yields:
            ScoreReadRes for each score found
        """
        # Build query conditions to filter at database level
        conditions: list[tsi_query.Operand] = []

        # Filter for calls with score attribute set to true
        # Note: Use string "true" for ClickHouse compatibility (JSON booleans are extracted as strings)
        conditions.append(
            tsi_query.EqOperation(
                eq_=[
                    tsi_query.GetFieldOperator(
                        get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_ATTR_KEY}"
                    ),
                    tsi_query.LiteralOperation(literal_="true"),
                ]
            )
        )

        # Filter by evaluation_run_id if provided
        if req.evaluation_run_id:
            conditions.append(
                tsi_query.EqOperation(
                    eq_=[
                        tsi_query.GetFieldOperator(
                            get_field_=f"attributes.{constants.WEAVE_ATTRIBUTES_NAMESPACE}.{constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY}"
                        ),
                        tsi_query.LiteralOperation(literal_=req.evaluation_run_id),
                    ]
                )
            )

        # Combine all conditions with AND (or use single condition if only one)
        if len(conditions) == 1:
            query = tsi.Query(expr_=conditions[0])
        else:
            query = tsi.Query(expr_=tsi_query.AndOperation(and_=conditions))

        # Query for calls that have the score attribute
        calls_query_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            query=query,
            limit=req.limit,
            offset=req.offset,
        )

        # Yield scores
        for call in self.calls_query_stream(calls_query_req):
            attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})

            # Extract score value from output (output is the value directly now)
            value = call.output if call.output is not None else 0.0

            # Get evaluation_run_id from attributes (preferred), fallback to parent traversal for backwards compatibility
            evaluation_run_id = attributes.get(
                constants.SCORE_EVALUATION_RUN_ID_ATTR_KEY
            )
            if evaluation_run_id is None and call.parent_id:
                # Fallback: If the parent is a predict_and_score call, get the evaluation_run_id from its parent
                parent_read_req = tsi.CallReadReq(
                    project_id=req.project_id,
                    id=call.parent_id,
                )
                parent_res = self.call_read(parent_read_req)
                if parent_res.call and op_name_matches(
                    parent_res.call.op_name,
                    constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                ):
                    evaluation_run_id = parent_res.call.parent_id

            yield tsi.ScoreReadRes(
                score_id=call.id,
                scorer=attributes.get(constants.SCORE_SCORER_ATTR_KEY, ""),
                value=value,
                evaluation_run_id=evaluation_run_id,
                wb_user_id=call.wb_user_id,
            )

    def score_delete(self, req: tsi.ScoreDeleteReq) -> tsi.ScoreDeleteRes:
        """Delete scores by deleting the underlying calls.

        Args:
            req: ScoreDeleteReq containing project_id and score_ids

        Returns:
            ScoreDeleteRes with the number of deleted scores
        """
        calls_delete_req = tsi.CallsDeleteReq(
            project_id=req.project_id,
            call_ids=req.score_ids,
            wb_user_id=req.wb_user_id,
        )
        self.calls_delete(calls_delete_req)
        return tsi.ScoreDeleteRes(num_deleted=len(req.score_ids))

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
        conditions: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        metadata_only: bool | None = False,
        limit: int | None = None,
        include_deleted: bool = False,
        offset: int | None = None,
        sort_by: list[tsi.SortBy] | None = None,
    ) -> list[tsi.ObjSchema]:
        conn, cursor = get_conn_cursor(self.db_path)
        conditions = conditions or []
        if not include_deleted:
            conditions.append("deleted_at IS NULL")
        if not conditions:
            conditions.append("1 = 1")
        pred = " AND ".join(conditions)
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
                is_latest,
                deleted_at,
                wb_user_id,
                leaf_object_class
            FROM objects
            WHERE project_id = ? AND {pred}
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
                # Add version_index as secondary sort to ensure deterministic ordering
                # when primary sort fields have identical values (e.g., same timestamp on Windows)
                query += f" ORDER BY {', '.join(sort_clauses)}, version_index ASC"
        else:
            # Default sort by created_at with version_index as tiebreaker
            # On Windows, datetime.now() has lower resolution, causing multiple objects
            # created in quick succession to share the same timestamp
            query += " ORDER BY created_at ASC, version_index ASC"

        if limit is not None:
            query += f" LIMIT {limit}"
        elif offset is not None:
            # SQLite requires LIMIT when using OFFSET
            query += " LIMIT -1"
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
                    deleted_at=row[9],
                    wb_user_id=row[10],
                    leaf_object_class=row[11],
                )
            )
        return result

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        results = self.table_query(req)
        yield from results.rows


def get_type(val: Any) -> str:
    if val is None:
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


def _transform_external_calls_field_to_internal_calls_field(
    field: str,
    cast: str | None = None,
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
    elif field == "summary.weave.latency_ms":
        # Special handling for latency to match sorting behavior
        field = """
            CASE
                WHEN ended_at IS NOT NULL THEN
                    CAST((julianday(ended_at) - julianday(started_at)) * 86400000 AS FLOAT)
                ELSE 0
            END
        """
        json_path = None
    elif field == "summary.weave.status":
        field = """
                            CASE
                                WHEN exception IS NOT NULL THEN 'error'
                                WHEN ended_at IS NULL THEN 'running'
                                WHEN json_extract(summary, '$.status_counts.error') > 0 THEN 'descendant_error'
                                ELSE 'success'
                            END
                        """
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
