# Clickhouse Trace Server

# A note on query structure:
# There are four major kinds of things that we query:
# - calls,
# - object_versions,
# - tables
# - files
#
# calls are identified by ID.
#
# object_versions, tables, and files are identified by digest. For these kinds of
# things, we dedupe at merge time using Clickhouse's ReplacingMergeTree, but we also
# need to dedupe at query time.
#
# Previously, we did query time deduping in *_deduped VIEWs. But it turns out
# clickhouse doesn't push down the project_id predicate into those views, so we were
# always scanning whole tables.
#
# Now, we've just written the what were views before into this file directly as
# subqueries, and put the project_id predicate in the innermost subquery, which fixes
# the problem.


import dataclasses
import datetime
import hashlib
import json
import logging
import threading
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Optional, Union, cast
from zoneinfo import ZoneInfo

import clickhouse_connect
import ddtrace
import emoji
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server import environment as wf_env
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.actions_worker.dispatcher import execute_batch
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    OrderField,
    QueryBuilderDynamicField,
    QueryBuilderField,
    build_calls_query_stats_query,
    combine_conditions,
    optimized_project_contains_call_query,
)
from weave.trace_server.clickhouse_schema import (
    CallDeleteCHInsertable,
    CallEndCHInsertable,
    CallStartCHInsertable,
    CallUpdateCHInsertable,
    ObjCHInsertable,
    ObjDeleteCHInsertable,
    SelectableCHCallSchema,
    SelectableCHObjSchema,
)
from weave.trace_server.constants import COMPLETIONS_CREATE_OP_NAME
from weave.trace_server.emoji_util import detone_emojis
from weave.trace_server.errors import (
    InsertTooLarge,
    InvalidRequest,
    MissingLLMApiKeyError,
    NotFoundError,
    ObjectDeletedError,
    RequestTooLarge,
)
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    validate_feedback_create_req,
    validate_feedback_purge_req,
)
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    FileStorageWriteError,
    key_for_project_digest,
    maybe_get_storage_client_from_env,
    read_from_bucket,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI
