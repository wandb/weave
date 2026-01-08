# Clickhouse Trace Server

import dataclasses
import datetime
import hashlib
import json
import logging
import threading
from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from re import sub
from typing import Any, cast
from zoneinfo import ZoneInfo

import clickhouse_connect
import ddtrace
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.httputil import get_pool_manager
from clickhouse_connect.driver.query import QueryResult
from clickhouse_connect.driver.summary import QuerySummary
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from weave.trace_server import clickhouse_trace_server_migrator as wf_migrator
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import constants, object_creation_utils
from weave.trace_server import environment as wf_env
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_common as tsc
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.actions_worker.dispatcher import execute_batch
from weave.trace_server.annotation_queues_query_builder import (
    make_queue_add_calls_check_duplicates_query,
    make_queue_add_calls_fetch_calls_query,
    make_queue_create_query,
    make_queue_items_query,
    make_queue_read_query,
    make_queues_query,
    make_queues_stats_query,
)
from weave.trace_server.base64_content_conversion import (
    process_call_req_to_content,
)
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    OrderField,
    QueryBuilderDynamicField,
    QueryBuilderField,
    build_calls_stats_query,
    combine_conditions,
)
from weave.trace_server.clickhouse_schema import (
    ALL_CALL_INSERT_COLUMNS,
    ALL_CALL_JSON_COLUMNS,
    ALL_CALL_SELECT_COLUMNS,
    ALL_FILE_CHUNK_INSERT_COLUMNS,
    ALL_OBJ_INSERT_COLUMNS,
    REQUIRED_CALL_COLUMNS,
    CallCHInsertable,
    CallDeleteCHInsertable,
    CallEndCHInsertable,
    CallStartCHInsertable,
    CallUpdateCHInsertable,
    FileChunkCreateCHInsertable,
    ObjCHInsertable,
    ObjDeleteCHInsertable,
    ObjRefListType,
    SelectableCHObjSchema,
)
from weave.trace_server.constants import (
    COMPLETIONS_CREATE_OP_NAME,
    IMAGE_GENERATION_CREATE_OP_NAME,
)
from weave.trace_server.datadog import (
    set_current_span_dd_tags,
    set_root_span_dd_tags,
)
from weave.trace_server.errors import (
    InsertTooLarge,
    InvalidRequest,
    MissingLLMApiKeyError,
    NotFoundError,
    ObjectDeletedError,
    RequestTooLarge,
    handle_clickhouse_query_error,
)
from weave.trace_server.feedback import (
    TABLE_FEEDBACK,
    format_feedback_to_res,
    format_feedback_to_row,
    process_feedback_payload,
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
from weave.trace_server.image_completion import lite_llm_image_generation
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.feedback_types import RUNNABLE_FEEDBACK_TYPE_PREFIX
from weave.trace_server.kafka import KafkaProducer
from weave.trace_server.llm_completion import (
    _build_choices_array,
    _build_completion_response,
    get_custom_provider_info,
    lite_llm_completion,
    lite_llm_completion_stream,
    resolve_and_apply_prompt,
)
from weave.trace_server.methods.evaluation_status import evaluation_status
from weave.trace_server.model_providers.model_providers import (
    LLMModelProviderInfo,
    read_model_to_provider_info_map,
)
from weave.trace_server.object_class_util import process_incoming_object_val
from weave.trace_server.objects_query_builder import (
    ObjectMetadataQueryBuilder,
    format_metadata_objects_from_query_result,
    make_objects_val_query_and_parameters,
)
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.orm import ParamBuilder, Row
from weave.trace_server.project_query_builder import make_project_stats_query
from weave.trace_server.project_version.project_version import (
    TableRoutingResolver,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context
from weave.trace_server.table_query_builder import (
    ROW_ORDER_COLUMN_NAME,
    TABLE_ROWS_ALIAS,
    VAL_DUMP_COLUMN_NAME,
    make_natural_sort_table_query,
    make_standard_table_query,
    make_table_stats_query_with_storage_size,
)
from weave.trace_server.threads_query_builder import make_threads_query
from weave.trace_server.token_costs import (
    LLM_TOKEN_PRICES_TABLE,
    validate_cost_purge_req,
)
from weave.trace_server.trace_server_common import (
    DynamicBatchProcessor,
    LRUCache,
    determine_call_status,
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
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelArgs,
    EvaluateModelDispatcher,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Create a shared connection pool manager for all ClickHouse connections
# maxsize: Maximum connections per pool (set higher than thread count to avoid blocking)
# num_pools: Number of distinct connection pools (for different hosts/configs)
_CH_POOL_MANAGER = get_pool_manager(maxsize=50, num_pools=2)


class ClickHouseTraceServer(tsi.FullTraceServerInterface):
    def __init__(
        self,
        *,
        host: str,
        port: int = 8123,
        user: str = "default",
        password: str = "",
        database: str = "default",
        use_async_insert: bool = False,
        evaluate_model_dispatcher: EvaluateModelDispatcher | None = None,
    ):
        super().__init__()
        self._thread_local = threading.local()
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._use_async_insert = use_async_insert
        self._model_to_provider_info_map = read_model_to_provider_info_map()
        self._file_storage_client: FileStorageClient | None = None
        self._kafka_producer: KafkaProducer | None = None
        self._evaluate_model_dispatcher = evaluate_model_dispatcher
        self._table_routing_resolver: TableRoutingResolver | None = None

    @property
    def _flush_immediately(self) -> bool:
        return getattr(self._thread_local, "flush_immediately", True)

    @_flush_immediately.setter
    def _flush_immediately(self, value: bool) -> None:
        self._thread_local.flush_immediately = value

    @property
    def _call_batch(self) -> list[list[Any]]:
        if not hasattr(self._thread_local, "call_batch"):
            self._thread_local.call_batch = []
        return self._thread_local.call_batch

    @_call_batch.setter
    def _call_batch(self, value: list[list[Any]]) -> None:
        self._thread_local.call_batch = value

    @property
    def _file_batch(self) -> list[FileChunkCreateCHInsertable]:
        if not hasattr(self._thread_local, "file_batch"):
            self._thread_local.file_batch = []
        return self._thread_local.file_batch

    @_file_batch.setter
    def _file_batch(self, value: list[FileChunkCreateCHInsertable]) -> None:
        self._thread_local.file_batch = value

    @classmethod
    def from_env(
        cls, use_async_insert: bool = False, **kwargs: Any
    ) -> "ClickHouseTraceServer":
        # Explicitly calling `RemoteHTTPTraceServer` constructor here to ensure
        # that type checking is applied to the constructor.
        return ClickHouseTraceServer(
            host=wf_env.wf_clickhouse_host(),
            port=wf_env.wf_clickhouse_port(),
            user=wf_env.wf_clickhouse_user(),
            password=wf_env.wf_clickhouse_pass(),
            database=wf_env.wf_clickhouse_database(),
            use_async_insert=use_async_insert,
            **kwargs,
        )

    @property
    def file_storage_client(self) -> FileStorageClient | None:
        if self._file_storage_client is not None:
            return self._file_storage_client
        self._file_storage_client = maybe_get_storage_client_from_env()
        return self._file_storage_client

    @property
    def kafka_producer(self) -> KafkaProducer:
        if self._kafka_producer is not None:
            return self._kafka_producer
        self._kafka_producer = KafkaProducer.from_env()
        return self._kafka_producer

    @property
    def table_routing_resolver(self) -> TableRoutingResolver:
        if self._table_routing_resolver is not None:
            return self._table_routing_resolver
        self._table_routing_resolver = TableRoutingResolver()
        return self._table_routing_resolver

    @property
    def use_distributed_mode(self) -> bool:
        """Check if ClickHouse is configured to use distributed tables.

        Returns the value from WF_CLICKHOUSE_USE_DISTRIBUTED_TABLES environment variable.

        Returns:
            bool: True if using distributed tables, False otherwise.
        """
        return wf_env.wf_clickhouse_use_distributed_tables()

    @property
    def clickhouse_cluster_name(self) -> str | None:
        """Get the ClickHouse cluster name from environment.

        Returns:
            str | None: The cluster name from WF_CLICKHOUSE_REPLICATED_CLUSTER, or None if not set.
        """
        return wf_env.wf_clickhouse_replicated_cluster()

    def _get_calls_complete_table_name(self) -> str:
        """Get the appropriate table name for calls_complete updates.

        In distributed mode, UPDATE statements must target the local table
        (with LOCAL_TABLE_SUFFIX) instead of the distributed table.

        Returns:
            str: Table name to use for UPDATE statements.
        """
        if self.use_distributed_mode:
            return f"calls_complete{ch_settings.LOCAL_TABLE_SUFFIX}"
        return "calls_complete"

    def _noop_project_version_latency_test(self, project_id: str) -> None:
        # NOOP for testing latency impact of project switcher
        try:
            self.table_routing_resolver.resolve_read_table(project_id, self.ch_client)
        except Exception as e:
            logger.warning(
                f"Error getting project version for project [{project_id}]: {e}"
            )

    def _get_existing_ops_from_spans(
        self, seen_ids: set[str], project_id: str, limit: int | None = None
    ) -> list[tsi.ObjSchema]:
        obj_version_filter = tsi.ObjectVersionFilter(
            object_ids=list(seen_ids),
            latest_only=True,
            is_op=True,
        )

        return self.objs_query(
            tsi.ObjQueryReq(
                project_id=project_id,
                filter=obj_version_filter,
                metadata_only=True,
                limit=limit,
            ),
        ).objs

    def _create_or_get_placeholder_ops_digest(
        self, project_id: str, create: bool
    ) -> str:
        if not create:
            return bytes_digest(
                (object_creation_utils.PLACEHOLDER_OP_SOURCE).encode("utf-8")
            )

        source_code = object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_req = tsi.FileCreateReq(
            project_id=project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        return self.file_create(source_file_req).digest

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.otel_export")
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        assert_non_null_wb_user_id(req)

        if not isinstance(req.traces, ExportTraceServiceRequest):
            raise TypeError(
                "Expected traces as ExportTraceServiceRequest, got {type(req.traces)}"
            )
        calls: list[
            tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]
        ] = []
        rejected_spans = 0
        error_messages: list[str] = []

        for proto_resource_spans in req.traces.resource_spans:
            resource = Resource.from_proto(proto_resource_spans.resource)
            for proto_scope_spans in proto_resource_spans.scope_spans:
                for proto_span in proto_scope_spans.spans:
                    try:
                        span = Span.from_proto(proto_span, resource)
                    except AttributePathConflictError as e:
                        # Record and skip malformed spans so we can partially accept the batch
                        rejected_spans += 1
                        # Use data available on the proto span for context
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
                        continue

                    calls.append(
                        span.to_call(
                            req.project_id,
                            wb_user_id=req.wb_user_id,
                            wb_run_id=req.wb_run_id,
                        )
                    )

        obj_id_idx_map = defaultdict(list)
        for idx, (start_call, _) in enumerate(calls):
            op_name = object_creation_utils.make_safe_name(start_call.op_name)
            obj_id_idx_map[op_name].append(idx)

        existing_objects = self._get_existing_ops_from_spans(
            seen_ids=set(obj_id_idx_map.keys()),
            project_id=req.project_id,
            limit=len(calls),
        )
        # We know that OTel will always use the placeholder source.
        # We can instead just reuse the existing file if we know it is present
        # and create it just once if we are not sure.
        if len(existing_objects) == 0:
            digest = self._create_or_get_placeholder_ops_digest(
                project_id=req.project_id, create=True
            )
        else:
            digest = self._create_or_get_placeholder_ops_digest(
                project_id=req.project_id, create=False
            )

        for obj in existing_objects:
            op_ref_uri = ri.InternalOpRef(
                project_id=req.project_id,
                name=obj.object_id,
                version=obj.digest,
            ).uri()

            # Modify each of the matched start calls in place
            for idx in obj_id_idx_map[obj.object_id]:
                calls[idx][0].op_name = op_ref_uri
            # Remove this ID from the mapping so that once the for loop is done we are left with only new objects
            obj_id_idx_map.pop(obj.object_id)

        obj_creation_batch = []
        for op_obj_id in obj_id_idx_map.keys():
            op_val = object_creation_utils.build_op_val(digest)
            obj_creation_batch.append(
                tsi.ObjSchemaForInsert(
                    project_id=req.project_id,
                    object_id=op_obj_id,
                    val=op_val,
                    wb_user_id=req.wb_user_id,
                )
            )
        res = self.obj_create_batch(obj_creation_batch)

        for result in res:
            if result.object_id is None:
                raise RuntimeError("Otel Export - Expected object_id but got None")

            op_ref_uri = ri.InternalOpRef(
                project_id=req.project_id,
                name=result.object_id,
                version=result.digest,
            ).uri()
            for idx in obj_id_idx_map[result.object_id]:
                calls[idx][0].op_name = op_ref_uri

        # Convert calls to CH insertable format and then to rows for batch insertion
        batch_rows = []
        for start_call, end_call in calls:
            ch_start = _start_call_for_insert_to_ch_insertable_start_call(start_call)
            ch_end = _end_call_for_insert_to_ch_insertable_end_call(end_call)
            batch_rows.append(_ch_call_to_row(ch_start))
            batch_rows.append(_ch_call_to_row(ch_end))

        # Insert directly without async_insert for OTEL calls
        self._insert_call_batch(batch_rows, settings=None, do_sync_insert=True)

        if rejected_spans > 0:
            # Join the first 20 errors and return them delimited by ';'
            joined_errors = "; ".join(error_messages[:20]) + (
                "; ..." if len(error_messages) > 20 else ""
            )
            return tsi.OtelExportRes(
                partial_success=tsi.ExportTracePartialSuccess(
                    rejected_spans=rejected_spans,
                    error_message=joined_errors,
                )
            )
        return tsi.OtelExportRes()

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.kafka_producer.flush")
    def _flush_kafka_producer(self) -> None:
        if wf_env.wf_enable_online_eval():
            self.kafka_producer.flush()

    @contextmanager
    def call_batch(self) -> Iterator[None]:
        # Not thread safe - do not use across threads
        self._flush_immediately = False
        try:
            yield
            self._flush_immediately = True
            self._flush_file_chunks()
            self._flush_calls()
            self._flush_kafka_producer()
        finally:
            self._file_batch = []
            self._call_batch = []
            self._flush_immediately = True

    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        with self.call_batch():
            res = []
            for item in req.batch:
                if item.mode == "start":
                    res.append(self.call_start(item.req))
                elif item.mode == "end":
                    res.append(self.call_end(item.req, flush_immediately=False))
                else:
                    raise ValueError("Invalid mode")
        return tsi.CallCreateBatchRes(res=res)

    # Creates a new call
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults

        req = process_call_req_to_content(req, self)
        ch_call = _start_call_for_insert_to_ch_insertable_start_call(req.start)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        # Returns the id of the newly created call
        return tsi.CallStartRes(
            id=ch_call.id,
            trace_id=ch_call.trace_id,
        )

    def call_end(
        self,
        req: tsi.CallEndReq,
        publish: bool = True,
        flush_immediately: bool = False,
    ) -> tsi.CallEndRes:
        # Converts the user-provided call details into a clickhouse schema.
        # This does validation and conversion of the input data as well
        # as enforcing business rules and defaults
        req = process_call_req_to_content(req, self)
        ch_call = _end_call_for_insert_to_ch_insertable_end_call(req.end)

        # Inserts the call into the clickhouse database, verifying that
        # the call does not already exist
        self._insert_call(ch_call)

        if wf_env.wf_enable_online_eval() and publish:
            # Strip large and optional fields, dont modify param
            end_copy = req.end.model_copy()
            end_copy.output = None
            end_copy.summary = {}
            end_copy.exception = None
            # Don't flush immediately by default, rely on explicit flush
            self.kafka_producer.produce_call_end(end_copy, flush_immediately)

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
            call = next(res)
        except StopIteration:
            call = None
        return tsi.CallReadRes(call=call)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        stream = self.calls_query_stream(req)
        return tsi.CallsQueryRes(calls=list(stream))

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.calls_query_stats")
    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Returns a stats object for the given query. This is useful for counts or other
        aggregate statistics that are not directly queryable from the calls themselves.
        """
        self._noop_project_version_latency_test(req.project_id)

        pb = ParamBuilder()
        query, columns = build_calls_stats_query(req, pb)
        raw_res = self._query(query, pb.get_params())

        res_dict = (
            dict(zip(columns, raw_res.result_rows[0], strict=False))
            if raw_res.result_rows
            else {}
        )

        return tsi.CallsQueryStatsRes(
            count=res_dict.get("count", 0),
            total_storage_size_bytes=res_dict.get("total_storage_size_bytes"),
        )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.calls_query_stream")
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Returns a stream of calls that match the given query."""
        self._noop_project_version_latency_test(project_id=req.project_id)

        cq = CallsQuery(
            project_id=req.project_id,
            include_costs=req.include_costs or False,
            include_storage_size=req.include_storage_size or False,
            include_total_storage_size=req.include_total_storage_size or False,
        )
        columns = ALL_CALL_SELECT_COLUMNS
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
            columns = list(set(REQUIRED_CALL_COLUMNS + columns))

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

        if req.expand_columns is not None:
            cq.set_expand_columns(req.expand_columns)
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
            # If user isn't already sorting by id, add id as secondary sort for consistency
            if not any(sort_by.field == "id" for sort_by in req.sort_by):
                cq.add_order("id", "asc")
        else:
            # Default sorting: started_at with id as secondary sort for consistency
            cq.add_order("started_at", "asc")
            cq.add_order("id", "asc")
        if req.limit is not None:
            cq.set_limit(req.limit)
        if req.offset is not None:
            cq.set_offset(req.offset)

        pb = ParamBuilder()
        raw_res = self._query_stream(cq.as_sql(pb), pb.get_params())

        select_columns = [c.field for c in cq.select_fields]
        expand_columns = req.expand_columns or []
        include_feedback = req.include_feedback or False

        def row_to_call_schema_dict(row: tuple[Any, ...]) -> dict[str, Any]:
            return _ch_call_dict_to_call_schema_dict(
                dict(zip(select_columns, row, strict=False))
            )

        if not expand_columns and not include_feedback:
            for row in raw_res:
                yield tsi.CallSchema.model_validate(row_to_call_schema_dict(row))
            return

        ref_cache = LRUCache(max_size=1000)
        batch_processor = DynamicBatchProcessor(
            initial_size=ch_settings.INITIAL_CALLS_STREAM_BATCH_SIZE,
            max_size=ch_settings.MAX_CALLS_STREAM_BATCH_SIZE,
            growth_factor=10,
        )

        for batch in batch_processor.make_batches(raw_res):
            call_dicts = [row_to_call_schema_dict(row) for row in batch]
            if expand_columns and req.return_expanded_column_values:
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

                refs_to_resolve[i, col] = ref
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
                for ref, val in zip(unique_ref_map.values(), vals, strict=False):
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
        if len(req.call_ids) > ch_settings.MAX_DELETE_CALLS_COUNT:
            raise RequestTooLarge(
                f"Cannot delete more than {ch_settings.MAX_DELETE_CALLS_COUNT} calls at once"
            )

        set_current_span_dd_tags(
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

        return tsi.CallsDeleteRes(num_deleted=len(all_descendants))

    def _ensure_valid_update_field(self, req: tsi.CallUpdateReq) -> None:
        valid_update_fields = ["display_name"]
        for field in valid_update_fields:
            if getattr(req, field, None) is not None:
                return

        raise ValueError(
            f"One of [{', '.join(valid_update_fields)}] is required for call update"
        )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.call_update")
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

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.obj_create")
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
            leaf_object_class=processed_result["leaf_object_class"],
            refs=extract_refs_from_values(processed_val),
            val_dump=json_val,
            digest=digest,
        )

        self._insert(
            "object_versions",
            data=[list(ch_obj.model_dump().values())],
            column_names=list(ch_obj.model_fields.keys()),
        )

        return tsi.ObjCreateRes(
            digest=digest,
            object_id=req.obj.object_id,
        )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.create_obj_batch")
    def obj_create_batch(
        self, batch: list[tsi.ObjSchemaForInsert]
    ) -> list[tsi.ObjCreateRes]:
        """This method is for the special case where all objects are known to use a placeholder.
        We lose any knowledge of what version the created object is in return for an enormous
        performance increase for operations like OTel ingest.

        This should **ONLY** be used when we know an object will never have more than one version.
        """
        set_current_span_dd_tags(
            {"clickhouse_trace_server_batched.create_obj_batch.count": str(len(batch))}
        )

        if not batch:
            return []

        obj_results = []
        ch_insert_batch = []

        unique_projects = {obj.project_id for obj in batch}
        if len(unique_projects) > 1:
            raise InvalidRequest(
                f"obj_create_batch only supports updating a single project. Supplied projects: {unique_projects}"
            )

        for obj in batch:
            processed_result = process_incoming_object_val(
                obj.val, obj.builtin_object_class
            )
            processed_val = processed_result["val"]
            json_val = json.dumps(processed_val)
            digest = str_digest(json_val)
            ch_obj = ObjCHInsertable(
                project_id=obj.project_id,
                object_id=obj.object_id,
                wb_user_id=obj.wb_user_id,
                kind=get_kind(processed_val),
                base_object_class=processed_result["base_object_class"],
                leaf_object_class=processed_result["leaf_object_class"],
                refs=extract_refs_from_values(processed_val),
                val_dump=json_val,
                digest=digest,
            )
            insert_data = list(ch_obj.model_dump().values())
            # Add the data to be inserted
            ch_insert_batch.append(insert_data)

            # Record the inserted data
            obj_results.append(
                tsi.ObjCreateRes(
                    digest=digest,
                    object_id=obj.object_id,
                )
            )

        self._insert(
            "object_versions",
            data=ch_insert_batch,
            column_names=ALL_OBJ_INSERT_COLUMNS,
        )

        return obj_results

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
            if req.filter.exclude_base_object_classes:
                object_query_builder.add_exclude_base_object_classes_condition(
                    req.filter.exclude_base_object_classes
                )
            if req.filter.leaf_object_classes:
                object_query_builder.add_leaf_object_classes_condition(
                    req.filter.leaf_object_classes
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
        """Delete object versions by digest, belonging to given object_id.
        All deletion in this method is "soft". Deletion occurs by inserting
        a new row into the object_versions table with the deleted_at field set.
        Inserted rows share identical primary keys (order by) with original rows,
        and will be combined by the ReplacingMergeTree engine at database merge
        time.
        If no digests are provided all versions will have their data overwritten with
        an empty val_dump.
        """
        max_objects_to_delete = 100
        if req.digests and len(req.digests) > max_objects_to_delete:
            raise ValueError(
                f"Object delete request contains {len(req.digests)} objects. Please delete {max_objects_to_delete} or fewer objects at a time."
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
                    leaf_object_class=obj.leaf_object_class,
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

    def table_create_from_digests(
        self, req: tsi.TableCreateFromDigestsReq
    ) -> tsi.TableCreateFromDigestsRes:
        """Create a table by specifying row digests, instead actual rows."""
        # Calculate table digest from row digests
        table_hasher = hashlib.sha256()
        for row_digest in req.row_digests:
            table_hasher.update(row_digest.encode())
        digest = table_hasher.hexdigest()

        # Insert into tables table
        self._insert(
            "tables",
            data=[(req.project_id, digest, req.row_digests)],
            column_names=["project_id", "digest", "row_digests"],
        )

        return tsi.TableCreateFromDigestsRes(digest=digest)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        rows = list(self.table_query_stream(req))
        return tsi.TableQueryRes(rows=rows)

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        conds = []
        pb = ParamBuilder()
        if req.filter and req.filter.row_digests:
            conds.append(
                f"tr.digest IN {{{pb.add_param(req.filter.row_digests)}: Array(String)}}"
            )

        sort_fields = []
        if req.sort_by:
            for sort in req.sort_by:
                # Validate sort field to prevent empty JSON paths
                if not sort.field or not sort.field.strip():
                    raise InvalidRequest("Sort field cannot be empty")

                # Check for invalid dot patterns that would create malformed JSON paths
                if (
                    sort.field.startswith(".")
                    or sort.field.endswith(".")
                    or ".." in sort.field
                ):
                    raise InvalidRequest(
                        f"Invalid sort field '{sort.field}': field names cannot start/end with dots or contain consecutive dots"
                    )

                # TODO: better splitting of escaped dots (.) in field names
                extra_path = sort.field.split(".")

                # Additional validation: ensure no empty path components
                if any(not component.strip() for component in extra_path):
                    raise InvalidRequest(
                        f"Invalid sort field '{sort.field}': field path components cannot be empty"
                    )

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
        # that these strings should have been sanitized by the caller.
        sql_safe_conditions: list[str] | None = None,
        sort_fields: list[OrderField] | None = None,
        limit: int | None = None,
        offset: int | None = None,
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

        # Business logic to ensure that we don't have raw CallRefs (not allowed)
        if any(isinstance(r, ri.InternalCallRef) for r in parsed_raw_refs):
            raise ValueError(
                "Call refs not supported in batch read, use calls_query_stream"
            )

        parsed_refs = cast(ObjRefListType, parsed_raw_refs)
        vals = self._parsed_refs_read_batch(parsed_refs)

        return tsi.RefsReadBatchRes(vals=vals)

    def project_stats(self, req: tsi.ProjectStatsReq) -> tsi.ProjectStatsRes:
        self._noop_project_version_latency_test(req.project_id)

        def _default_true(val: bool | None) -> bool:
            return True if val is None else val

        pb = ParamBuilder()
        query, columns = make_project_stats_query(
            req.project_id,
            pb,
            include_trace_storage_size=_default_true(req.include_trace_storage_size),
            include_objects_storage_size=_default_true(req.include_object_storage_size),
            include_tables_storage_size=_default_true(req.include_table_storage_size),
            include_files_storage_size=_default_true(req.include_file_storage_size),
        )
        query_result = self.ch_client.query(query, parameters=pb.get_params())

        if len(query_result.result_rows) != 1:
            raise RuntimeError("Unexpected number of results", query_result)

        return tsi.ProjectStatsRes(
            **dict(zip(columns, query_result.result_rows[0], strict=False))
        )

    def threads_query_stream(
        self, req: tsi.ThreadsQueryReq
    ) -> Iterator[tsi.ThreadSchema]:
        """Stream threads with aggregated statistics sorted by last activity."""
        self._noop_project_version_latency_test(req.project_id)

        pb = ParamBuilder()

        # Extract filter values
        after_datetime = None
        before_datetime = None
        thread_ids = None
        if req.filter is not None:
            after_datetime = req.filter.after_datetime
            before_datetime = req.filter.before_datetime
            thread_ids = req.filter.thread_ids

        # Use the dedicated query builder
        query = make_threads_query(
            project_id=req.project_id,
            pb=pb,
            limit=req.limit,
            offset=req.offset,
            sort_by=req.sort_by,
            sortable_datetime_after=after_datetime,
            sortable_datetime_before=before_datetime,
            thread_ids=thread_ids,
        )

        # Stream the results using _query_stream
        raw_res = self._query_stream(query, pb.get_params())

        for row in raw_res:
            (
                thread_id,
                turn_count,
                start_time,
                last_updated,
                first_turn_id,
                last_turn_id,
                p50_turn_duration_ms,
                p99_turn_duration_ms,
            ) = row

            # Ensure datetimes have timezone info
            start_time_with_tz = _ensure_datetimes_have_tz(start_time)
            last_updated_with_tz = _ensure_datetimes_have_tz(last_updated)

            if start_time_with_tz is None or last_updated_with_tz is None:
                # Skip threads without valid timestamps
                continue

            yield tsi.ThreadSchema(
                thread_id=thread_id,
                turn_count=turn_count,
                start_time=start_time_with_tz,
                last_updated=last_updated_with_tz,
                first_turn_id=first_turn_id,
                last_turn_id=last_turn_id,
                p50_turn_duration_ms=p50_turn_duration_ms,
                p99_turn_duration_ms=p99_turn_duration_ms,
            )

    # Annotation Queue API
    def annotation_queue_create(
        self, req: tsi.AnnotationQueueCreateReq
    ) -> tsi.AnnotationQueueCreateRes:
        """Create a new annotation queue."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        # Generate UUIDv7 for the queue
        queue_id = generate_id()

        # Get wb_user_id from request (should be set by auth layer)
        created_by = req.wb_user_id
        assert created_by is not None  # Ensured by assert_non_null_wb_user_id

        # Build and execute INSERT query
        query = make_queue_create_query(
            project_id=req.project_id,
            queue_id=queue_id,
            name=req.name,
            description=req.description,
            scorer_refs=req.scorer_refs,
            created_by=created_by,
            pb=pb,
        )

        self.ch_client.command(query, parameters=pb.get_params())

        return tsi.AnnotationQueueCreateRes(id=queue_id)

    def annotation_queues_query_stream(
        self, req: tsi.AnnotationQueuesQueryReq
    ) -> Iterator[tsi.AnnotationQueueSchema]:
        """Stream annotation queues for a project."""
        pb = ParamBuilder()

        query = make_queues_query(
            project_id=req.project_id,
            pb=pb,
            name=req.name,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
        )

        # Stream the results using _query_stream
        raw_res = self._query_stream(query, pb.get_params())

        for row in raw_res:
            (
                queue_id,
                project_id,
                name,
                description,
                scorer_refs,
                created_at,
                created_by,
                updated_at,
                deleted_at,
            ) = row

            # Ensure datetimes have timezone info
            created_at_with_tz = _ensure_datetimes_have_tz(created_at)
            updated_at_with_tz = _ensure_datetimes_have_tz(updated_at)
            deleted_at_with_tz = _ensure_datetimes_have_tz(deleted_at)

            if created_at_with_tz is None or updated_at_with_tz is None:
                # Skip queues without valid timestamps
                continue

            yield tsi.AnnotationQueueSchema(
                id=str(queue_id),  # Convert UUID to string
                project_id=project_id,
                name=name,
                description=description,
                scorer_refs=scorer_refs,
                created_at=created_at_with_tz,
                created_by=created_by,
                updated_at=updated_at_with_tz,
                deleted_at=deleted_at_with_tz,
            )

    def annotation_queue_read(
        self, req: tsi.AnnotationQueueReadReq
    ) -> tsi.AnnotationQueueReadRes:
        """Read a specific annotation queue."""
        pb = ParamBuilder()

        query = make_queue_read_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
        )

        result = self.ch_client.query(query, parameters=pb.get_params())
        rows = result.named_results()

        if not rows:
            raise NotFoundError(f"Queue {req.queue_id} not found")

        row = next(rows)
        queue = tsi.AnnotationQueueSchema(
            id=str(row["id"]),
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            scorer_refs=row["scorer_refs"],
            created_at=_ensure_datetimes_have_tz(row["created_at"]),
            created_by=row["created_by"],
            updated_at=_ensure_datetimes_have_tz(row["updated_at"]),
            deleted_at=_ensure_datetimes_have_tz(row["deleted_at"]),
        )

        return tsi.AnnotationQueueReadRes(queue=queue)

    def annotation_queue_add_calls(
        self, req: tsi.AnnotationQueueAddCallsReq
    ) -> tsi.AnnotationQueueAddCallsRes:
        """Add calls to an annotation queue in batch with duplicate prevention."""
        assert_non_null_wb_user_id(req)
        pb = ParamBuilder()

        # Step 1: Check for existing calls (duplicate prevention)
        dup_query = make_queue_add_calls_check_duplicates_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            call_ids=req.call_ids,
            pb=pb,
        )

        dup_result = self.ch_client.query(dup_query, parameters=pb.get_params())
        existing_call_ids = {row[0] for row in dup_result.result_rows}
        new_call_ids = [cid for cid in req.call_ids if cid not in existing_call_ids]

        if not new_call_ids:
            return tsi.AnnotationQueueAddCallsRes(
                added_count=0, duplicates=len(req.call_ids)
            )

        # Step 2: Fetch call details for caching
        pb2 = ParamBuilder()
        calls_query = make_queue_add_calls_fetch_calls_query(
            project_id=req.project_id,
            call_ids=new_call_ids,
            pb=pb2,
        )

        calls_result = self.ch_client.query(calls_query, parameters=pb2.get_params())
        calls_data = list(calls_result.named_results())

        if not calls_data:
            # No calls found in database
            return tsi.AnnotationQueueAddCallsRes(
                added_count=0, duplicates=len(existing_call_ids)
            )

        # Step 3: Create queue items
        queue_items_rows = []
        added_by = req.wb_user_id

        for call in calls_data:
            queue_item_id = generate_id()

            # Queue item row (must be tuple in column order)
            queue_items_rows.append(
                (
                    queue_item_id,
                    req.project_id,
                    req.queue_id,
                    call["id"],
                    call["started_at"],
                    call["ended_at"],
                    call["op_name"] or "",
                    call["trace_id"] or "",
                    req.display_fields,
                    added_by,
                    added_by,
                )
            )

        # Step 4: Batch insert queue items
        self.ch_client.insert(
            "annotation_queue_items",
            queue_items_rows,
            column_names=[
                "id",
                "project_id",
                "queue_id",
                "call_id",
                "call_started_at",
                "call_ended_at",
                "call_op_name",
                "call_trace_id",
                "display_fields",
                "added_by",
                "created_by",
            ],
        )

        return tsi.AnnotationQueueAddCallsRes(
            added_count=len(calls_data), duplicates=len(existing_call_ids)
        )

    def annotation_queue_items_query(
        self, req: tsi.AnnotationQueueItemsQueryReq
    ) -> tsi.AnnotationQueueItemsQueryRes:
        """Query items in an annotation queue with pagination, sorting, and filtering."""
        pb = ParamBuilder()

        query = make_queue_items_query(
            project_id=req.project_id,
            queue_id=req.queue_id,
            pb=pb,
            filter=req.filter,
            sort_by=req.sort_by,
            limit=req.limit,
            offset=req.offset,
            include_position=req.include_position,
        )

        result = self.ch_client.query(query, parameters=pb.get_params())

        items = []
        for row in result.named_results():
            items.append(
                tsi.AnnotationQueueItemSchema(
                    id=row["id"],
                    project_id=row["project_id"],
                    queue_id=row["queue_id"],
                    call_id=row["call_id"],
                    call_started_at=row["call_started_at"],
                    call_ended_at=row["call_ended_at"],
                    call_op_name=row["call_op_name"],
                    call_trace_id=row["call_trace_id"],
                    display_fields=row["display_fields"],
                    added_by=row["added_by"],
                    annotation_state=row["annotation_state"],
                    created_at=row["created_at"],
                    created_by=row["created_by"],
                    updated_at=row["updated_at"],
                    deleted_at=row["deleted_at"],
                    position_in_queue=row.get("position_in_queue"),
                )
            )

        return tsi.AnnotationQueueItemsQueryRes(items=items)

    def annotation_queues_stats(
        self, req: tsi.AnnotationQueuesStatsReq
    ) -> tsi.AnnotationQueuesStatsRes:
        """Get stats for multiple annotation queues."""
        if not req.queue_ids:
            # Return empty stats if no queue IDs provided
            return tsi.AnnotationQueuesStatsRes(stats=[])

        pb = ParamBuilder()

        query = make_queues_stats_query(
            project_id=req.project_id,
            queue_ids=req.queue_ids,
            pb=pb,
        )

        result = self.ch_client.query(query, parameters=pb.get_params())

        stats = []
        for row in result.result_rows:
            # Row order: queue_id, total_items, completed_items
            queue_id, total_items, completed_items = row
            stats.append(
                tsi.AnnotationQueueStatsSchema(
                    queue_id=str(queue_id),
                    total_items=int(total_items),
                    completed_items=int(completed_items),
                )
            )

        return tsi.AnnotationQueuesStatsRes(stats=stats)

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create an op object by delegating to obj_create.

        Args:
            req: OpCreateReq containing project_id, name, description, and source_code

        Returns:
            OpCreateRes with digest, object_id, version_index, and op_ref
        """
        # Create the obj.py file that the SDK would have created
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        source_file_req = tsi.FileCreateReq(
            project_id=req.project_id,
            name=object_creation_utils.OP_SOURCE_FILE_NAME,
            content=source_code.encode("utf-8"),
        )
        source_file_res = self.file_create(source_file_req)

        # Create the op "val" that the SDK would have created
        # Note: We store just the digest string, matching SDK's to_json output
        op_val = object_creation_utils.build_op_val(source_file_res.digest)
        object_id = object_creation_utils.make_object_id(req.name, "Op")
        obj_req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=req.project_id,
                object_id=object_id,
                val=op_val,
                wb_user_id=None,
            )
        )
        obj_result = self.obj_create(obj_req)

        # Query the object back to get its version index (this may not be
        # immediately available, so we retry a few times)
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        return tsi.OpCreateRes(
            digest=obj_result.digest,
            object_id=object_id,
            version_index=obj_read_res.obj.version_index,
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Get a specific op object by delegating to obj_read with op filtering.

        Returns the actual source code of the op.
        """
        # Query for the ops
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_is_op_condition(True)
        object_query_builder.add_object_ids_condition([req.object_id])
        object_query_builder.add_digests_conditions(req.digest)
        object_query_builder.set_include_deleted(include_deleted=True)
        objs = self._select_objs_query(object_query_builder)
        if len(objs) == 0:
            raise NotFoundError(f"Op {req.object_id}:{req.digest} not found")

        # There should not be multiple ops returned, but in case there are, just
        # return the first one.
        obj = objs[0]
        if obj.deleted_at is not None:
            raise ObjectDeletedError(
                f"Op {req.object_id}:v{obj.version_index} was deleted at {obj.deleted_at}",
                deleted_at=obj.deleted_at,
            )

        # For ops, the object_id is the function name since ops don't have
        # a "name" field in their val object. Ops are stored as CustomWeaveType
        # objects with files containing source code.
        code = ""

        val = json.loads(obj.val_dump)

        # Check if this is a file-based op
        if not isinstance(val, dict):
            raise TypeError(f"Op {req.object_id}:{req.digest} has invalid val: {val}")

        if val.get("_type") != "CustomWeaveType":
            raise TypeError(f"Op {req.object_id}:{req.digest} has invalid val: {val}")

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
            object_id=obj.object_id,
            digest=obj.digest,
            version_index=obj.version_index,
            created_at=_ensure_datetimes_have_tz(obj.created_at),
            code=code,
        )

    def op_list(self, req: tsi.OpListReq) -> Iterator[tsi.OpReadRes]:
        """List op objects in a project by delegating to objs_query with op filtering."""
        # Query the objects
        op_filter = tsi.ObjectVersionFilter(is_op=True)

        complex_query = req.limit is not None or req.offset is not None
        if complex_query:
            object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
            object_query_builder.add_is_op_condition(True)
            object_query_builder.set_include_deleted(include_deleted=False)

            if req.limit is not None:
                object_query_builder.set_limit(req.limit)
            if req.offset is not None:
                object_query_builder.set_offset(req.offset)

            # Sort by latest first (most recent version first)
            object_query_builder.add_order("object_id", "asc")
            object_query_builder.add_order("version_index", "desc")

            objs = self._select_objs_query(object_query_builder, metadata_only=False)
        else:
            # Use objs_query for simpler cases without custom sorting
            obj_query_req = tsi.ObjQueryReq(
                project_id=req.project_id,
                filter=op_filter,
                metadata_only=False,
            )
            obj_res = self.objs_query(obj_query_req)
            objs = obj_res.objs

        # Yield back a descriptive metadata object for each op
        for obj in objs:
            code = ""

            # Extract file reference from the val if it's a file-based op

            try:
                if complex_query:
                    val = json.loads(obj.val_dump)
                else:
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
                created_at=_ensure_datetimes_have_tz(obj.created_at),
                code=code,
            )

    def op_delete(self, req: tsi.OpDeleteReq) -> tsi.OpDeleteRes:
        """Delete op object versions by delegating to obj_delete with op filtering."""
        # First verify that the objects are indeed ops by querying them
        object_query_builder = ObjectMetadataQueryBuilder(req.project_id)
        object_query_builder.add_is_op_condition(True)
        object_query_builder.add_object_ids_condition([req.object_id])
        metadata_only = True
        if req.digests:
            object_query_builder.add_digests_conditions(*req.digests)
            metadata_only = False

        object_versions = self._select_objs_query(object_query_builder, metadata_only)

        # If no op objects found, raise NotFoundError
        if len(object_versions) == 0:
            raise NotFoundError(
                f"Op object {req.object_id} ({req.digests}) not found when deleting."
            )

        # Verify we found all requested digests if they were specified
        if req.digests:
            given_digests = set(req.digests)
            found_digests = {obj.digest for obj in object_versions}
            if len(given_digests) != len(found_digests):
                raise NotFoundError(
                    f"Delete request contains {len(req.digests)} digests, but found {len(found_digests)} objects to delete. Diff digests: {given_digests - found_digests}"
                )

        # Now delegate to obj_delete to perform the actual deletion
        obj_delete_req = tsi.ObjDeleteReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digests=req.digests,
        )

        obj_delete_res = self.obj_delete(obj_delete_req)

        return tsi.OpDeleteRes(num_deleted=obj_delete_res.num_deleted)

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

        # Query the object back to get its version index (this may not be
        # immediately available, so we retry a few times)
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=dataset_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        return tsi.DatasetCreateRes(
            digest=obj_result.digest,
            object_id=dataset_id,
            version_index=obj_read_res.obj.version_index,
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        """Get a dataset object by delegating to obj_read with retry logic.

        Returns the rows reference as a string.
        """
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
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
                logger.warning(
                    f"Skipping dataset object {obj.object_id} with digest {obj.digest}: missing or empty val"
                )
                continue

            val = obj.val
            if not isinstance(val, dict):
                logger.warning(
                    f"Skipping dataset object {obj.object_id} with digest {obj.digest}: val is not a dict"
                )
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
        # Create a safe ID for the scorer
        scorer_id = object_creation_utils.make_object_id(req.name, "Scorer")

        # Create the score op
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

        # Create the scorer object
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

        # Query the object back to get its version index (this may not be
        # immediately available, so we retry a few times)
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=scorer_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        # Get the ref and return the create result
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
        """Get a scorer object by delegating to obj_read with retry logic."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name")
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
        # Query the objects
        scorer_filter = tsi.ObjectVersionFilter(
            base_object_classes=["Scorer"], is_op=False
        )
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=scorer_filter,
            limit=req.limit,
            offset=req.offset,
        )
        obj_res = self.objs_query(obj_query_req)

        # Yield back the full ScorerReadRes for each scorer
        for obj in obj_res.objs:
            name = None
            description = None
            score_op = ""

            if hasattr(obj, "val") and obj.val:
                val = obj.val
                if isinstance(val, dict):
                    name = val.get("name")
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
        # Create a safe ID for the evaluation
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

        # Create the evaluation object
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

        # Query the object back to get its version index (this may not be
        # immediately available, so we retry a few times)
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=evaluation_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

        # Get the ref and return the create result
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
        """Get an evaluation object by delegating to obj_read with retry logic."""
        obj_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=req.object_id,
            digest=req.digest,
        )
        result = self._obj_read_with_retry(obj_req)
        val = result.obj.val

        # Extract name and description from val data
        name = val.get("name")
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
        """List evaluation objects by delegating to objs_query with Evaluation filtering."""
        # Query the objects
        obj_query_req = tsi.ObjQueryReq(
            project_id=req.project_id,
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["Evaluation"], is_op=False
            ),
            limit=req.limit,
            offset=req.offset,
        )
        result = self.objs_query(obj_query_req)

        # Yield back a descriptive metadata object for each evaluation
        for obj in result.objs:
            val = obj.val if hasattr(obj, "val") and obj.val else {}

            name = val.get("name") if isinstance(val, dict) else None
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
                evaluation_name=(
                    val.get("evaluation_name") if isinstance(val, dict) else None
                ),
                evaluate_op=val.get("evaluate", "") if isinstance(val, dict) else "",
                predict_and_score_op=(
                    val.get("predict_and_score", "") if isinstance(val, dict) else ""
                ),
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

        # Query back to get version_index with retry
        obj_read_req = tsi.ObjReadReq(
            project_id=req.project_id,
            object_id=object_id,
            digest=obj_result.digest,
        )
        obj_read_res = self._obj_read_with_retry(obj_read_req)

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

        # Create the evaluation run op
        op_create_req = tsi.OpCreateReq(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            source_code=object_creation_utils.PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE,
        )
        op_create_res = self.op_create(op_create_req)

        # Build the op ref
        op_ref = ri.InternalOpRef(
            project_id=req.project_id,
            name=constants.EVALUATION_RUN_OP_NAME,
            version=op_create_res.digest,
        )

        # Start a call to represent the evaluation run
        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                id=evaluation_run_id,
                trace_id=evaluation_run_id,
                op_name=op_ref.uri(),
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
        if (call := call_res.call) is None:
            raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")

        attributes = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
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
                            [
                                tsi_query.LiteralOperation(literal_=eval_ref)
                                for eval_ref in req.filter.evaluations
                            ],
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
                            [
                                tsi_query.LiteralOperation(literal_=model_ref)
                                for model_ref in req.filter.models
                            ],
                        ]
                    )
                )
            if req.filter.evaluation_run_ids:
                conditions.append(
                    tsi_query.InOperation(
                        in_=[
                            tsi_query.GetFieldOperator(get_field_="id"),
                            [
                                tsi_query.LiteralOperation(literal_=run_id)
                                for run_id in req.filter.evaluation_run_ids
                            ],
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
        res = self.calls_delete(calls_delete_req)
        return tsi.EvaluationRunDeleteRes(num_deleted=res.num_deleted)

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
        evaluation_run_call = self.call_read(evaluation_run_read_req).call
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

        # Collect outputs and scores from all predict_and_score calls
        model_outputs = []
        scorer_outputs_by_name: dict[str, list[float]] = {}

        for call in self.calls_query_stream(calls_query_req):
            # Check if this is a predict_and_score call
            if not tsc.op_name_matches(
                call.op_name, constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME
            ):
                continue

            if call.output is None or not isinstance(call.output, dict):
                continue

            # Extract model output
            if (model_output := call.output.get("output")) is not None:
                model_outputs.append(model_output)

            # Extract scores
            scores = call.output.get("scores", {})
            if not isinstance(scores, dict):
                continue

            for scorer_name, score_value in scores.items():
                if scorer_name not in scorer_outputs_by_name:
                    scorer_outputs_by_name[scorer_name] = []
                # Only add numeric scores for mean calculation
                if isinstance(score_value, float):
                    scorer_outputs_by_name[scorer_name].append(float(score_value))

        # Build the evaluation run output with means
        eval_output = {}

        # Add scorer outputs
        for scorer_name, scores in scorer_outputs_by_name.items():
            if scores:
                eval_output[scorer_name] = {"mean": sum(scores) / len(scores)}

        # Add model outputs
        if model_outputs:
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
            eval_run_read_res = self.call_read(evaluation_run_read_req)

            call = eval_run_read_res.call
            if call is None:
                raise NotFoundError(f"Evaluation run {req.evaluation_run_id} not found")
            evaluation_ref = call.inputs.get("self")

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

        call = call_res.call
        if call is None:
            raise NotFoundError(f"Prediction {req.prediction_id} not found")

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
            if parent_res.call and tsc.op_name_matches(
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
                if parent_res.call and tsc.op_name_matches(
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
        res = self.calls_delete(calls_delete_req)
        return tsi.PredictionDeleteRes(num_deleted=res.num_deleted)

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

        # If there is no parent, or the parent is not a predict_and_score call,
        # this is a regular prediction and we can return success
        if not prediction_call or not prediction_call.parent_id:
            return tsi.PredictionFinishRes(success=True)

        parent_id = prediction_call.parent_id

        parent_read_req = tsi.CallReadReq(
            project_id=req.project_id,
            id=parent_id,
        )
        parent_res = self.call_read(parent_read_req)
        parent_call = parent_res.call
        if not parent_call or not tsc.op_name_matches(
            parent_call.op_name,
            constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
        ):
            return tsi.PredictionFinishRes(success=True)

        # == After here, we assume the parent is a predict_and_score call ==

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
            columns=["output", "attributes"],
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
        prediction_call = prediction_res.call
        if prediction_call:
            # The prediction call has inputs structured as {"self": model_ref, "inputs": actual_inputs}
            # We want just the actual_inputs part
            if isinstance(prediction_call.inputs, dict):
                prediction_inputs = prediction_call.inputs.get("inputs", {})
            prediction_output = prediction_call.output

        # Determine trace_id and parent_id based on evaluation_run_id
        if req.evaluation_run_id:
            # If evaluation_run_id is provided, find the prediction's parent (predict_and_score call)
            # and make this score a sibling of the prediction
            trace_id = req.evaluation_run_id

            if prediction_call and prediction_call.parent_id:
                # Use the prediction's parent as this score's parent
                parent_id = prediction_call.parent_id
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
            or (prediction_call.wb_user_id if prediction_call else None)
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
            if parent_res.call and tsc.op_name_matches(
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
                if parent_res.call and tsc.op_name_matches(
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
        res = self.calls_delete(calls_delete_req)
        return tsi.ScoreDeleteRes(num_deleted=res.num_deleted)

    def _obj_read_with_retry(
        self, req: tsi.ObjReadReq, max_retries: int = 10, initial_delay: float = 0.05
    ) -> tsi.ObjReadRes:
        """Read an object with retry logic to handle race conditions.

        After creating an object, ClickHouse may not immediately make it available
        for reading due to eventual consistency. This method retries with exponential
        backoff to handle this race condition.

        Args:
            req: The object read request
            max_retries: Maximum number of retry attempts (default 10)
            initial_delay: Initial delay in seconds (default 0.05, i.e., 50ms)

        Returns:
            ObjReadRes with the object data

        Raises:
            NotFoundError: If the object is not found after all retries
        """

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=initial_delay, max=1.0),
            retry=retry_if_exception_type(NotFoundError),
            reraise=True,
        )
        def _read() -> tsi.ObjReadRes:
            return self.obj_read(req)

        return _read()

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._parsed_refs_read_batch")
    def _parsed_refs_read_batch(
        self,
        parsed_refs: ObjRefListType,
        root_val_cache: dict[str, Any] | None = None,
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
            for ref, result in zip(project_refs, project_results, strict=False):
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
        root_val_cache: dict[str, Any] | None,
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
            parameters: dict[str, str | int] = {}
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
            unresolved_obj_ref: ri.InternalObjectRef | None
            unresolved_table_ref: ri.InternalTableRef | None
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
                for _, extra_result in needed_extra_results:
                    if extra_result.unresolved_obj_ref is None:
                        raise ValueError("Expected unresolved obj ref")
                    refs.append(extra_result.unresolved_obj_ref)
                obj_roots = get_object_refs_root_val(refs)
                for (i, extra_result), obj_root in zip(
                    needed_extra_results, obj_roots, strict=False
                ):
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
                    if row_digest not in row_digest_vals:
                        raise NotFoundError(f"Row digest {row_digest} not found")
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
            except FileStorageWriteError:
                self._file_create_clickhouse(req, digest)
        else:
            self._file_create_clickhouse(req, digest)
        set_root_span_dd_tags({"write_bytes": len(req.content)})
        return tsi.FileCreateRes(digest=digest)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_create_clickhouse")
    def _file_create_clickhouse(self, req: tsi.FileCreateReq, digest: str) -> None:
        set_root_span_dd_tags({"storage_provider": "clickhouse"})
        chunks = [
            req.content[i : i + ch_settings.FILE_CHUNK_SIZE]
            for i in range(0, len(req.content), ch_settings.FILE_CHUNK_SIZE)
        ]
        self._insert_file_chunks(
            [
                FileChunkCreateCHInsertable(
                    project_id=req.project_id,
                    digest=digest,
                    chunk_index=i,
                    n_chunks=len(chunks),
                    name=req.name,
                    val_bytes=chunk,
                    bytes_stored=len(chunk),
                    file_storage_uri=None,
                )
                for i, chunk in enumerate(chunks)
            ]
        )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_create_bucket")
    def _file_create_bucket(
        self, req: tsi.FileCreateReq, digest: str, client: FileStorageClient
    ) -> None:
        set_root_span_dd_tags({"storage_provider": "bucket"})
        target_file_storage_uri = store_in_bucket(
            client, key_for_project_digest(req.project_id, digest), req.content
        )
        self._insert_file_chunks(
            [
                FileChunkCreateCHInsertable(
                    project_id=req.project_id,
                    digest=digest,
                    chunk_index=0,
                    n_chunks=1,
                    name=req.name,
                    val_bytes=b"",
                    bytes_stored=len(req.content),
                    file_storage_uri=target_file_storage_uri.to_uri_str(),
                )
            ]
        )

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._flush_file_chunks")
    def _flush_file_chunks(self) -> None:
        if not self._flush_immediately:
            raise ValueError("File chunks must be flushed immediately")
        self._insert_file_chunks(self._file_batch)
        self._file_batch = []

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert_file_chunks")
    def _insert_file_chunks(
        self, file_chunks: list[FileChunkCreateCHInsertable]
    ) -> None:
        if not self._flush_immediately:
            self._file_batch.extend(file_chunks)
            return

        data = []
        for chunk in file_chunks:
            chunk_dump = chunk.model_dump()
            row = []
            for col in ALL_FILE_CHUNK_INSERT_COLUMNS:
                row.append(chunk_dump.get(col, None))
            data.append(row)

        if data:
            self._insert(
                "files",
                data=data,
                column_names=ALL_FILE_CHUNK_INSERT_COLUMNS,
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
            # of any previous write. In that case, you have something like the following:
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

        processed_payload = process_feedback_payload(req)
        row = format_feedback_to_row(req, processed_payload)
        prepared = TABLE_FEEDBACK.insert(row).prepare(database_type="clickhouse")
        self._insert(
            TABLE_FEEDBACK.name,
            prepared.data,
            prepared.column_names,
            # Always do sync inserts, we want speedy response times for this endpoint
            do_sync_insert=True,
        )

        return format_feedback_to_res(row)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.feedback_create_batch")
    def feedback_create_batch(
        self, req: tsi.FeedbackCreateBatchReq
    ) -> tsi.FeedbackCreateBatchRes:
        """Create multiple feedback items in a batch efficiently."""
        rows_to_insert = []
        results = []

        set_root_span_dd_tags({"feedback_create_batch.count": len(req.batch)})

        for feedback_req in req.batch:
            assert_non_null_wb_user_id(feedback_req)
            validate_feedback_create_req(feedback_req, self)

            processed_payload = process_feedback_payload(feedback_req)
            row = format_feedback_to_row(feedback_req, processed_payload)
            rows_to_insert.append(row)
            results.append(format_feedback_to_res(row))

        # Batch insert all rows at once
        if rows_to_insert:
            insert_query = TABLE_FEEDBACK.insert()
            for row in rows_to_insert:
                insert_query.row(row)
            prepared = insert_query.prepare(database_type="clickhouse")
            self._insert(TABLE_FEEDBACK.name, prepared.data, prepared.column_names)

        return tsi.FeedbackCreateBatchRes(res=results)

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
        # --- Resolve prompt if provided and set messages
        prompt = getattr(req.inputs, "prompt", None)
        template_vars = getattr(req.inputs, "template_vars", None)

        # Initialize initial_messages with the original messages
        initial_messages = getattr(req.inputs, "messages", None) or []

        if prompt:
            try:
                # Use helper to resolve prompt, combine messages, and apply template vars
                combined_messages, initial_messages = resolve_and_apply_prompt(
                    prompt=prompt,
                    messages=getattr(req.inputs, "messages", None),
                    template_vars=template_vars,
                    project_id=req.project_id,
                    obj_read_func=self.obj_read,
                )
                req.inputs.messages = combined_messages

            except Exception as e:
                logger.error(f"Failed to resolve prompt: {e}", exc_info=True)
                return tsi.CompletionsCreateRes(
                    response={"error": f"Failed to resolve prompt: {e!s}"}
                )

        # Use shared setup logic
        model_info = self._model_to_provider_info_map.get(req.inputs.model)
        try:
            model_name, api_key, provider, base_url, extra_headers, return_type = (
                _setup_completion_model_info(model_info, req, self.obj_read)
            )
        except Exception as e:
            return tsi.CompletionsCreateRes(response={"error": str(e)})

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

        req.inputs.messages = initial_messages
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
        calls: list[CallStartCHInsertable | CallEndCHInsertable] = [
            start_call,
            end_call,
        ]
        batch_data = []
        for call in calls:
            call_dict = call.model_dump()
            values = [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]
            batch_data.append(values)

        self._insert_call_batch(batch_data)

        return tsi.CompletionsCreateRes(
            response=res.response, weave_call_id=start_call.id
        )

    # -------------------------------------------------------------------
    # Streaming variant
    # -------------------------------------------------------------------
    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> Iterator[dict[str, Any]]:
        """Stream LLM completion chunks.

        Mirrors ``completions_create`` but with streaming enabled.  If
        ``track_llm_call`` is True we emit a call_start record immediately and
        a call_end record once the stream finishes (successfully or not).

        When req.inputs.n > 1, properly separates and tracks all choices
        within a single call's output rather than creating separate calls.
        """
        # --- Resolve prompt if provided and prepend messages
        prompt = getattr(req.inputs, "prompt", None)
        template_vars = getattr(req.inputs, "template_vars", None)

        try:
            # Use helper to resolve prompt, combine messages, and apply template vars
            combined_messages, initial_messages = resolve_and_apply_prompt(
                prompt=prompt,
                messages=getattr(req.inputs, "messages", None),
                template_vars=template_vars,
                project_id=req.project_id,
                obj_read_func=self.obj_read,
            )
        except Exception as e:
            logger.error(f"Failed to resolve and apply prompt: {e}", exc_info=True)

            # Yield error as single chunk then stop.
            def _single_error_iter(err: Exception) -> Iterator[dict[str, str]]:
                yield {"error": f"Failed to resolve and apply prompt: {err!s}"}

            return _single_error_iter(e)

        # --- Shared setup logic (copy of completions_create up to litellm call)
        model_info = self._model_to_provider_info_map.get(req.inputs.model)
        try:
            (
                model_name,
                api_key,
                provider,
                base_url,
                extra_headers,
                return_type,
            ) = _setup_completion_model_info(model_info, req, self.obj_read)
        except Exception as e:
            # Yield error as single chunk then stop.
            def _single_error_iter(err: Exception) -> Iterator[dict[str, str]]:
                yield {"error": str(err)}

            return _single_error_iter(e)

        # Track start call if requested
        start_call: CallStartCHInsertable | None = None
        if req.track_llm_call:
            # Prepare inputs for tracking: use original messages (with template syntax)
            # and include prompt and template_vars
            tracked_inputs = req.inputs.model_dump(exclude_none=True)
            tracked_inputs["model"] = model_name
            tracked_inputs["messages"] = initial_messages
            if prompt:
                tracked_inputs["prompt"] = prompt
            if template_vars:
                tracked_inputs["template_vars"] = template_vars

            start = tsi.StartedCallSchemaForInsert(
                project_id=req.project_id,
                wb_user_id=req.wb_user_id,
                op_name=COMPLETIONS_CREATE_OP_NAME,
                started_at=datetime.datetime.now(),
                inputs=tracked_inputs,
                attributes={},
            )
            start_call = _start_call_for_insert_to_ch_insertable_start_call(start)
            # Insert immediately so that callers can see the call in progress
            self._insert_call(start_call)

        # Set the combined messages (with template vars replaced) for LiteLLM
        req.inputs.messages = combined_messages

        # Make a copy for the API call without prompt and template_vars
        api_inputs = req.inputs.model_copy()
        if hasattr(api_inputs, "prompt"):
            api_inputs.prompt = None
        if hasattr(api_inputs, "template_vars"):
            api_inputs.template_vars = None

        # --- Build the underlying chunk iterator
        chunk_iter = lite_llm_completion_stream(
            api_key=api_key or "",
            inputs=api_inputs,
            provider=provider,
            base_url=base_url,
            extra_headers=extra_headers,
            return_type=return_type,
        )

        # If tracking not requested just return chunks directly
        if not req.track_llm_call or start_call is None:
            return chunk_iter

        # Otherwise, wrap the iterator with tracking
        return _create_tracked_stream_wrapper(
            self._insert_call,
            chunk_iter,
            start_call,
            model_name,
            req.project_id,
        )

    def image_create(
        self, req: tsi.ImageGenerationCreateReq
    ) -> tsi.ImageGenerationCreateRes:
        """Create images using LLM image generation.

        Args:
            req (tsi.ImageGenerationCreateReq): The image generation request.

        Returns:
            tsi.ImageGenerationCreateRes: The image generation response.
        """
        # Validate input parameters
        if req.inputs.model is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No model specified in request"}
            )

        if req.inputs.prompt is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No prompt specified in request"}
            )

        # Get API key from secret fetcher
        secret_fetcher = _secret_fetcher_context.get()
        if secret_fetcher is None:
            logger.error("No secret fetcher available for image generation request")
            return tsi.ImageGenerationCreateRes(
                response={
                    "error": "Unable to access required credentials for image generation"
                }
            )

        api_key = (
            secret_fetcher.fetch("OPENAI_API_KEY")
            .get("secrets", {})
            .get("OPENAI_API_KEY")
        )

        if api_key is None:
            return tsi.ImageGenerationCreateRes(
                response={"error": "No OpenAI API key found"}
            )

        # Now that we have the API key, we can make the API call
        start_time = datetime.datetime.now()

        try:
            res = lite_llm_image_generation(
                api_key=api_key,
                inputs=req.inputs.model_dump(exclude_none=True),
                trace_server=self,
                project_id=req.project_id,
                wb_user_id=req.wb_user_id,
            )
            if "error" in res.response:
                return tsi.ImageGenerationCreateRes(
                    response={"error": res.response["error"]}
                )
        except Exception as e:
            return tsi.ImageGenerationCreateRes(
                response={"error": f"Image generation failed: {e!s}"}
            )

        end_time = datetime.datetime.now()

        # Return response directly if not tracking calls
        if req.track_llm_call is False:
            return res

        # Capture all input fields for call tracking
        input_data = req.inputs.model_dump(exclude_none=False)

        start = tsi.StartedCallSchemaForInsert(
            project_id=req.project_id,
            wb_user_id=req.wb_user_id,
            op_name=IMAGE_GENERATION_CREATE_OP_NAME,
            started_at=start_time,
            inputs=input_data,
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
            end.summary["usage"] = {req.inputs.model: res.response["usage"]}

        if "error" in res.response:
            end.exception = res.response["error"]

        end_call = _end_call_for_insert_to_ch_insertable_end_call(end)
        calls: list[CallStartCHInsertable | CallEndCHInsertable] = [
            start_call,
            end_call,
        ]
        batch_data = []
        for call in calls:
            call_dict = call.model_dump()
            values = [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]
            batch_data.append(values)

        try:
            self._insert_call_batch(batch_data)
        except Exception as e:
            # Log error but don't fail the response
            print(f"Error inserting call batch for image generation: {e}", flush=True)

        return tsi.ImageGenerationCreateRes(
            response=res.response, weave_call_id=start_call.id
        )

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

    # Private Methods
    @property
    def ch_client(self) -> CHClient:
        """Returns a thread-local clickhouse client.

        Each thread gets its own client instance to avoid session conflicts,
        but all clients share the same underlying connection pool via _CH_POOL_MANAGER.
        """
        if not hasattr(self._thread_local, "ch_client"):
            self._thread_local.ch_client = self._mint_client()
        return self._thread_local.ch_client

    def _mint_client(self) -> CHClient:
        """Create a new ClickHouse client using the shared pool manager."""
        client = clickhouse_connect.get_client(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            secure=self._port == 8443,
            pool_mgr=_CH_POOL_MANAGER,
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

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert_call_batch")
    def _insert_call_batch(
        self,
        batch: list,
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> None:
        set_current_span_dd_tags(
            {
                "clickhouse_trace_server_batched._insert_call_batch.count": str(
                    len(batch)
                )
            }
        )
        if not batch:
            return

        self._insert(
            "call_parts",
            data=batch,
            column_names=ALL_CALL_INSERT_COLUMNS,
            settings=settings,
            do_sync_insert=do_sync_insert,
        )

    def _select_objs_query(
        self,
        object_query_builder: ObjectMetadataQueryBuilder,
        metadata_only: bool = False,
    ) -> list[SelectableCHObjSchema]:
        """Main query for fetching objects.

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
            object_values[object_id, digest] = val_dump

        # update the val_dump for each object
        for obj in metadata_result:
            obj.val_dump = object_values.get((obj.object_id, obj.digest), "{}")
        return metadata_result

    def _run_migrations(self) -> None:
        logger.info("Running migrations")
        migrator = wf_migrator.get_clickhouse_trace_server_migrator(
            self._mint_client(),
            replicated=wf_env.wf_clickhouse_replicated(),
            replicated_path=wf_env.wf_clickhouse_replicated_path(),
            replicated_cluster=wf_env.wf_clickhouse_replicated_cluster(),
            use_distributed=wf_env.wf_clickhouse_use_distributed_tables(),
        )
        migrator.apply_migrations(self._database)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._query_stream")
    def _query_stream(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Iterator[tuple]:
        """Streams the results of a query from the database."""
        if not settings:
            settings = {}
        settings.update(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

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
            # always raises, optionally with custom error class
            handle_clickhouse_query_error(e)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._query")
    def _query(
        self,
        query: str,
        parameters: dict[str, Any],
        column_formats: dict[str, Any] | None = None,
        settings: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Directly queries the database and returns the result."""
        if not settings:
            settings = {}
        settings.update(ch_settings.CLICKHOUSE_DEFAULT_QUERY_SETTINGS)

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
            # always raises, optionally with custom error class
            handle_clickhouse_query_error(e)

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
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,  # overrides _use_async_insert
    ) -> QuerySummary:
        set_current_span_dd_tags(
            {
                "clickhouse_trace_server_batched._insert.table": table,
            }
        )

        if self._use_async_insert and not do_sync_insert:
            settings = ch_settings.update_settings_for_async_insert(settings)
            set_current_span_dd_tags(
                {
                    "clickhouse_trace_server_batched._insert.async_insert": True,
                }
            )
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
                ) from e
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
                },
            )
            raise

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert_call")
    def _insert_call(self, ch_call: CallCHInsertable) -> None:
        parameters = ch_call.model_dump()
        row = []
        for key in ALL_CALL_INSERT_COLUMNS:
            row.append(parameters.get(key, None))
        self._call_batch.append(row)
        if self._flush_immediately:
            self._flush_calls()

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._flush_calls")
    def _flush_calls(self) -> None:
        self._analyze_call_batch_breakdown()
        if len(self._call_batch) > 0:
            project_id_idx = ALL_CALL_INSERT_COLUMNS.index("project_id")
            project_id = self._call_batch[0][project_id_idx]
            self._noop_project_version_latency_test(project_id=project_id)

        try:
            self._insert_call_batch(self._call_batch)
        except InsertTooLarge:
            logger.info("Retrying with large objects stripped.")
            batch = self._strip_large_values(self._call_batch)
            # Insert rows one at a time after stripping large values
            for row in batch:
                self._insert_call_batch([row])

        self._call_batch = []

    @ddtrace.tracer.wrap(
        name="clickhouse_trace_server_batched._analyze_call_batch_breakdown"
    )
    def _analyze_call_batch_breakdown(self) -> None:
        """Analyze the batch to count calls with starts but no ends"""
        if not self._call_batch:
            return

        try:
            id_idx = ALL_CALL_INSERT_COLUMNS.index("id")
            started_at_idx = ALL_CALL_INSERT_COLUMNS.index("started_at")
            ended_at_idx = ALL_CALL_INSERT_COLUMNS.index("ended_at")

            started_call_ids: set[str] = set()
            ended_call_ids: set[str] = set()

            for row in self._call_batch:
                call_id = row[id_idx]
                started_at = row[started_at_idx]
                ended_at = row[ended_at_idx]

                if started_at is not None:
                    started_call_ids.add(call_id)
                if ended_at is not None:
                    ended_call_ids.add(call_id)

            unmatched_starts = started_call_ids - ended_call_ids

            set_current_span_dd_tags(
                {
                    "weave_trace_server._flush_calls.unmatched_starts": len(
                        unmatched_starts
                    ),
                }
            )
        except Exception as e:
            # Under no circumstances should we block ingest with an error
            pass

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._strip_large_values")
    def _strip_large_values(self, batch: list[list[Any]]) -> list[list[Any]]:
        """Iterate through the batch and replace large JSON values with placeholders.

        Only considers JSON dump columns and ensures their combined size stays under
        the limit by selectively replacing the largest values.
        """
        stripped_count = 0
        final_batch = []

        json_column_indices = [
            ALL_CALL_INSERT_COLUMNS.index(f"{col}_dump")
            for col in ALL_CALL_JSON_COLUMNS
        ]
        entity_too_large_payload_byte_size = _num_bytes(
            ch_settings.ENTITY_TOO_LARGE_PAYLOAD
        )

        for item in batch:
            # Calculate only JSON dump bytes
            json_idx_size_pairs = [
                (i, _num_bytes(item[i])) for i in json_column_indices
            ]
            total_json_bytes = sum(size for _, size in json_idx_size_pairs)

            # If over limit, try to optimize by selectively stripping largest JSON values
            stripped_item = list(item)
            sorted_json_idx_size_pairs = sorted(
                json_idx_size_pairs, key=lambda x: x[1], reverse=True
            )

            # Try to get under the limit by replacing largest JSON values
            for col_idx, size in sorted_json_idx_size_pairs:
                if (
                    total_json_bytes
                    <= ch_settings.CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT
                ):
                    break

                # Replace this large JSON value with placeholder, update running size
                stripped_item[col_idx] = ch_settings.ENTITY_TOO_LARGE_PAYLOAD
                total_json_bytes -= size - entity_too_large_payload_byte_size
                stripped_count += 1

            final_batch.append(stripped_item)

        ddtrace.tracer.current_span().set_tags(
            {
                "clickhouse_trace_server_batched._strip_large_values.stripped_count": str(
                    stripped_count
                )
            }
        )
        return final_batch


def _num_bytes(data: Any) -> int:
    """Calculate the number of bytes in a string.

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
    dt: datetime.datetime | None = None,
) -> datetime.datetime | None:
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
    val: str | None,
) -> Any | None:
    return _any_dump_to_any(val) if val else None


def _ch_call_dict_to_call_schema_dict(ch_call_dict: dict) -> dict:
    summary = _nullable_any_dump_to_any(ch_call_dict.get("summary_dump"))
    started_at = _ensure_datetimes_have_tz(ch_call_dict.get("started_at"))
    ended_at = _ensure_datetimes_have_tz(ch_call_dict.get("ended_at"))
    display_name = empty_str_to_none(ch_call_dict.get("display_name"))

    # Load attributes from attributes_dump
    attributes = _dict_dump_to_dict(ch_call_dict.get("attributes_dump", "{}"))

    # For backwards/future compatibility: inject otel_dump into attributes if present
    # Legacy trace servers stored all otel info in attributes, clients expect it
    # TODO(gst): consider returning the raw otel column and reconstructing client side
    if otel_dump := ch_call_dict.get("otel_dump"):
        attributes["otel_span"] = _dict_dump_to_dict(otel_dump)

    return {
        "project_id": ch_call_dict.get("project_id"),
        "id": ch_call_dict.get("id"),
        "trace_id": ch_call_dict.get("trace_id"),
        "parent_id": ch_call_dict.get("parent_id"),
        "thread_id": ch_call_dict.get("thread_id"),
        "turn_id": ch_call_dict.get("turn_id"),
        "op_name": ch_call_dict.get("op_name"),
        "started_at": started_at,
        "ended_at": ended_at,
        "attributes": attributes,
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
        "wb_run_step": ch_call_dict.get("wb_run_step"),
        "wb_run_step_end": ch_call_dict.get("wb_run_step_end"),
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
        leaf_object_class=ch_obj.leaf_object_class,
        val=json.loads(ch_obj.val_dump),
        size_bytes=ch_obj.size_bytes,
    )


def _ch_table_stats_to_table_stats_schema(
    ch_table_stats_row: Sequence[Any],
) -> tsi.TableStatsRow:
    # Unpack the row with a default for the third value if it doesn't exist
    row_tuple = tuple(ch_table_stats_row)
    digest, count = row_tuple[:2]
    storage_size_bytes = row_tuple[2] if len(row_tuple) > 2 else cast(Any, None)

    return tsi.TableStatsRow(
        count=count,
        digest=digest,
        storage_size_bytes=storage_size_bytes,
    )


def _ch_call_to_row(ch_call: CallCHInsertable) -> list[Any]:
    """Convert a CH insertable call to a row for batch insertion with the correct defaults."""
    call_dict = ch_call.model_dump()
    return [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]


def _start_call_for_insert_to_ch_insertable_start_call(
    start_call: tsi.StartedCallSchemaForInsert,
) -> CallStartCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()
    # Process inputs for base64 content if trace_server is provided
    inputs = start_call.inputs
    input_refs = extract_refs_from_values(inputs)

    otel_dump_str = None
    if start_call.otel_dump is not None:
        otel_dump_str = _dict_value_to_dump(start_call.otel_dump)

    return CallStartCHInsertable(
        project_id=start_call.project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        thread_id=start_call.thread_id,
        turn_id=start_call.turn_id,
        op_name=start_call.op_name,
        started_at=start_call.started_at,
        attributes_dump=_dict_value_to_dump(start_call.attributes),
        inputs_dump=_dict_value_to_dump(inputs),
        input_refs=input_refs,
        otel_dump=otel_dump_str,
        wb_run_id=start_call.wb_run_id,
        wb_run_step=start_call.wb_run_step,
        wb_user_id=start_call.wb_user_id,
        display_name=start_call.display_name,
    )


def _end_call_for_insert_to_ch_insertable_end_call(
    end_call: tsi.EndedCallSchemaForInsert,
) -> CallEndCHInsertable:
    # Note: it is technically possible for the user to mess up and provide the
    # wrong trace id (one that does not match the parent_id)!

    output = end_call.output
    output_refs = extract_refs_from_values(output)

    return CallEndCHInsertable(
        project_id=end_call.project_id,
        id=end_call.id,
        exception=end_call.exception,
        ended_at=end_call.ended_at,
        summary_dump=_dict_value_to_dump(dict(end_call.summary)),
        output_dump=_any_value_to_dump(output),
        output_refs=output_refs,
        wb_run_step_end=end_call.wb_run_step_end,
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


@ddtrace.tracer.wrap(name="clickhouse_trace_server_batched.find_call_descendants")
def find_call_descendants(
    root_ids: list[str],
    all_calls: list[tsi.CallSchema],
) -> list[str]:
    set_current_span_dd_tags(
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


def _update_metadata_from_chunk(
    chunk: dict[str, Any], aggregated_metadata: dict[str, Any]
) -> None:
    """Update aggregated metadata from a chunk."""
    metadata_fields = [
        "id",
        "created",
        "model",
        "system_fingerprint",
        "service_tier",
        "usage",
    ]

    for field in metadata_fields:
        if field in chunk and field not in aggregated_metadata:
            if field == "service_tier":
                aggregated_metadata[field] = chunk.get(field, "default")
            else:
                aggregated_metadata[field] = chunk[field]


def _process_tool_call_delta(
    tool_call_delta: list, tool_calls: list[dict[str, Any]]
) -> None:
    """Process tool call delta and update tool_calls list."""
    for tool_call in tool_call_delta:
        tool_call_index = tool_call.get("index", 0)

        # Ensure we have enough tool calls in our list
        while len(tool_calls) <= tool_call_index:
            tool_calls.append(
                {
                    "id": None,
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            )

        existing_tool_call = tool_calls[tool_call_index]

        # Update existing tool call fields
        if tool_call.get("id"):
            existing_tool_call["id"] = tool_call["id"]
        if tool_call.get("type"):
            existing_tool_call["type"] = tool_call["type"]

        if "function" in tool_call:
            function_data = tool_call["function"]
            if function_data.get("name"):
                existing_tool_call["function"]["name"] = function_data["name"]
            if "arguments" in function_data:
                existing_tool_call["function"]["arguments"] += function_data[
                    "arguments"
                ]


def _create_tracked_stream_wrapper(
    insert_call: Callable[[CallEndCHInsertable], None],
    chunk_iter: Iterator[dict[str, Any]],
    start_call: CallStartCHInsertable,
    model_name: str,
    project_id: str,
) -> Iterator[dict[str, Any]]:
    """Create a wrapper that tracks streaming completion and emits call records."""

    def _stream_wrapper() -> Iterator[dict[str, Any]]:
        # (1) send meta chunk first so clients can associate stream
        yield {"_meta": {"weave_call_id": start_call.id}}

        # Initialize accumulation variables for all choices
        aggregated_output: dict[str, Any] | None = None
        choice_contents: dict[int, list[str]] = {}  # Track content by choice index
        choice_tool_calls: dict[
            int, list[dict[str, Any]]
        ] = {}  # Track tool calls by choice index
        choice_reasoning_content: dict[
            int, list[str]
        ] = {}  # Track reasoning by choice index
        choice_finish_reasons: dict[
            int, str | None
        ] = {}  # Track finish reasons by choice index
        aggregated_metadata: dict[str, Any] = {}

        try:
            for chunk in chunk_iter:
                yield chunk  # Yield to client immediately

                if not isinstance(chunk, dict):
                    continue

                # Accumulate metadata from chunks
                _update_metadata_from_chunk(chunk, aggregated_metadata)

                # Process all choices in the chunk
                choices = chunk.get("choices")
                if choices:
                    for choice in choices:
                        choice_index = choice.get("index", 0)

                        # Initialize choice accumulators if not present
                        if choice_index not in choice_contents:
                            choice_contents[choice_index] = []
                            choice_tool_calls[choice_index] = []
                            choice_reasoning_content[choice_index] = []
                            choice_finish_reasons[choice_index] = None

                        # Update finish reason
                        if "finish_reason" in choice:
                            choice_finish_reasons[choice_index] = choice[
                                "finish_reason"
                            ]

                        delta = choice.get("delta")
                        if delta and isinstance(delta, dict):
                            # Accumulate assistant content for this choice
                            content_piece = delta.get("content")
                            if content_piece:
                                choice_contents[choice_index].append(content_piece)

                            # Handle tool calls for this choice
                            tool_call_delta = delta.get("tool_calls")
                            if tool_call_delta:
                                _process_tool_call_delta(
                                    tool_call_delta, choice_tool_calls[choice_index]
                                )

                            # Handle reasoning content for this choice
                            reasoning_content_delta = delta.get("reasoning_content")
                            if reasoning_content_delta:
                                choice_reasoning_content[choice_index].append(
                                    reasoning_content_delta
                                )

        finally:
            # Build final aggregated output with all choices
            if choice_contents or choice_tool_calls or choice_reasoning_content:
                choices_array = _build_choices_array(
                    choice_contents,
                    choice_tool_calls,
                    choice_reasoning_content,
                    choice_finish_reasons,
                )
                aggregated_output = _build_completion_response(
                    aggregated_metadata,
                    choices_array,
                )

            # Prepare summary and end call
            summary: dict[str, Any] = {}
            if aggregated_output is not None and model_name is not None:
                aggregated_output["model"] = model_name

                if "usage" in aggregated_output:
                    summary["usage"] = {model_name: aggregated_output["usage"]}

            end = tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=start_call.id,
                ended_at=datetime.datetime.now(),
                output=aggregated_output,
                summary=summary,
            )
            end_call = _end_call_for_insert_to_ch_insertable_end_call(end)
            insert_call(end_call)

    return _stream_wrapper()


def _setup_completion_model_info(
    model_info: LLMModelProviderInfo | None,
    req: tsi.CompletionsCreateReq,
    obj_read: Callable[[tsi.ObjReadReq], tsi.ObjReadRes],
) -> tuple[str, str | None, str, str | None, dict[str, str], str | None]:
    """Extract model setup logic shared between completions_create and completions_create_stream.

    Returns: (model_name, api_key, provider, base_url, extra_headers, return_type)
    Note: api_key can be None for bedrock providers since they use AWS credentials instead.
    """
    model_name = req.inputs.model
    api_key: str | None = None
    provider: str = "openai"  # Default provider
    base_url: str | None = None
    extra_headers: dict[str, str] = {}
    return_type: str | None = None

    # Check for explicit custom provider prefix
    is_explicit_custom = model_name.startswith("custom::")

    is_coreweave = (
        model_info and model_info.get("litellm_provider") == "coreweave"
    ) or model_name.startswith("coreweave/")
    if is_coreweave:
        # See https://docs.litellm.ai/docs/providers/openai_compatible
        # but ignore the bit about omitting the /v1 because it is actually necessary
        req.inputs.model = "openai/" + model_name.removeprefix("coreweave/")
        provider = "custom"
        base_url = wf_env.inference_service_base_url()
        # The API key should have been passed in as an extra header.
        if req.inputs.extra_headers:
            api_key = req.inputs.extra_headers.pop("api_key", None)
            extra_headers = req.inputs.extra_headers
            req.inputs.extra_headers = None
        return_type = "openai"
    elif is_explicit_custom:
        # Custom provider path - model_name format: custom::<provider>::<model>
        # Parse provider and model names, create sanitized object_id for lookup
        name_part = model_name.replace("custom::", "")

        if "::" in name_part:
            # Format: custom::<provider>::<model>
            provider_name, model_name_part = name_part.split("::", 1)

            # Create sanitized object_id to match what was created during provider setup

            sanitized_provider = _sanitize_name_for_object_id(provider_name)
            sanitized_model = _sanitize_name_for_object_id(model_name_part)
            sanitized_object_id = f"{sanitized_provider}-{sanitized_model}"
        else:
            # Fallback: assume it's already in object_id format
            # Extract names from object_id (this is a fallback case)
            parts = name_part.split("-", 1) if "-" in name_part else [name_part, ""]
            provider_name = parts[0]  # May be sanitized
            model_name_part = parts[1] if len(parts) > 1 else ""
            sanitized_provider = provider_name  # Already sanitized
            sanitized_object_id = name_part

        custom_provider_info = get_custom_provider_info(
            project_id=req.project_id,
            provider_name=sanitized_provider,
            model_name=sanitized_object_id,
            obj_read_func=obj_read,
        )

        base_url = custom_provider_info.base_url
        final_model_name = custom_provider_info.actual_model_name
        provider_model_name = (
            f"{provider_name}/{final_model_name}"
            if "::" in name_part
            else final_model_name
        )

        # prefix the model name with "ollama/" if it is an ollama model else with openai/
        req.inputs.model = (
            "ollama/" + final_model_name
            if "ollama" in provider_name.lower()
            else "openai/" + final_model_name
        )

        return (
            provider_model_name,
            custom_provider_info.api_key,
            "custom",  # return "custom" as provider
            base_url,
            custom_provider_info.extra_headers,
            custom_provider_info.return_type,
        )
    elif model_info:
        secret_name = model_info.get("api_key_name")
        if not secret_name:
            raise InvalidRequest(f"No secret name found for model {model_name}")

        secret_fetcher = _secret_fetcher_context.get()
        if not secret_fetcher:
            raise InvalidRequest(
                f"No secret fetcher found, cannot fetch API key for model {model_name}"
            )

        api_key = secret_fetcher.fetch(secret_name).get("secrets", {}).get(secret_name)
        provider = model_info.get("litellm_provider", "openai")

        if not api_key and provider not in ("bedrock", "bedrock_converse"):
            raise MissingLLMApiKeyError(
                f"No API key {secret_name} found for model {model_name}",
                api_key_name=secret_name,
            )

    return (
        model_name,
        api_key,
        provider,
        base_url,
        extra_headers,
        return_type,
    )


def _sanitize_name_for_object_id(name: str) -> str:
    return sub(r"[^a-zA-Z0-9_-]", "_", name)