from weave.trace_server.ids import generate_id
from weave.trace_server.llm_completion import (
    get_custom_provider_info,
    lite_llm_completion,
)
from weave.trace_server.model_providers.model_providers import (
    read_model_to_provider_info_map,
)
from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.objects_query_builder import (
    ObjectMetadataQueryBuilder,
    format_metadata_objects_from_query_result,
    make_objects_val_query_and_parameters,
)
from weave.trace_server.opentelemetry.python_spans import ResourceSpans
from weave.trace_server.orm import ParamBuilder, Row
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context
from weave.trace_server.table_query_builder import (
    ROW_ORDER_COLUMN_NAME,
    TABLE_ROWS_ALIAS,
    VAL_DUMP_COLUMN_NAME,
    make_natural_sort_table_query,
    make_standard_table_query,
    make_table_stats_query_with_storage_size,
)
from weave.trace_server.token_costs import (
    LLM_TOKEN_PRICES_TABLE,
    validate_cost_purge_req,
)
from weave.trace_server.trace_server_common import (
    DynamicBatchProcessor,
    LRUCache,
    empty_str_to_none,
    get_nested_key,
    hydrate_calls_with_feedback,
    make_derived_summary_fields,
    make_feedback_query_req,
    set_nested_key,
)
from weave.trace_server.trace_server_interface_util import (
    assert_non_null_wb_user_id,
    bytes_digest,
    extract_refs_from_values,
    str_digest,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FILE_CHUNK_SIZE = 100000

MAX_DELETE_CALLS_COUNT = 1000
INITIAL_CALLS_STREAM_BATCH_SIZE = 50
MAX_CALLS_STREAM_BATCH_SIZE = 500


CallCHInsertable = Union[
    CallStartCHInsertable,
    CallEndCHInsertable,
    CallDeleteCHInsertable,
    CallUpdateCHInsertable,
]


all_call_insert_columns = list(
    CallStartCHInsertable.model_fields.keys()
    | CallEndCHInsertable.model_fields.keys()
    | CallDeleteCHInsertable.model_fields.keys()
    | CallUpdateCHInsertable.model_fields.keys()
)

all_call_select_columns = list(SelectableCHCallSchema.model_fields.keys())
all_call_json_columns = ("inputs", "output", "attributes", "summary")
required_call_columns = ["id", "project_id", "trace_id", "op_name", "started_at"]


# Columns in the calls_merged table with special aggregation functions:
call_select_raw_columns = ["id", "project_id"]  # no aggregation
call_select_arrays_columns = ["input_refs", "output_refs"]  # array_concat_agg
call_select_argmax_columns = ["display_name"]  # argMaxMerge
# all others use `any`


all_obj_select_columns = list(SelectableCHObjSchema.model_fields.keys())
all_obj_insert_columns = list(ObjCHInsertable.model_fields.keys())

# Let's just make everything required for now ... can optimize when we implement column selection
required_obj_select_columns = list(set(all_obj_select_columns) - set())

ObjRefListType = list[ri.InternalObjectRef]


CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT = 3.5 * 1024 * 1024  # 3.5 MiB
CLICKHOUSE_SINGLE_VALUE_BYTES_LIMIT = 1 * 1024 * 1024  # 1 MiB
ENTITY_TOO_LARGE_PAYLOAD = '{"_weave": {"error":"<EXCEEDS_LIMITS>"}}'

DEFAULT_MAX_MEMORY_USAGE = 16 * 1024 * 1024 * 1024  # 16 GiB
CLICKHOUSE_DEFAULT_QUERY_SETTINGS = {
    "max_memory_usage": wf_env.wf_clickhouse_max_memory_usage()
    or DEFAULT_MAX_MEMORY_USAGE
}


class ClickHouseTraceServer(tsi.TraceServerInterface):
    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
    ):
        super().__init__()
        self._thread_local = threading.local()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._flush_immediately = True
        self._call_batch: list[list[Any]] = []
        self._use_async_insert = use_async_insert
        self._model_to_provider_info_map = read_model_to_provider_info_map()
        self._file_storage_client: Optional[FileStorageClient] = None

    @classmethod
    def from_env(cls, use_async_insert: bool = False) -> "ClickHouseTraceServer":
        # Explicitly calling `RemoteHTTPTraceServer` constructor here to ensure
        # that type checking is applied to the constructor.
        return ClickHouseTraceServer(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
        )

    @property
    def file_storage_client(self) -> Optional[FileStorageClient]:
        if self._file_storage_client is not None:
            return self._file_storage_client
        self._file_storage_client = maybe_get_storage_client_from_env()
        return self._file_storage_client

    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        if not isinstance(req.traces, ExportTraceServiceRequest):
            raise TypeError(
                "Expected traces as ExportTraceServiceRequest, got {type(req.traces)}"
            )
        traces_data = [
            ResourceSpans.from_proto(span) for span in req.traces.resource_spans
        ]

        calls = []
        for resource_spans in traces_data:
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
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
        # TODO: Actually populate the error fields if call_start_batch fails
        self.call_start_batch(tsi.CallCreateBatchReq(batch=calls))
        return tsi.OtelExportRes()

    @contextmanager
    def call_batch(self) -> Iterator[None]:
        # Not thread safe - do not use across threads
        self._flush_immediately = False
        try:
            yield
            self._flush_calls()
        finally:
            self._call_batch = []
            self._flush_immediately = True

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        with self.call_batch():
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
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        ch_call = _start_call_for_insert_to_ch_insertable_start_call(req.start)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        # Returns the id of the newly created call
        return tsi.CallStartRes(
            id=ch_call.id,
            trace_id=ch_call.trace_id,
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        ch_call = _end_call_for_insert_to_ch_insertable_end_call(req.end)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        # Returns the id of the newly created call
        return tsi.CallEndRes()

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        res = self.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=tsi.CallsFilter(
                    call_ids=[req.id],
                ),
                limit=1,
                include_costs=req.include_costs,
                include_storage_size=req.include_storage_size,
                include_total_storage_size=req.include_total_storage_size,
            )
        )
        try:
            _call = next(res)
        except StopIteration:
            _call = None
        return tsi.CallReadRes(call=_call)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        stream = self.calls_query_stream(req)
        return tsi.CallsQueryRes(calls=list(stream))

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Returns a stats object for the given query. This is useful for counts or other
        aggregate statistics that are not directly queryable from the calls themselves.
        """
        pb = ParamBuilder()

        # Special case when limit=1 and there is no filter or query,
        # construct highly optimized query that returns early
        if (
            req.limit == 1
            and req.filter is None
            and req.query is None
            and not req.include_total_storage_size
        ):
            query = optimized_project_contains_call_query(req.project_id, pb)
            raw_res = self._query(query, pb.get_params())
            rows = raw_res.result_rows
            count = rows[0][0]
            return tsi.CallsQueryStatsRes(
                count=count,
                total_storage_size_bytes=None,
            )

        query, columns = build_calls_query_stats_query(req, pb)

        raw_res = self._query(query, pb.get_params())

        res_dict = (
            dict(zip(columns, raw_res.result_rows[0])) if raw_res.result_rows else {}
        )

        return tsi.CallsQueryStatsRes(
            count=res_dict.get("count", 0),
            total_storage_size_bytes=res_dict.get("total_storage_size_bytes"),
        )

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Returns a stream of calls that match the given query."""
        cq = CallsQuery(
            project_id=req.project_id,
            include_costs=req.include_costs or False,
            include_storage_size=req.include_storage_size or False,
            include_total_storage_size=req.include_total_storage_size or False,
        )
        columns = all_call_select_columns
        if req.columns:
            # TODO: add support for json extract fields
            # Split out any nested column requests
            columns = [col.split(".")[0] for col in req.columns]

            # If we are returning a summary object, make sure that all fields
            # required to compute the summary are in the columns
            if "summary" in columns or req.include_costs:
                columns += ["ended_at", "exception", "display_name"]

            # Set columns to user-requested columns, w/ required columns
            # These are all formatted by the CallsQuery, which prevents injection
            # and other attack vectors.
            columns = list(set(required_call_columns + columns))

        # sort the columns such that similar queries are grouped together
        columns = sorted(columns)

        # The order is actually important, it has something to do with how the cost_query wants to arrange things.
        # specifically, the summary column should always be the last.
        if req.include_storage_size:
            columns.append("storage_size_bytes")

        if req.include_total_storage_size:
            columns.append("total_storage_size_bytes")

        # We put summary_dump last so that when we compute the costs and summary its in the right place
        if req.include_costs:
            summary_columns = ["summary", "summary_dump"]
            columns = [
                *[col for col in columns if col not in summary_columns],
                "summary_dump",
            ]

        for col in columns:
            cq.add_field(col)
        if req.filter is not None:
            cq.set_hardcoded_filter(HardCodedFilter(filter=req.filter))
        if req.query is not None:
            cq.add_condition(req.query.expr_)

        # Sort with empty list results in no sorting
        if req.sort_by is not None:
            for sort_by in req.sort_by:
                cq.add_order(sort_by.field, sort_by.direction)
        else:
            cq.add_order("started_at", "asc")
        if req.limit is not None:
            cq.set_limit(req.limit)
        if req.offset is not None:
            cq.set_offset(req.offset)

        pb = ParamBuilder()
        raw_res = self._query_stream(
            cq.as_sql(pb),
            pb.get_params(),
        )

        select_columns = [c.field for c in cq.select_fields]
        expand_columns = req.expand_columns or []
        include_feedback = req.include_feedback or False

        def row_to_call_schema_dict(row: tuple[Any, ...]) -> dict[str, Any]:
            return _ch_call_dict_to_call_schema_dict(dict(zip(select_columns, row)))

        if not expand_columns and not include_feedback:
            for row in raw_res:
                yield tsi.CallSchema.model_validate(row_to_call_schema_dict(row))
            return

        ref_cache = LRUCache(max_size=1000)
        batch_processor = DynamicBatchProcessor(
            initial_size=INITIAL_CALLS_STREAM_BATCH_SIZE,
            max_size=MAX_CALLS_STREAM_BATCH_SIZE,
            growth_factor=10,
        )

        for batch in batch_processor.make_batches(raw_res):
            call_dicts = [row_to_call_schema_dict(row) for row in batch]
            if expand_columns:
                self._expand_call_refs(
                    req.project_id, call_dicts, expand_columns, ref_cache
                )

            if include_feedback:
                self._add_feedback_to_calls(req.project_id, call_dicts)

            for call in call_dicts:
                yield tsi.CallSchema.model_validate(call)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._add_feedback_to_calls")
    def _add_feedback_to_calls(
        self, project_id: str, calls: list[dict[str, Any]]
    ) -> None:
        if len(calls) == 0:
            return

        feedback_query_req = make_feedback_query_req(project_id, calls)
        with self.with_new_client():
            feedback = self.feedback_query(feedback_query_req)
        hydrate_calls_with_feedback(calls, feedback)

    def _get_refs_to_resolve(
        self, calls: list[dict[str, Any]], expand_columns: list[str]
    ) -> dict[tuple[int, str], ri.InternalObjectRef]:
        refs_to_resolve: dict[tuple[int, str], ri.InternalObjectRef] = {}
        for i, call in enumerate(calls):
            for col in expand_columns:
                if col in call:
                    val = call[col]
                else:
                    val = get_nested_key(call, col)
                    if not val:
                        continue

                if not ri.any_will_be_interpreted_as_ref_str(val):
                    continue

                ref = ri.parse_internal_uri(val)
                if not isinstance(ref, ri.InternalObjectRef):
                    continue

                refs_to_resolve[(i, col)] = ref
        return refs_to_resolve

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._expand_call_refs")
    def _expand_call_refs(
        self,
        project_id: str,
        calls: list[dict[str, Any]],
        expand_columns: list[str],
        ref_cache: LRUCache,
    ) -> None:
        if len(calls) == 0:
            return

        # format expand columns by depth, iterate through each batch in order
        expand_column_by_depth = defaultdict(list)
        for col in expand_columns:
            expand_column_by_depth[col.count(".")].append(col)

        for depth in sorted(expand_column_by_depth.keys()):
            refs_to_resolve = self._get_refs_to_resolve(
                calls, expand_column_by_depth[depth]
            )
            if not refs_to_resolve:
                continue

            with self.with_new_client():
                # Filter out non-unique refs
                unique_ref_map = {}
                for ref in refs_to_resolve.values():
                    if ref.uri() not in unique_ref_map:
                        unique_ref_map[ref.uri()] = ref

                # Fetch values only for the unique refs
                vals = self._refs_read_batch_within_project(
                    project_id, list(unique_ref_map.values()), ref_cache
                )

                # update the ref map with the fetched values
                ref_val_map = {}
                for ref, val in zip(unique_ref_map.values(), vals):
                    ref_val_map[ref.uri()] = val

                # Replace the refs with values and add ref key
                for (i, col), ref in refs_to_resolve.items():
                    # Look up the value using the ref's URI
                    val = ref_val_map.get(ref.uri())
                    if val is not None:
                        if isinstance(val, dict) and "_ref" not in val:
                            val["_ref"] = ref.uri()
                        set_nested_key(calls[i], col, val)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.calls_delete")
    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        assert_non_null_wb_user_id(req)
        if len(req.call_ids) > MAX_DELETE_CALLS_COUNT:
            raise RequestTooLarge(
                f"Cannot delete more than {MAX_DELETE_CALLS_COUNT} calls at once"
            )

        if root_span := ddtrace.tracer.current_span():
            root_span.set_tags(
                {
                    "clickhouse_trace_server_batched.calls_delete.count": str(
                        len(req.call_ids)
                    )
                }
            )

        # get the requested calls to delete
        parents = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi.CallsFilter(
                        call_ids=req.call_ids,
                    ),
                    columns=["id", "parent_id"],
                )
            )
        )
        parent_trace_ids = [p.trace_id for p in parents]

        # get first 10k calls with trace_ids matching parents
        all_calls = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi.CallsFilter(trace_ids=parent_trace_ids),
                    columns=["id", "parent_id"],
                    limit=10_000,
                )
            )
        )
        all_descendants = find_call_descendants(
            root_ids=req.call_ids,
            all_calls=all_calls,
        )

        deleted_at = datetime.datetime.now()
        insertables = [
            CallDeleteCHInsertable(
                project_id=req.project_id,
                id=call_id,
                wb_user_id=req.wb_user_id,
                deleted_at=deleted_at,
            )
            for call_id in all_descendants
        ]

        with self.call_batch():
            for insertable in insertables:
                self._insert_call(insertable)

        return tsi.CallsDeleteRes()

    def _ensure_valid_update_field(self, req: tsi.CallUpdateReq) -> None:
        valid_update_fields = ["display_name"]
        for field in valid_update_fields:
            if getattr(req, field, None) is not None:
                return

        raise ValueError(
            f"One of [{', '.join(valid_update_fields)}] is required for call update"
        )

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        assert_non_null_wb_user_id(req)
        self._ensure_valid_update_field(req)
        renamed_insertable = CallUpdateCHInsertable(
            project_id=req.project_id,
            id=req.call_id,
            wb_user_id=req.wb_user_id,
            display_name=req.display_name,
        )
        self._insert_call(renamed_insertable)

        return tsi.CallUpdateRes()

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        raise NotImplementedError()

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_is_op_condition(True)
        object_query_builder.add_digests_conditions(req.digest)
        object_query_builder.add_object_ids_condition([req.name], "op_name")
        object_query_builder.set_include_deleted(include_deleted=True)

        objs = self._select_objs_query(object_query_builder)
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.name}:{req.digest} not found")

        op = objs[0]
        if op.deleted_at is not None:
            raise ObjectDeletedError(
                f"Op {req.name}:v{op.version_index} was deleted at {op.deleted_at}",
                deleted_at=op.deleted_at,
            )

        return tsi.OpReadRes(op_obj=_ch_obj_to_obj_schema(op))

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_is_op_condition(True)
        if req.filter:
            if req.filter.op_names:
                object_query_builder.add_object_ids_condition(
                    req.filter.op_names, "op_names"
                )
            if req.filter.latest_only:
                object_query_builder.add_is_latest_condition()

        ch_objs = self._select_objs_query(object_query_builder)
        objs = [_ch_obj_to_obj_schema(call) for call in ch_objs]
        return tsi.OpQueryRes(op_objs=objs)

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        processed_result = process_incoming_object_val(
            req.obj.val, req.obj.builtin_object_class
        )
        processed_val = processed_result["val"]
        json_val = json.dumps(processed_val)
        digest = str_digest(json_val)

        ch_obj = ObjCHInsertable(
            project_id=req.obj.project_id,
            object_id=req.obj.object_id,
            wb_user_id=req.obj.wb_user_id,
            kind=get_kind(processed_val),
            base_object_class=processed_result["base_object_class"],
            refs=extract_refs_from_values(processed_val),
            val_dump=json_val,
            digest=digest,
        )

        self._insert(
            "object_versions",
            data=[list(ch_obj.model_dump().values())],
            column_names=list(ch_obj.model_fields.keys()),
        )
        return tsi.ObjCreateRes(digest=digest)

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_digests_conditions(req.digest)
        object_query_builder.add_object_ids_condition([req.object_id])
        object_query_builder.set_include_deleted(include_deleted=True)
        metadata_only = req.metadata_only or False

        objs = self._select_objs_query(object_query_builder, metadata_only)
        if len(objs) == 0:
            raise NotFoundError(f"Obj {req.object_id}:{req.digest} not found")

        obj = objs[0]
        if obj.deleted_at is not None:
            raise ObjectDeletedError(
                f"{req.object_id}:v{obj.version_index} was deleted at {obj.deleted_at}",
                deleted_at=obj.deleted_at,
            )

        return tsi.ObjReadRes(obj=_ch_obj_to_obj_schema(obj))

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        if req.filter:
            if req.filter.is_op is not None:
                if req.filter.is_op:
                    object_query_builder.add_is_op_condition(True)
                else:
                    object_query_builder.add_is_op_condition(False)
            if req.filter.object_ids:
                object_query_builder.add_object_ids_condition(
                    req.filter.object_ids, "object_ids"
                )
            if req.filter.latest_only:
                object_query_builder.add_is_latest_condition()
            if req.filter.base_object_classes:
                object_query_builder.add_base_object_classes_condition(
                    req.filter.base_object_classes
                )
        if req.limit is not None:
            object_query_builder.set_limit(req.limit)
        if req.offset is not None:
            object_query_builder.set_offset(req.offset)
        if req.sort_by:
            for sort in req.sort_by:
                object_query_builder.add_order(sort.field, sort.direction)
        metadata_only = req.metadata_only or False
        object_query_builder.set_include_deleted(include_deleted=False)
        object_query_builder.include_storage_size = req.include_storage_size or False
        objs = self._select_objs_query(object_query_builder, metadata_only)
        return tsi.ObjQueryRes(objs=[_ch_obj_to_obj_schema(obj) for obj in objs])

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        """
        Delete object versions by digest, belonging to given object_id.
        All deletion in this method is "soft". Deletion occurs by inserting
        a new row into the object_versions table with the deleted_at field set.
        Inserted rows share identical primary keys (order by) with original rows,
        and will be combined by the ReplacingMergeTree engine at database merge
        time.
        If no digests are provided all versions will have their data overwritten with
        an empty val_dump.
        """
        MAX_OBJECTS_TO_DELETE = 100
        if req.digests and len(req.digests) > MAX_OBJECTS_TO_DELETE:
            raise ValueError(
                f"Object delete request contains {len(req.digests)} objects. Please delete {MAX_OBJECTS_TO_DELETE} or fewer objects at a time."
            )

        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_object_ids_condition([req.object_id])
        metadata_only = True
        if req.digests:
            object_query_builder.add_digests_conditions(*req.digests)
            metadata_only = False

        object_versions = self._select_objs_query(object_query_builder, metadata_only)

        delete_insertables = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for obj in object_versions:
            original_created_at = _ensure_datetimes_have_tz_strict(obj.created_at)
            delete_insertables.append(
                ObjDeleteCHInsertable(
                    project_id=obj.project_id,
                    object_id=obj.object_id,
                    digest=obj.digest,
                    kind=obj.kind,
                    val_dump=obj.val_dump,
                    refs=obj.refs,
                    base_object_class=obj.base_object_class,
                    deleted_at=now,
                    wb_user_id=obj.wb_user_id,
                    # Keep the original created_at timestamp
                    created_at=original_created_at,
                )
            )

        if len(delete_insertables) == 0:
            raise NotFoundError(
                f"Object {req.object_id} ({req.digests}) not found when deleting."
            )

        if req.digests:
            given_digests = set(req.digests)
            found_digests = {obj.digest for obj in delete_insertables}
            if len(given_digests) != len(found_digests):
                raise NotFoundError(
                    f"Delete request contains {len(req.digests)} digests, but found {len(found_digests)} objects to delete. Diff digests: {given_digests - found_digests}"
                )

        data = [list(obj.model_dump().values()) for obj in delete_insertables]
        column_names = list(delete_insertables[0].model_fields.keys())

        self._insert("object_versions", data=data, column_names=column_names)
        num_deleted = len(delete_insertables)

        return tsi.ObjDeleteRes(num_deleted=num_deleted)

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        insert_rows = []
        for r in req.table.rows:
            if not isinstance(r, dict):
                raise TypeError(
                    f"""Validation Error: Encountered a non-dictionary row when creating a table. Please ensure that all rows are dictionaries. Violating row:\n{r}."""
                )
            row_json = json.dumps(r)
            row_digest = str_digest(row_json)
            insert_rows.append(
                (
                    req.table.project_id,
                    row_digest,
                    extract_refs_from_values(r),
                    row_json,
                )
            )

        self._insert(
            "table_rows",
            data=insert_rows,
            column_names=["project_id", "digest", "refs", "val_dump"],
        )

        row_digests = [r[1] for r in insert_rows]

        table_hasher = hashlib.sha256()
        for row_digest in row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._insert(
            "tables",
            data=[(req.table.project_id, digest, row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )
        return tsi.TableCreateRes(digest=digest, row_digests=row_digests)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        query = """
            SELECT *
            FROM (
                    SELECT *,
                        row_number() OVER (PARTITION BY project_id, digest) AS rn
                    FROM tables
                    WHERE project_id = {project_id:String} AND digest = {digest:String}
                )
            WHERE rn = 1
            ORDER BY project_id, digest
        """

        row_digest_result_query = self.ch_client.query(
            query,
            parameters={
                "project_id": req.project_id,
                "digest": req.base_digest,
            },
        )

        if len(row_digest_result_query.result_rows) == 0:
            raise NotFoundError(f"Table {req.project_id}:{req.base_digest} not found")

        final_row_digests: list[str] = row_digest_result_query.result_rows[0][2]
        new_rows_needed_to_insert = []
        known_digests = set(final_row_digests)

        def add_new_row_needed_to_insert(row_data: Any) -> str:
            if not isinstance(row_data, dict):
                raise TypeError("All rows must be dictionaries")
            row_json = json.dumps(row_data)
            row_digest = str_digest(row_json)
            if row_digest not in known_digests:
                new_rows_needed_to_insert.append(
                    (
                        req.project_id,
                        row_digest,
                        extract_refs_from_values(row_data),
                        row_json,
                    )
                )
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

        if new_rows_needed_to_insert:
            self._insert(
                "table_rows",
                data=new_rows_needed_to_insert,
                column_names=["project_id", "digest", "refs", "val_dump"],
            )

        table_hasher = hashlib.sha256()
        for row_digest in final_row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        self._insert(
            "tables",
            data=[(req.project_id, digest, final_row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )
        return tsi.TableUpdateRes(digest=digest, updated_row_digests=updated_digests)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        rows = list(self.table_query_stream(req))
        return tsi.TableQueryRes(rows=rows)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        conds = []
        pb = ParamBuilder()
        if req.filter:
            if req.filter.row_digests:
                conds.append(
                    f"tr.digest IN {{{pb.add_param(req.filter.row_digests)}: Array(String)}}"
                )

        sort_fields = []
        if req.sort_by:
            for sort in req.sort_by:
                # TODO: better splitting of escaped dots (.) in field names
                extra_path = sort.field.split(".")
                field = OrderField(
                    field=QueryBuilderDynamicField(
                        field=VAL_DUMP_COLUMN_NAME, extra_path=extra_path
                    ),
                    direction="ASC" if sort.direction.lower() == "asc" else "DESC",
                )
                sort_fields.append(field)

        rows = self._table_query_stream(
            req.project_id,
            req.digest,
            pb,
            sql_safe_conditions=conds,
            sort_fields=sort_fields,
            limit=req.limit,
            offset=req.offset,
        )
        yield from rows

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._table_query_stream")
    def _table_query_stream(
        self,
        project_id: str,
        digest: str,
        pb: ParamBuilder,
        *,
        # using the `sql_safe_*` prefix is a way to signal to the caller
        # that these strings should have been santized by the caller.
        sql_safe_conditions: Optional[list[str]] = None,
        sort_fields: Optional[list[OrderField]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Iterator[tsi.TableRowSchema]:
        if not sort_fields:
            sort_fields = [
                OrderField(
                    field=QueryBuilderField(field=ROW_ORDER_COLUMN_NAME),
                    direction="ASC",
                )
            ]

        if (
            len(sort_fields) == 1
            and sort_fields[0].field.field == ROW_ORDER_COLUMN_NAME
            and not sql_safe_conditions
        ):
            query = make_natural_sort_table_query(
                project_id,
                digest,
                pb,
                limit=limit,
                offset=offset,
                natural_direction=sort_fields[0].direction,
            )
        else:
            order_by_components = ", ".join(
                [sort_field.as_sql(pb, TABLE_ROWS_ALIAS) for sort_field in sort_fields]
            )
            sql_safe_sort_clause = f"ORDER BY {order_by_components}"
            query = make_standard_table_query(
                project_id,
                digest,
                pb,
                sql_safe_conditions=sql_safe_conditions,
                sql_safe_sort_clause=sql_safe_sort_clause,
                limit=limit,
                offset=offset,
            )

        res = self._query_stream(query, parameters=pb.get_params())

        for row in res:
            yield tsi.TableRowSchema(
                digest=row[0], val=json.loads(row[1]), original_index=row[2]
            )

    # This is a legacy endpoint, it should be removed once the client is mostly updated
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        batch_req = tsi.TableQueryStatsBatchReq(
            project_id=req.project_id, digests=[req.digest]
        )

        res = self.table_query_stats_batch(batch_req)

        if len(res.tables) != 1:
            logger.exception(RuntimeError("Unexpected number of results", res))

        count = res.tables[0].count
        return tsi.TableQueryStatsRes(count=count)

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        parameters: dict[str, Any] = {
            "project_id": req.project_id,
            "digests": req.digests,
        }

        query = """
        SELECT digest, any(length(row_digests))
        FROM tables
        WHERE project_id = {project_id:String} AND digest IN {digests:Array(String)}
        GROUP BY digest
        """

        if req.include_storage_size:
            # Use an advanced query builder to get the storage size
            pb = ParamBuilder()
            query = make_table_stats_query_with_storage_size(
                project_id=req.project_id,
                table_digests=cast(list[str], req.digests),
                pb=pb,
            )
            parameters = pb.get_params()

        query_result = self.ch_client.query(query, parameters=parameters)

        tables = [
            _ch_table_stats_to_table_stats_schema(row)
            for row in query_result.result_rows
        ]

        return tsi.TableQueryStatsBatchRes(tables=tables)

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # TODO: This reads one ref at a time, it should read them in batches
        # where it can. Like it should group by object that we need to read.
        # And it should also batch into table refs (like when we are reading a bunch
        # of rows from a single Dataset)
        if len(req.refs) > 1000:
            raise ValueError("Too many refs")

        # First, parse the refs
        parsed_raw_refs = [ri.parse_internal_uri(r) for r in req.refs]

        # Business logic to ensure that we don't have raw TableRefs (not allowed)
        if any(isinstance(r, ri.InternalTableRef) for r in parsed_raw_refs):
            raise ValueError("Table refs not supported")

        parsed_refs = cast(ObjRefListType, parsed_raw_refs)
        vals = self._parsed_refs_read_batch(parsed_refs)

        return tsi.RefsReadBatchRes(vals=vals)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._parsed_refs_read_batch")
    def _parsed_refs_read_batch(
        self,
        parsed_refs: ObjRefListType,
        root_val_cache: Optional[dict[str, Any]] = None,
    ) -> list[Any]:
        # Next, group the refs by project_id
        refs_by_project_id: dict[str, ObjRefListType] = defaultdict(list)
        for ref in parsed_refs:
            refs_by_project_id[ref.project_id].append(ref)

        # Lookup data for each project, scoped to each project
        final_result_cache: dict[str, Any] = {}

        def make_ref_cache_key(ref: ri.InternalObjectRef) -> str:
            return ref.uri()

        for project in refs_by_project_id:
            project_refs = refs_by_project_id[project]
            project_results = self._refs_read_batch_within_project(
                project,
                refs_by_project_id[project],
                root_val_cache,
            )
            for ref, result in zip(project_refs, project_results):
                final_result_cache[make_ref_cache_key(ref)] = result

        # Return the final data payload
        return [final_result_cache[make_ref_cache_key(ref)] for ref in parsed_refs]

    @ddtrace.tracer.wrap(
        name="clickhouse_trace_server_batched._refs_read_batch_within_project"
    )
    def _refs_read_batch_within_project(
        self,
        project_id_scope: str,
        parsed_refs: ObjRefListType,
        root_val_cache: Optional[dict[str, Any]],
    ) -> list[Any]:
        if root_val_cache is None:
            root_val_cache = {}

        def make_root_ref_cache_key(ref: ri.InternalObjectRef) -> str:
            return f"{ref.project_id}/{ref.name}/{ref.version}"

        def make_obj_cache_key(obj: SelectableCHObjSchema) -> str:
            return f"{obj.project_id}/{obj.object_id}/{obj.digest}"

        def get_object_refs_root_val(
            refs: list[ri.InternalObjectRef],
        ) -> Any:
            conds: list[str] = []
            object_id_conds: list[str] = []
            parameters: dict[str, Union[str, int]] = {}
            ref_digests: set[str] = set()

            for ref_index, ref in enumerate(refs):
                if ref.version == "latest":
                    raise ValueError("Reading refs with `latest` is not supported")

                cache_key = make_root_ref_cache_key(ref)

                if cache_key in root_val_cache:
                    continue

                if ref.project_id != project_id_scope:
                    # At some point in the future, we may allow cross-project references.
                    # However, until then, we disallow this feature. Practically, we
                    # should never hit this code path since the `resolve_extra` function
                    # handles this check. However, out of caution, we add this check here.
                    # Hitting this would be a programming error, not a user error.
                    raise ValueError("Will not resolve cross-project refs.")

                object_id_param_key = "object_id_" + str(ref_index)
                version_param_key = "version_" + str(ref_index)
                conds.append(f"digest = {{{version_param_key}: String}}")
                object_id_conds.append(f"object_id = {{{object_id_param_key}: String}}")
                parameters[object_id_param_key] = ref.name
                parameters[version_param_key] = ref.version
                ref_digests.add(ref.version)
                root_val_cache[cache_key] = None
            if len(conds) > 0:
                conditions = [combine_conditions(conds, "OR")]
                object_id_conditions = [combine_conditions(object_id_conds, "OR")]
                object_query_builder = ObjectMetadataQueryBuilder(
                    project_id=project_id_scope,
                    conditions=conditions,
                    object_id_conditions=object_id_conditions,
                    parameters=parameters,
                    include_deleted=True,
                )
                objs = self._select_objs_query(object_query_builder)
                found_digests = {obj.digest for obj in objs}
                if len(ref_digests) != len(found_digests):
                    raise NotFoundError(
                        f"Ref read contains {len(ref_digests)} digests, but found {len(found_digests)} objects. Diff digests: {ref_digests - found_digests}"
                    )
                # filter out deleted objects
                valid_objects = [obj for obj in objs if obj.deleted_at is None]
                for obj in valid_objects:
                    root_val_cache[make_obj_cache_key(obj)] = json.loads(obj.val_dump)

            return [
                root_val_cache.get(make_root_ref_cache_key(ref), None) for ref in refs
            ]

        # Represents work left to do for resolving a ref
        @dataclasses.dataclass
        class PartialRefResult:
            remaining_extra: list[str]
            # unresolved_obj_ref and unresolved_table_ref are mutually exclusive
            unresolved_obj_ref: Optional[ri.InternalObjectRef]
            unresolved_table_ref: Optional[ri.InternalTableRef]
            val: Any

        def resolve_extra(extra: list[str], val: Any) -> PartialRefResult:
            for extra_index in range(0, len(extra), 2):
                empty_result = PartialRefResult(
                    remaining_extra=[],
                    unresolved_obj_ref=None,
                    unresolved_table_ref=None,
                    val=None,
                )
                op, arg = extra[extra_index], extra[extra_index + 1]
                if isinstance(val, str) and val.startswith(
                    ri.WEAVE_INTERNAL_SCHEME + "://"
                ):
                    parsed_ref = ri.parse_internal_uri(val)

                    if parsed_ref.project_id != project_id_scope:
                        # This is the primary check to enforce that we do not
                        # traverse into a different project. It is perfectly
                        # reasonable to support this functionality in the
                        # future. At such point in time, we will want to define
                        # a "check read project" function that the client can
                        # use to validate that the project is allowed to be
                        # read. Once this is lifted, other parts of this
                        # function will need to be updated as well, as they will
                        # currently `raise ValueError("Will not resolve
                        # cross-project refs.")` under such conditions.
                        return empty_result

                    if isinstance(parsed_ref, ri.InternalObjectRef):
                        return PartialRefResult(
                            remaining_extra=extra[extra_index:],
                            unresolved_obj_ref=parsed_ref,
                            unresolved_table_ref=None,
                            val=val,
                        )
                    elif isinstance(parsed_ref, ri.InternalTableRef):
                        return PartialRefResult(
                            remaining_extra=extra[extra_index:],
                            unresolved_obj_ref=None,
                            unresolved_table_ref=parsed_ref,
                            val=val,
                        )
                if val is None:
                    return empty_result
                if op == ri.DICT_KEY_EDGE_NAME:
                    val = val.get(arg)
                elif op == ri.OBJECT_ATTR_EDGE_NAME:
                    val = val.get(arg)
                elif op == ri.LIST_INDEX_EDGE_NAME:
                    index = int(arg)
                    if index >= len(val):
                        return empty_result
                    val = val[index]
                else:
                    raise ValueError(f"Unknown ref type: {extra[extra_index]}")
            return PartialRefResult(
                remaining_extra=[],
                unresolved_obj_ref=None,
                unresolved_table_ref=None,
                val=val,
            )

        # Initialize the results with the parsed refs
        extra_results = [
            PartialRefResult(
                remaining_extra=[],
                unresolved_obj_ref=ref,
                unresolved_table_ref=None,
                val=None,
            )
            for ref in parsed_refs
        ]

        # Loop until there is nothing left to resolve
        while (
            any(r.unresolved_obj_ref is not None for r in extra_results)
            or any(r.unresolved_table_ref is not None for r in extra_results)
            or any(r.remaining_extra for r in extra_results)
        ):
            # Resolve any unresolved object refs
            needed_extra_results: list[tuple[int, PartialRefResult]] = []
            for i, extra_result in enumerate(extra_results):
                if extra_result.unresolved_obj_ref is not None:
                    needed_extra_results.append((i, extra_result))

            if len(needed_extra_results) > 0:
                refs: list[ri.InternalObjectRef] = []
                for i, extra_result in needed_extra_results:
                    if extra_result.unresolved_obj_ref is None:
                        raise ValueError("Expected unresolved obj ref")
                    refs.append(extra_result.unresolved_obj_ref)
                obj_roots = get_object_refs_root_val(refs)
                for (i, extra_result), obj_root in zip(needed_extra_results, obj_roots):
                    if extra_result.unresolved_obj_ref is None:
                        raise ValueError("Expected unresolved obj ref")
                    extra_results[i] = PartialRefResult(
                        remaining_extra=extra_result.unresolved_obj_ref.extra,
                        val=obj_root,
                        unresolved_obj_ref=None,
                        unresolved_table_ref=None,
                    )

            # Resolve any unresolved table refs
            # First batch the table queries by project_id and table digest
            table_queries: dict[tuple[str, str], list[tuple[int, str]]] = {}
            for i, extra_result in enumerate(extra_results):
                if extra_result.unresolved_table_ref is not None:
                    table_ref = extra_result.unresolved_table_ref
                    if not extra_result.remaining_extra:
                        raise ValueError("Table refs must have id extra")
                    op, row_digest = (
                        extra_result.remaining_extra[0],
                        extra_result.remaining_extra[1],
                    )
                    if op != ri.TABLE_ROW_ID_EDGE_NAME:
                        raise ValueError("Table refs must have id extra")
                    table_queries.setdefault(
                        (table_ref.project_id, table_ref.digest), []
                    ).append((i, row_digest))
            # Make the queries
            for (project_id, digest), index_digests in table_queries.items():
                row_digests = [d for i, d in index_digests]
                if project_id != project_id_scope:
                    # At some point in the future, we may allow cross-project references.
                    # However, until then, we disallow this feature. Practically, we
                    # should never hit this code path since the `resolve_extra` function
                    # handles this check. However, out of caution, we add this check here.
                    # Hitting this would be a programming error, not a user error.
                    raise ValueError("Will not resolve cross-project refs.")
                pb = ParamBuilder()
                row_digests_name = pb.add_param(row_digests)
                rows_stream = self._table_query_stream(
                    project_id=project_id_scope,
                    digest=digest,
                    pb=pb,
                    sql_safe_conditions=[
                        f"digest IN {{{row_digests_name}: Array(String)}}"
                    ],
                )
                rows = list(rows_stream)
                # Unpack the results into the target rows
                row_digest_vals = {r.digest: r.val for r in rows}
                for index, row_digest in index_digests:
                    extra_results[index] = PartialRefResult(
                        remaining_extra=extra_results[index].remaining_extra[2:],
                        val=row_digest_vals[row_digest],
                        unresolved_obj_ref=None,
                        unresolved_table_ref=None,
                    )

            # Resolve any remaining extras, possibly producing more unresolved refs
            for i, extra_result in enumerate(extra_results):
                if extra_result.remaining_extra:
                    extra_results[i] = resolve_extra(
                        extra_result.remaining_extra, extra_result.val
                    )

        return [r.val for r in extra_results]

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        digest = bytes_digest(req.content)
        use_file_storage = self._should_use_file_storage_for_writes(req.project_id)
        client = self.file_storage_client

        if client is not None and use_file_storage:
            try:
                self._file_create_bucket(req, digest, client)
            except FileStorageWriteError as e:
                self._file_create_clickhouse(req, digest)
        else:
            self._file_create_clickhouse(req, digest)
        set_root_span_dd_tags({"write_bytes": len(req.content)})
        return tsi.FileCreateRes(digest=digest)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_create_clickhouse")
    def _file_create_clickhouse(self, req: tsi.FileCreateReq, digest: str) -> None:
        set_root_span_dd_tags({"storage_provider": "clickhouse"})
        chunks = [
            req.content[i : i + FILE_CHUNK_SIZE]
            for i in range(0, len(req.content), FILE_CHUNK_SIZE)
        ]
        self._insert(
            "files",
            data=[
                (
                    req.project_id,
                    digest,
                    i,
                    len(chunks),
                    req.name,
                    chunk,
                    len(chunk),
                    None,
                )
                for i, chunk in enumerate(chunks)
            ],
            column_names=[
                "project_id",
                "digest",
                "chunk_index",
                "n_chunks",
                "name",
                "val_bytes",
                "bytes_stored",
                "file_storage_uri",
            ],
        )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_create_bucket")
    def _file_create_bucket(
        self, req: tsi.FileCreateReq, digest: str, client: FileStorageClient
    ) -> None:
        set_root_span_dd_tags({"storage_provider": "bucket"})
        target_file_storage_uri = store_in_bucket(
            client, key_for_project_digest(req.project_id, digest), req.content
        )
        self._insert(
            "files",
            data=[
                (
                    req.project_id,
                    digest,
                    0,
                    1,
                    req.name,
                    b"",
                    len(req.content),
                    target_file_storage_uri.to_uri_str(),
                )
            ],
            column_names=[
                "project_id",
                "digest",
                "chunk_index",
                "n_chunks",
                "name",
                "val_bytes",
                "bytes_stored",
                "file_storage_uri",
            ],
        )

    def _should_use_file_storage_for_writes(self, project_id: str) -> bool:
        """Determine if we should use file storage for a project."""
        # Check if we should use file storage based on the ramp percentage
        ramp_pct = wf_env.wf_file_storage_project_ramp_pct()
        if ramp_pct is not None:
            # If the hash value is less than the ramp percentage, use file storage
            project_hash_value = _string_to_int_in_range(project_id, 100)
            if project_hash_value < ramp_pct:
                return True

        # Check if we should use file storage based on the allow list
        project_allow_list = wf_env.wf_file_storage_project_allow_list()
        if project_allow_list is None:
            return False

        universally_enabled = (
            len(project_allow_list) == 1 and project_allow_list[0] == "*"
        )

        if not universally_enabled and project_id not in project_allow_list:
            return False

        return True

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        # The subquery is responsible for deduplication of file chunks by digest
        query_result = self.ch_client.query(
            """
            SELECT n_chunks, val_bytes, file_storage_uri
            FROM (
                SELECT *
                FROM (
                        SELECT *,
                            row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
                        FROM files
                        WHERE project_id = {project_id:String} AND digest = {digest:String}
                    )
                WHERE rn = 1
                ORDER BY project_id, digest, chunk_index
            )
            WHERE project_id = {project_id:String} AND digest = {digest:String}""",
            parameters={"project_id": req.project_id, "digest": req.digest},
            column_formats={"val_bytes": "bytes"},
        )

        if len(query_result.result_rows) == 0:
            raise NotFoundError(f"File with digest {req.digest} not found")

        n_chunks = query_result.result_rows[0][0]
        result_rows = list(query_result.result_rows)

        if len(result_rows) < n_chunks:
            raise ValueError("Missing chunks")
        elif len(result_rows) > n_chunks:
            # The general case where this can occur is when there are multiple
            # writes of the same digest AND the effective `FILE_CHUNK_SIZE`
            # of the most recent write is more than the effective `FILE_CHUNK_SIZE`
            # of any previous write. In that case, you have something like tthe following:
            # Consider a file of size 500 bytes.
            # Insert Batch 1 (chunk_size=100): C0(0-99), C1(100-199), C2(200-299), C3(300-399), C4(400-499)
            # Insert Batch 2 (chunk_size=50): C0(0-49), C1(50-99), C2(100-149), C3(150-199), C4(200-249), C5(250-299), C6(300-349), C7(350-399), C8(400-449), C9(450-499)
            # Insert Batch 3 (chunk_size=200): C0(0-199), C1(200-399), C2(400-499)
            #
            # When Clickhouse runs it's merge operation, it keeps the last inserted rows according to the index (project, digest, chunk_index).
            # Similarly, the inner select statement in the query above (partitioned and keep row 1) does the same thing.
            #
            # As a result, the resulting query gives you all the chunks from batch 3, then any "extra" chunks from previous batches.
            # |--------- Insert Batch 3 --------| |-------------------------- Extra Chunks from Batch 2 -----------------------------------|
            # C0(0-199), C1(200-399), C2(400-499), C3(150-199), C4(200-249), C5(250-299), C6(300-349), C7(350-399), C8(400-449), C9(450-499)
            #
            #
            # Those "extra" chunks are no long valid, but will be returned by the query. By design, we include the expected number of chunks in the response
            # and since the last insert batch is the valid one, we can truncate the response to the expected number of chunks to isolate the valid chunks.
            #
            #
            # Now, practically, we have never changed the `FILE_CHUNK_SIZE` - nor should we!
            # However, with bucket storage, we don't chunk at all - storing the data effectively as a single chunk.
            # This effectively means that `FILE_CHUNK_SIZE` for these cases is the size of the file!. Therefore,
            # in such cases where a file was written before bucket storage (using chunking) and then after, we will
            # reach a situation that matches the general case above.
            #
            # To solve this, we truncate the response to the expected number of chunks to isolate the valid chunks.
            result_rows = result_rows[:n_chunks]

        # There are 2 cases:
        # 1: file_storage_uri_str is not none (storing in file store)
        # 2: file_storage_uri_str is None (storing directly in clickhouse)
        bytes = b""

        for result_row in result_rows:
            chunk_file_storage_uri_str = result_row[2]
            if chunk_file_storage_uri_str:
                file_storage_uri = FileStorageURI.parse_uri_str(
                    chunk_file_storage_uri_str
                )
                bytes += self._file_read_bucket(file_storage_uri)
            else:
                chunk_bytes = result_row[1]
                bytes += chunk_bytes
                set_root_span_dd_tags({"storage_provider": "clickhouse"})

        set_root_span_dd_tags({"read_bytes": len(bytes)})
        return tsi.FileContentReadRes(content=bytes)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_read_bucket")
    def _file_read_bucket(self, file_storage_uri: FileStorageURI) -> bytes:
        set_root_span_dd_tags({"storage_provider": "bucket"})
        client = self.file_storage_client
        if client is None:
            raise FileStorageReadError("File storage client is not configured")
        return read_from_bucket(client, file_storage_uri)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        pb = ParamBuilder()

        project_id_param = pb.add_param(req.project_id)

        query = f"""
        SELECT sum(size_bytes) as total_size_bytes
        FROM files_stats
        WHERE project_id = {{{project_id_param}: String}}
        """
        result = self.ch_client.query(query, parameters=pb.get_params())

        if len(result.result_rows) == 0 or result.result_rows[0][0] is None:
            raise RuntimeError("No results found")

        return tsi.FilesStatsRes(total_size_bytes=result.result_rows[0][0])

    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        assert_non_null_wb_user_id(req)
        created_at = datetime.datetime.now(ZoneInfo("UTC"))

        costs = []
        for llm_id, cost in req.costs.items():
            cost_id = generate_id()

            row: Row = {
                "id": cost_id,
                "created_by": req.wb_user_id,
                "created_at": created_at,
                "pricing_level": "project",
                "pricing_level_id": req.project_id,
                "provider_id": cost.provider_id if cost.provider_id else "default",
                "llm_id": llm_id,
                "effective_date": (
                    cost.effective_date if cost.effective_date else created_at
                ),
                "prompt_token_cost": cost.prompt_token_cost,
                "completion_token_cost": cost.completion_token_cost,
                "prompt_token_cost_unit": cost.prompt_token_cost_unit,
                "completion_token_cost_unit": cost.completion_token_cost_unit,
            }

            costs.append((cost_id, llm_id))

            prepared = LLM_TOKEN_PRICES_TABLE.insert(row).prepare(
                database_type="clickhouse"
            )
            self._insert(
                LLM_TOKEN_PRICES_TABLE.name, prepared.data, prepared.column_names
            )

        return tsi.CostCreateRes(ids=costs)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        expr = {
            "$and": [
                (
                    req.query.expr_
                    if req.query
                    else {
                        "$eq": [
                            {"$getField": "pricing_level_id"},
                            {"$literal": req.project_id},
                        ],
                    }
                ),
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": "project"},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})
        query = LLM_TOKEN_PRICES_TABLE.select()
        query = query.fields(req.fields)
        query = query.where(query_with_pricing_level)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="clickhouse")
        query_result = self.ch_client.query(prepared.sql, prepared.parameters)
        results = LLM_TOKEN_PRICES_TABLE.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.CostQueryRes(results=results)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        validate_cost_purge_req(req)

        expr = {
            "$and": [
                req.query.expr_,
                {
                    "$eq": [
                        {"$getField": "pricing_level_id"},
                        {"$literal": req.project_id},
                    ],
                },
                {
                    "$eq": [
                        {"$getField": "pricing_level"},
                        {"$literal": "project"},
                    ],
                },
            ]
        }
        query_with_pricing_level = tsi.Query(**{"$expr": expr})

        query = LLM_TOKEN_PRICES_TABLE.purge()
        query = query.where(query_with_pricing_level)
        prepared = query.prepare(database_type="clickhouse")
        self.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.CostPurgeRes()

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        assert_non_null_wb_user_id(req)
        validate_feedback_create_req(req, self)

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
        payload = _dict_value_to_dump(req.payload)
        MAX_PAYLOAD = 1 << 20  # 1 MiB
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
            "annotation_ref": req.annotation_ref,
            "runnable_ref": req.runnable_ref,
            "call_ref": req.call_ref,
            "trigger_ref": req.trigger_ref,
        }
        prepared = TABLE_FEEDBACK.insert(row).prepare(database_type="clickhouse")
        self._insert(TABLE_FEEDBACK.name, prepared.data, prepared.column_names)
        return tsi.FeedbackCreateRes(
            id=feedback_id,
            created_at=created_at,
            wb_user_id=req.wb_user_id,
            payload=res_payload,
        )

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        query = TABLE_FEEDBACK.select()
        query = query.project_id(req.project_id)
        query = query.fields(req.fields)
        query = query.where(req.query)
        query = query.order_by(req.sort_by)
        query = query.limit(req.limit).offset(req.offset)
        prepared = query.prepare(database_type="clickhouse")
        query_result = self.ch_client.query(prepared.sql, prepared.parameters)
        result = TABLE_FEEDBACK.tuples_to_rows(
            query_result.result_rows, prepared.fields
        )
        return tsi.FeedbackQueryRes(result=result)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        # TODO: Instead of passing conditions to DELETE FROM,
        #       should we select matching ids, and then DELETE FROM WHERE id IN (...)?
        #       This would allow us to return the number of rows deleted, and complain
        #       if too many things would be deleted.
        validate_feedback_purge_req(req)
        query = TABLE_FEEDBACK.purge()
        query = query.project_id(req.project_id)
        query = query.where(req.query)
        prepared = query.prepare(database_type="clickhouse")
        self.ch_client.query(prepared.sql, prepared.parameters)
        return tsi.FeedbackPurgeRes()

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        # To replace, first purge, then if successful, create.
        query = tsi.Query(
            **{
                "$expr": {
                    "$eq": [
                        {"$getField": "id"},
                        {"$literal": req.feedback_id},
                    ],
                }
            }
        )
        purge_request = tsi.FeedbackPurgeReq(
            project_id=req.project_id,
            query=query,
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
        if len(req.call_ids) == 0:
            return tsi.ActionsExecuteBatchRes()
        if len(req.call_ids) > 1:
            # This is temporary until we setup our batching infrastructure
            raise NotImplementedError("Batching actions is not yet supported")

        # For now, we just execute in-process if it is a single action
        execute_batch(
            batch_req=req,
            trace_server=self,
        )

        return tsi.ActionsExecuteBatchRes()

    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        # Required fields
        model_name = req.inputs.model
        api_key = None
        provider = None

        # Custom model fields
        base_url: Optional[str] = None
        extra_headers: dict[str, str] = {}
        return_type: Optional[str] = None

        # For custom and standard models, we fetch the fields differently
        #  1. Standard models: All of the information comes from the model_to_provider_info_map
        #  2. Custom models: We fetch the provider object and provider model object

        # First we try to see if the model name is a custom model
        model_info = self._model_to_provider_info_map.get(model_name)

        if model_info:
            # Handle standard model case
            # 1. We get the model info from the map
            # 2. We fetch the API key, with the secret fetcher
            # 3. We set the provider, to the litellm provider
            # 4. If no api key, we raise an error, except for bedrock and bedrock_converse (we fetch bedrock credentials, in lite_llm_completion)

            secret_name = model_info.get("api_key_name")
            if not secret_name:
                raise InvalidRequest(f"No secret name found for model {model_name}")

            secret_fetcher = _secret_fetcher_context.get()
            if not secret_fetcher:
                raise InvalidRequest(
                    f"No secret fetcher found, cannot fetch API key for model {model_name}"
                )

            api_key = (
                secret_fetcher.fetch(secret_name).get("secrets", {}).get(secret_name)
            )
            provider = model_info.get("litellm_provider", "openai")

            # We fetch bedrock credentials, in lite_llm_completion, later
            if not api_key and provider != "bedrock" and provider != "bedrock_converse":
                raise MissingLLMApiKeyError(
                    f"No API key {secret_name} found for model {model_name}",
                    api_key_name=secret_name,
                )

        else:
            # If we don't have model info, we assume it is a custom model
            # Handle custom provider case
            # We fetch the provider object and provider model object
            try:
                custom_provider_info = get_custom_provider_info(
                    project_id=req.project_id,
                    model_name=model_name,
                    obj_read_func=self.obj_read,
                )

                base_url = custom_provider_info.base_url
                api_key = custom_provider_info.api_key
                extra_headers = custom_provider_info.extra_headers
                return_type = custom_provider_info.return_type
                actual_model_name = custom_provider_info.actual_model_name

            except Exception as e:
                return tsi.CompletionsCreateRes(response={"error": str(e)})

            # Always use "custom" as the provider for litellm
            provider = "custom"
            # Update the model name for the API call
            # If the model name is ollama, we need to add the ollama/ prefix
            req.inputs.model = (
                "ollama/" + actual_model_name
                if "ollama" in model_name
                else actual_model_name
            )

        # Now that we have all the fields for both cases, we can make the API call
        start_time = datetime.datetime.now()

        # Make the API call
        res = lite_llm_completion(
            api_key=api_key,
            inputs=req.inputs,
            provider=provider,
            base_url=base_url,
            extra_headers=extra_headers,
            return_type=return_type,
        )

        end_time = datetime.datetime.now()

        if not req.track_llm_call:
            return tsi.CompletionsCreateRes(response=res.response)

        start = tsi.StartedCallSchemaForInsert(
            project_id=req.project_id,
            wb_user_id=req.wb_user_id,
            op_name=COMPLETIONS_CREATE_OP_NAME,
            started_at=start_time,
            inputs={**req.inputs.model_dump(exclude_none=True)},
            attributes={},
        )
        start_call = _start_call_for_insert_to_ch_insertable_start_call(start)
        end = tsi.EndedCallSchemaForInsert(
            project_id=req.project_id,
            id=start_call.id,
            ended_at=end_time,
            output=res.response,
            summary={},
        )
        if "usage" in res.response:
            end.summary["usage"] = {model_name: res.response["usage"]}

        if "error" in res.response:
            end.exception = res.response["error"]
        end_call = _end_call_for_insert_to_ch_insertable_end_call(end)
        calls: list[Union[CallStartCHInsertable, CallEndCHInsertable]] = [
            start_call,
            end_call,
        ]
        batch_data = []
        for call in calls:
            call_dict = call.model_dump()
            values = [call_dict.get(col) for col in all_call_insert_columns]
            batch_data.append(values)

        self._insert_call_batch(batch_data)

        return tsi.CompletionsCreateRes(
            response=res.response, weave_call_id=start_call.id
        )

    # Private Methods
    @property
    def ch_client(self) -> CHClient:
        """Returns and creates (if necessary) the clickhouse client"""
        if not hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client = self._mint_client()
        return self._thread_local.ch_client

    def _mint_client(self) -> CHClient:
        client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            secure=self._port == 8443,
        )
        # Safely create the database if it does not exist
        client.command(f"CREATE DATABASE IF NOT EXISTS {self._database}")
        client.database = self._database
        return client

    @contextmanager
    def with_new_client(self) -> Iterator[None]:
        """Context manager to use a new client for operations.
        Each call gets a fresh client with its own clickhouse session ID.

        Usage:
        ```
        with self.with_new_client():
            self.feedback_query(req)
        ```
        """
        client = self._mint_client()
        original_client = self.ch_client
        self._thread_local.ch_client = client
        try:
            yield
        finally:
            self._thread_local.ch_client = original_client
            client.close()

    # def __del__(self) -> None:
    #     self.ch_client.close()

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert_call_batch")
    def _insert_call_batch(self, batch: list) -> None:
        if root_span := ddtrace.tracer.current_span():
            root_span.set_tags(
                {
                    "clickhouse_trace_server_batched._insert_call_batch.count": str(
                        len(batch)
                    )
                }
            )
        if batch:
            settings = {}
            if self._use_async_insert:
                settings["async_insert"] = 1
                # https://clickhouse.com/docs/en/optimize/asynchronous-inserts#enabling-asynchronous-inserts
                # Setting wait_for_async_insert = 0 does not guarantee that insert errors
                # are caught, reverting to default behavior.
                settings["wait_for_async_insert"] = 1
            self._insert(
                "call_parts",
                data=batch,
                column_names=all_call_insert_columns,
                settings=settings,
            )

    def _select_objs_query(
        self,
        object_query_builder: ObjectMetadataQueryBuilder,
        metadata_only: bool = False,
    ) -> list[SelectableCHObjSchema]:
        """
        Main query for fetching objects.

        conditions:
            conditions should include operations on version_index, digest, kind (is_op)
            ALL conditions are AND'ed together.
        object_id_conditions:
            conditions should include operations on ONLY object_id
            ALL conditions are AND'ed together.
        parameters:
            parameters to be passed to the query. Must include all parameters for both
            conditions and object_id_conditions.
        metadata_only:
            if metadata_only is True, then we return early and dont grab the value.
            Otherwise, make a second query to grab the val_dump from the db
        """
        obj_metadata_query = object_query_builder.make_metadata_query()
        parameters = object_query_builder.parameters or {}
        query_result = self._query_stream(obj_metadata_query, parameters)
        metadata_result = format_metadata_objects_from_query_result(
            query_result, object_query_builder.include_storage_size
        )

        # -- Don't make second query for object values if metadata_only --
        if metadata_only or len(metadata_result) == 0:
            return metadata_result

        value_query, value_parameters = make_objects_val_query_and_parameters(
            project_id=object_query_builder.project_id,
            object_ids=list({row.object_id for row in metadata_result}),
            digests=list({row.digest for row in metadata_result}),
        )
        query_result = self._query_stream(value_query, value_parameters)
        # Map (object_id, digest) to val_dump
        object_values: dict[tuple[str, str], Any] = {}
        for row in query_result:
            (object_id, digest, val_dump) = row
            object_values[(object_id, digest)] = val_dump

        # update the val_dump for each object
        for obj in metadata_result:
            obj.val_dump = object_values.get((obj.object_id, obj.digest), "{}")
        return metadata_result

    def _run_migrations(self) -> None:
        logger.info("Running migrations")
        migrator = wf_migrator.ClickHouseTraceServerMigrator(self._mint_client())
        migrator.apply_migrations(self._database)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._query_stream")
    def _query_stream(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: Optional[dict[str, Any]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> Iterator[tuple]:
        """Streams the results of a query from the database."""
        if not settings:
            settings = {}
        settings.update(CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

        summary = None
        parameters = _process_parameters(parameters)
        try:
            with self.ch_client.query_rows_stream(
                query,
                parameters=parameters,
                column_formats=column_formats,
                use_none=True,
                settings=settings,
            ) as stream:
                if isinstance(stream.source, QueryResult):
                    summary = stream.source.summary
                logger.info(
                    "clickhouse_stream_query",
                    extra={
                        "query": query,
                        "parameters": parameters,
                        "summary": summary,
                    },
                )
                yield from stream
        except Exception as e:
            logger.exception(
                "clickhouse_stream_query_error",
                extra={
                    "error_str": str(e),
                    "query": query,
                    "parameters": parameters,
                },
            )
            raise

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._query")
    def _query(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: Optional[dict[str, Any]] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> QueryResult:
        """Directly queries the database and returns the result."""
        if not settings:
            settings = {}
        settings.update(CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

        parameters = _process_parameters(parameters)
        try:
            res = self.ch_client.query(
                query,
                parameters=parameters,
                column_formats=column_formats,
                use_none=True,
                settings=settings,
            )
        except Exception as e:
            logger.exception(
                "clickhouse_query_error",
                extra={"error_str": str(e), "query": query, "parameters": parameters},
            )
            raise

        logger.info(
            "clickhouse_query",
            extra={
                "query": query,
                "parameters": parameters,
                "summary": res.summary,
            },
        )
        return res

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert")
    def _insert(
        self,
        table: str,
        data: Sequence[Sequence[Any]],
        column_names: list[str],
        settings: Optional[dict[str, Any]] = None,
    ) -> QuerySummary:
        try:
            return self.ch_client.insert(
                table, data=data, column_names=column_names, settings=settings
            )
        except ValueError as e:
            if "negative shift count" in str(e):
                # clickhouse_connect raises a weird error message like
                # File "/Users/shawn/.pyenv/versions/3.10.13/envs/weave-public-editable/lib/python3.10/site-packages/clickhouse_connect/driver/
                # │insert.py", line 120, in _calc_block_size
                # │    return 1 << (21 - int(log(row_size, 2)))
                # │ValueError: negative shift count
                # when we try to insert something that's too large.
                raise InsertTooLarge(
                    "Database insertion failed. Record too large. "
                    "A likely cause is that a single row or cell exceeded "
                    "the limit. If logging images, save them as `Image.PIL`."
                )
            raise
        except Exception as e:
            # Do potentially expensive data length calculation, only on
            # error, which should be very rare!
            data_bytes = sum(_num_bytes(row) for row in data)
            logger.exception(
                "clickhouse_insert_error",
                extra={
                    "error_str": str(e),
                    "table": table,
                    "data_len": len(data),
                    "data_bytes": data_bytes,
                    "example_data": None if len(data) == 0 else data[0],
                    "column_names": column_names,
                    "settings": settings,
                },
            )
            raise

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert_call")
    def _insert_call(self, ch_call: CallCHInsertable) -> None:
        parameters = ch_call.model_dump()
        row = []
        for key in all_call_insert_columns:
            row.append(parameters.get(key, None))
        self._call_batch.append(row)
        if self._flush_immediately:
            self._flush_calls()

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._flush_calls")
    def _flush_calls(self) -> None:
        try:
            self._insert_call_batch(self._call_batch)
        except InsertTooLarge:
            logger.info("Retrying with large objects stripped.")
            batch = self._strip_large_values(self._call_batch)
            self._insert_call_batch(batch)

        self._call_batch = []

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._strip_large_values")
    def _strip_large_values(self, batch: list[list[Any]]) -> list[list[Any]]:
        """
        Iterate through the batch and replace large values with placeholders.

        If values are larger than 1MiB replace them with placeholder values.
        """
        stripped_count = 0
        final_batch = []
        # Set the value byte limit to be anything over 1MiB to catch
        # payloads with multiple large values that are still under the
        # single row insert limit.
        for item in batch:
            bytes_size = _num_bytes(str(item))
            # If bytes_size > the limit, this item is too large,
            # iterate through the json-dumped item values to find and
            # replace the large values with a placeholder.
            if bytes_size > CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT:
                stripped_item = []
                for value in item:
                    # all the values should be json dumps, there are no
                    # non json fields controlled by the user that can
                    # be large enough to strip... (?)
                    if _num_bytes(value) > CLICKHOUSE_SINGLE_VALUE_BYTES_LIMIT:
                        stripped_item += [ENTITY_TOO_LARGE_PAYLOAD]
                        stripped_count += 1
                    else:
                        stripped_item += [value]
                final_batch.append(stripped_item)
            else:
                final_batch.append(item)

        ddtrace.tracer.current_span().set_tags(
            {
                "clickhouse_trace_server_batched._strip_large_values.stripped_count": str(
                    stripped_count
                )
            }
        )
        return final_batch


def _num_bytes(data: Any) -> int:
    """
    Calculate the number of bytes in a string.

    This can be computationally expensive, only call when necessary.
    Never raise on a failed str cast, just return 0.
    """
    try:
        return len(str(data).encode("utf-8"))
    except Exception:
        return 0


def _dict_value_to_dump(
    value: dict,
) -> str:
    if not isinstance(value, dict):
        raise TypeError(f"Value is not a dict: {value}")
    return json.dumps(value)


def _any_value_to_dump(
    value: Any,
) -> str:
    return json.dumps(value)


def _dict_dump_to_dict(val: str) -> dict[str, Any]:
    res = json.loads(val)
    if not isinstance(res, dict):
        raise TypeError(f"Value is not a dict: {val}")
    return res


def _any_dump_to_any(val: str) -> Any:
    return json.loads(val)


def _ensure_datetimes_have_tz(
    dt: Optional[datetime.datetime] = None,
) -> Optional[datetime.datetime]:
    # https://github.com/ClickHouse/clickhouse-connect/issues/210
    # Clickhouse does not support timezone-aware datetimes. You can specify the
    # desired timezone at query time. However according to the issue above,
    # clickhouse will produce a timezone-naive datetime when the preferred
    # timezone is UTC. This is a problem because it does not match the ISO8601
    # standard as datetimes are to be interpreted locally unless specified
    # otherwise. This function ensures that the datetime has a timezone, and if
    # it does not, it adds the UTC timezone to correctly convey that the
    # datetime is in UTC for the caller.
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _ensure_datetimes_have_tz_strict(
    dt: datetime.datetime,
) -> datetime.datetime:
    res = _ensure_datetimes_have_tz(dt)
    if res is None:
        raise ValueError(f"Datetime is None: {dt}")
    return res


def _nullable_any_dump_to_any(
    val: Optional[str],
) -> Optional[Any]:
    return _any_dump_to_any(val) if val else None


def _ch_call_dict_to_call_schema_dict(ch_call_dict: dict) -> dict:
    summary = _nullable_any_dump_to_any(ch_call_dict.get("summary_dump"))
    started_at = _ensure_datetimes_have_tz(ch_call_dict.get("started_at"))
    ended_at = _ensure_datetimes_have_tz(ch_call_dict.get("ended_at"))
    display_name = empty_str_to_none(ch_call_dict.get("display_name"))
    return {
        "project_id": ch_call_dict.get("project_id"),
        "id": ch_call_dict.get("id"),
        "trace_id": ch_call_dict.get("trace_id"),
        "parent_id": ch_call_dict.get("parent_id"),
        "op_name": ch_call_dict.get("op_name"),
        "started_at": started_at,
        "ended_at": ended_at,
        "attributes": _dict_dump_to_dict(ch_call_dict.get("attributes_dump", "{}")),
        "inputs": _dict_dump_to_dict(ch_call_dict.get("inputs_dump", "{}")),
        "output": _nullable_any_dump_to_any(ch_call_dict.get("output_dump")),
        "summary": make_derived_summary_fields(
            summary=summary or {},
            op_name=ch_call_dict.get("op_name", ""),
            started_at=started_at,
            ended_at=ended_at,
            exception=ch_call_dict.get("exception"),
            display_name=display_name,
        ),
        "exception": ch_call_dict.get("exception"),
        "wb_run_id": ch_call_dict.get("wb_run_id"),
        "wb_user_id": ch_call_dict.get("wb_user_id"),
        "display_name": display_name,
        "storage_size_bytes": ch_call_dict.get("storage_size_bytes"),
        "total_storage_size_bytes": ch_call_dict.get("total_storage_size_bytes"),
    }


def _ch_obj_to_obj_schema(ch_obj: SelectableCHObjSchema) -> tsi.ObjSchema:
    return tsi.ObjSchema(
        project_id=ch_obj.project_id,
        object_id=ch_obj.object_id,
        created_at=_ensure_datetimes_have_tz(ch_obj.created_at),
        wb_user_id=ch_obj.wb_user_id,
        version_index=ch_obj.version_index,
        is_latest=ch_obj.is_latest,
        digest=ch_obj.digest,
        kind=ch_obj.kind,
        base_object_class=ch_obj.base_object_class,
        val=json.loads(ch_obj.val_dump),
        size_bytes=ch_obj.size_bytes,
    )


def _ch_table_stats_to_table_stats_schema(
    ch_table_stats_row: Sequence[Any],
) -> tsi.TableStatsRow:
    digest, count, storage_size_bytes = (lambda a, b, c=cast(Any, None): (a, b, c))(
        *ch_table_stats_row
    )

    return tsi.TableStatsRow(
        count=count,
        digest=digest,
        storage_size_bytes=storage_size_bytes,
    )


def _start_call_for_insert_to_ch_insertable_start_call(
    start_call: tsi.StartedCallSchemaForInsert,
) -> CallStartCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()
    return CallStartCHInsertable(
        project_id=start_call.project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        op_name=start_call.op_name,
        started_at=start_call.started_at,
        attributes_dump=_dict_value_to_dump(start_call.attributes),
        inputs_dump=_dict_value_to_dump(start_call.inputs),
        input_refs=extract_refs_from_values(start_call.inputs),
        wb_run_id=start_call.wb_run_id,
        wb_user_id=start_call.wb_user_id,
        display_name=start_call.display_name,
    )


def _end_call_for_insert_to_ch_insertable_end_call(
    end_call: tsi.EndedCallSchemaForInsert,
) -> CallEndCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    return CallEndCHInsertable(
        project_id=end_call.project_id,
        id=end_call.id,
        exception=end_call.exception,
        ended_at=end_call.ended_at,
        summary_dump=_dict_value_to_dump(dict(end_call.summary)),
        output_dump=_any_value_to_dump(end_call.output),
        output_refs=extract_refs_from_values(end_call.output),
    )


def _process_parameters(
    parameters: dict[str, Any],
) -> dict[str, Any]:
    # Special processing for datetimes! For some reason, the clickhouse connect
    # client truncates the datetime to the nearest second, so we need to convert
    # the datetime to a float which is then converted back to a datetime in the
    # clickhouse query
    parameters = parameters.copy()
    for key, value in parameters.items():
        if isinstance(value, datetime.datetime):
            parameters[key] = value.timestamp()
    return parameters


# def _partial_obj_schema_to_ch_obj(
#     partial_obj: tsi.ObjSchemaForInsert,
# ) -> ObjCHInsertable:
#     version_hash = version_hash_for_object(partial_obj)

#     return ObjCHInsertable(
#         id=uuid.uuid4(),
#         project_id=partial_obj.project_id,
#         name=partial_obj.name,
#         type="unknown",
#         refs=[],
#         val=json.dumps(partial_obj.val),
#     )


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


@ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.find_call_descendants")
def find_call_descendants(
    root_ids: list[str],
    all_calls: list[tsi.CallSchema],
) -> list[str]:
    if root_span := ddtrace.tracer.current_span():
        root_span.set_tags(
            {
                "clickhouse_trace_server_batched.find_call_descendants.root_ids_count": str(
                    len(root_ids)
                ),
                "clickhouse_trace_server_batched.find_call_descendants.all_calls_count": str(
                    len(all_calls)
                ),
            }
        )
    # make a map of call_id to children list
    children_map = defaultdict(list)
    for call in all_calls:
        if call.parent_id is not None:
            children_map[call.parent_id].append(call.id)

    # do DFS to get all descendants
    def find_all_descendants(root_ids: list[str]) -> set[str]:
        descendants = set()
        stack = root_ids

        while stack:
            current_id = stack.pop()
            if current_id not in descendants:
                descendants.add(current_id)
                stack += children_map.get(current_id, [])

        return descendants

    # Find descendants for each initial id
    descendants = find_all_descendants(root_ids)

    return list(descendants)


def _string_to_int_in_range(input_string: str, range_max: int) -> int:
    """Convert a string to a deterministic integer within a specified range.

    Args:
        input_string: The string to convert to an integer
        range_max: The maximum allowed value (exclusive)

    Returns:
        int: A deterministic integer value between 0 and range_max
    """
    hash_obj = hashlib.md5(input_string.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    return hash_int % range_max


def set_root_span_dd_tags(tags: dict[str, Union[str, float, int]]) -> None:
    root_span = ddtrace.tracer.current_root_span()
    if root_span is None:
        logger.debug("No root span")
    else:
        root_span.set_tags(tags)
