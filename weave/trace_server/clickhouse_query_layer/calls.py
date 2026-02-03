# ClickHouse Calls - Call operations (v1, v2) and stats

import datetime
from collections import defaultdict
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

import ddtrace

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import (
    process_call_req_to_content,
    process_complete_call_to_content,
)
from weave.trace_server.clickhouse_query_layer import settings as ch_settings
from weave.trace_server.clickhouse_query_layer.batching import BatchManager
from weave.trace_server.clickhouse_query_layer.client import (
    ClickHouseClient,
    any_value_to_dump,
    datetime_to_microseconds,
    dict_dump_to_dict,
    dict_value_to_dump,
    empty_str_to_none,
    ensure_datetimes_have_tz,
    nullable_any_dump_to_any,
)
from weave.trace_server.clickhouse_query_layer.query_builders.calls.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    build_calls_complete_delete_query,
    build_calls_complete_update_end_query,
    build_calls_complete_update_query,
    build_calls_stats_query,
)
from weave.trace_server.clickhouse_query_layer.schema import (
    ALL_CALL_COMPLETE_INSERT_COLUMNS,
    ALL_CALL_INSERT_COLUMNS,
    ALL_CALL_SELECT_COLUMNS,
    REQUIRED_CALL_COLUMNS,
    CallCHInsertable,
    CallCompleteCHInsertable,
    CallDeleteCHInsertable,
    CallEndCHInsertable,
    CallStartCHInsertable,
    CallUpdateCHInsertable,
)
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import CallsCompleteModeRequired, RequestTooLarge
from weave.trace_server.ids import generate_id
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.project_version import TableRoutingResolver
from weave.trace_server.project_version.types import WriteTarget
from weave.trace_server.trace_server_common import (
    DynamicBatchProcessor,
    LRUCache,
    get_nested_key,
    hydrate_calls_with_feedback,
    make_derived_summary_fields,
    make_feedback_query_req,
    set_nested_key,
)
from weave.trace_server.trace_server_interface_util import (
    assert_non_null_wb_user_id,
    extract_refs_from_values,
)

if TYPE_CHECKING:
    from weave.trace_server.kafka import KafkaProducer


class CallsRepository:
    """Repository for call operations including v1, v2, and stats."""

    def __init__(
        self,
        ch_client: ClickHouseClient,
        batch_manager: BatchManager,
        table_routing_resolver: TableRoutingResolver,
        kafka_producer_getter: Callable[[], "KafkaProducer"],
        feedback_query_func: Callable[[tsi.FeedbackQueryReq], tsi.FeedbackQueryRes],
        refs_read_batch_func: Callable[
            [str, list[ri.InternalObjectRef], LRUCache], list[Any]
        ],
    ):
        self._ch_client = ch_client
        self._batch_manager = batch_manager
        self._table_routing_resolver = table_routing_resolver
        self._kafka_producer_getter = kafka_producer_getter
        self._feedback_query_func = feedback_query_func
        self._refs_read_batch_func = refs_read_batch_func

    # =========================================================================
    # V1 API
    # =========================================================================

    def call_start(self, req: tsi.CallStartReq, trace_server: Any) -> tsi.CallStartRes:
        """Start a call (v1 API)."""
        req = process_call_req_to_content(req, trace_server)
        ch_call = start_call_for_insert_to_ch_insertable(req.start)

        # Check write target - v1 call_start cannot write to calls_complete
        write_target = self._table_routing_resolver.resolve_v1_write_target(
            ch_call.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            raise CallsCompleteModeRequired(ch_call.project_id)

        self._insert_call(ch_call)

        return tsi.CallStartRes(
            id=ch_call.id,
            trace_id=ch_call.trace_id,
        )

    def call_end(
        self,
        req: tsi.CallEndReq,
        trace_server: Any,
        publish: bool = True,
        flush_immediately: bool = False,
    ) -> tsi.CallEndRes:
        """End a call (v1 API)."""
        req = process_call_req_to_content(req, trace_server)
        ch_call = end_call_for_insert_to_ch_insertable(req.end)

        # Check write target - v1 call_end cannot write to calls_complete
        write_target = self._table_routing_resolver.resolve_v1_write_target(
            ch_call.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            raise CallsCompleteModeRequired(ch_call.project_id)

        self._insert_call(ch_call)

        if publish:
            maybe_enqueue_minimal_call_end(
                self._kafka_producer_getter(),
                req.end.project_id,
                req.end.id,
                req.end.ended_at,
                flush_immediately,
            )

        return tsi.CallEndRes()

    def call_start_batch(
        self, req: tsi.CallCreateBatchReq, trace_server: Any
    ) -> tsi.CallCreateBatchRes:
        """Process a batch of call start/end operations."""
        with self._batch_manager.call_batch():
            res = []
            for item in req.batch:
                if item.mode == "start":
                    res.append(self.call_start(item.req, trace_server))
                elif item.mode == "end":
                    res.append(
                        self.call_end(item.req, trace_server, flush_immediately=False)
                    )
                else:
                    raise ValueError("Invalid mode")
        return tsi.CallCreateBatchRes(res=res)

    # =========================================================================
    # V2 API
    # =========================================================================

    def calls_complete(
        self, req: tsi.CallsUpsertCompleteReq, trace_server: Any
    ) -> tsi.CallsUpsertCompleteRes:
        """Insert a batch of complete calls (v2 API)."""
        with self._batch_manager.call_batch():
            for complete_call in req.batch:
                complete_call = process_complete_call_to_content(
                    complete_call, trace_server
                )

                write_target = self._table_routing_resolver.resolve_v2_write_target(
                    complete_call.project_id,
                    self._ch_client.ch_client,
                )

                ch_call = complete_call_to_ch_insertable(complete_call)
                if write_target == WriteTarget.CALLS_COMPLETE:
                    self._insert_call_complete(ch_call)
                else:
                    self._insert_call_to_v1(ch_call)

                maybe_enqueue_minimal_call_end(
                    self._kafka_producer_getter(),
                    complete_call.project_id,
                    complete_call.id,
                    complete_call.ended_at,
                )

        return tsi.CallsUpsertCompleteRes()

    def call_start_v2(
        self, req: tsi.CallStartV2Req, trace_server: Any
    ) -> tsi.CallStartV2Res:
        """Start a single call (v2 API)."""
        start_req = process_call_req_to_content(
            tsi.CallStartReq(start=req.start), trace_server
        )
        ch_start = start_call_for_insert_to_ch_insertable(start_req.start)

        write_target = self._table_routing_resolver.resolve_v2_write_target(
            ch_start.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            ch_complete_start = start_call_insertable_to_complete_start(ch_start)
            self._insert_call_complete(ch_complete_start)
        else:
            self._insert_call(ch_start)

        return tsi.CallStartV2Res(id=ch_start.id, trace_id=ch_start.trace_id)

    def call_end_v2(self, req: tsi.CallEndV2Req, trace_server: Any) -> tsi.CallEndV2Res:
        """End a single call (v2 API)."""
        req = process_call_req_to_content(req, trace_server)

        write_target = self._table_routing_resolver.resolve_v2_write_target(
            req.end.project_id,
            self._ch_client.ch_client,
        )

        if write_target == WriteTarget.CALLS_COMPLETE:
            self._update_call_end_in_calls_complete(req.end)
        elif write_target == WriteTarget.CALLS_MERGED:
            ch_end = end_call_for_insert_to_ch_insertable(req.end)
            self._insert_call(ch_end)
            if self._batch_manager._flush_immediately:
                self._batch_manager.flush_calls()

        maybe_enqueue_minimal_call_end(
            self._kafka_producer_getter(),
            req.end.project_id,
            req.end.id,
            req.end.ended_at,
        )

        return tsi.CallEndV2Res()

    @ddtrace.tracer.wrap(name="calls_repository._update_call_end_in_calls_complete")
    def _update_call_end_in_calls_complete(
        self, end_call: tsi.EndedCallSchemaForInsertWithStartedAt
    ) -> None:
        """Update a call's end data in calls_complete using lightweight UPDATE."""
        table_name = self._get_calls_complete_table_name()

        output = end_call.output
        output_refs = extract_refs_from_values(output)
        output_dump = any_value_to_dump(output)
        summary_dump = dict_value_to_dump(dict(end_call.summary))

        ended_at_us = datetime_to_microseconds(end_call.ended_at)

        pb = ParamBuilder()
        project_id_param = pb.add_param(end_call.project_id)
        id_param = pb.add_param(end_call.id)
        ended_at_param = pb.add_param(ended_at_us)
        exception_param = pb.add_param(end_call.exception)
        output_dump_param = pb.add_param(output_dump)
        summary_dump_param = pb.add_param(summary_dump)
        output_refs_param = pb.add_param(output_refs)
        wb_run_step_end_param = pb.add_param(end_call.wb_run_step_end)

        started_at_param: str | None = None
        if end_call.started_at is not None:
            started_at_us = datetime_to_microseconds(end_call.started_at)
            started_at_param = pb.add_param(started_at_us)

        query = build_calls_complete_update_end_query(
            table_name=table_name,
            project_id_param=project_id_param,
            id_param=id_param,
            ended_at_param=ended_at_param,
            exception_param=exception_param,
            output_dump_param=output_dump_param,
            summary_dump_param=summary_dump_param,
            output_refs_param=output_refs_param,
            wb_run_step_end_param=wb_run_step_end_param,
            started_at_param=started_at_param,
            cluster_name=self._ch_client.clickhouse_cluster_name,
        )

        self._ch_client.command(query, parameters=pb.get_params())

    def _get_calls_complete_table_name(self) -> str:
        """Get the appropriate table name for calls_complete updates."""
        if self._ch_client.use_distributed_mode:
            return f"calls_complete{ch_settings.LOCAL_TABLE_SUFFIX}"
        return "calls_complete"

    # =========================================================================
    # Stats Operations
    # =========================================================================

    def call_stats(self, req: tsi.CallStatsReq) -> tsi.CallStatsRes:
        """Get aggregated call statistics over a time range."""
        from weave.trace_server.clickhouse_query_layer.query_builders.calls.call_metrics_query_builder import (
            build_call_metrics_query,
        )
        from weave.trace_server.clickhouse_query_layer.query_builders.calls.usage_query_builder import (
            build_usage_query,
        )

        # Resolve which table to read from based on project data residency
        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )

        usage_buckets: list[dict[str, Any]] = []
        call_buckets: list[dict[str, Any]] = []
        granularity = req.granularity
        end = req.end or datetime.datetime.now(datetime.timezone.utc)

        # Build usage stats query if requested
        if req.usage_metrics:
            pb = ParamBuilder()
            query, columns, params, granularity, start, end = build_usage_query(
                req, req.usage_metrics, pb, read_table
            )
            result = self._ch_client.query(query, params)
            for row in result.result_rows:
                bucket = dict(zip(columns, row, strict=False))
                usage_buckets.append(bucket)

        # Build call metrics query if requested
        if req.call_metrics:
            pb = ParamBuilder()
            query, columns, params, granularity, start, end = build_call_metrics_query(
                req, req.call_metrics, pb, read_table
            )
            result = self._ch_client.query(query, params)
            for row in result.result_rows:
                bucket = dict(zip(columns, row, strict=False))
                call_buckets.append(bucket)

        return tsi.CallStatsRes(
            start=req.start,
            end=end,
            granularity=granularity,
            timezone=req.timezone,
            usage_buckets=usage_buckets,
            call_buckets=call_buckets,
        )

    def trace_usage(self, req: tsi.TraceUsageReq) -> tsi.TraceUsageRes:
        """Compute per-call usage for a trace, with descendant rollup."""
        from weave.trace_server.usage_utils import aggregate_usage_with_descendants

        # Query all matching calls
        calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=req.filter,
            query=req.query,
            include_costs=req.include_costs,
            limit=req.limit,
            columns=["id", "parent_id", "summary"],
        )
        calls = list(self.calls_query_stream(calls_req))

        # Compute rolled-up usage
        call_usage = aggregate_usage_with_descendants(
            calls, include_costs=req.include_costs
        )

        return tsi.TraceUsageRes(call_usage=call_usage)

    def calls_usage(self, req: tsi.CallsUsageReq) -> tsi.CallsUsageRes:
        """Compute aggregated usage for multiple root calls."""
        from weave.trace_server.usage_utils import aggregate_usage_with_descendants

        # Get all calls for the specified root call IDs
        calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(call_ids=req.call_ids),
            include_costs=req.include_costs,
            limit=req.limit,
            columns=["id", "parent_id", "trace_id", "summary"],
        )
        root_calls = list(self.calls_query_stream(calls_req))

        # Get trace IDs for all root calls
        trace_ids = list({c.trace_id for c in root_calls if c.trace_id})

        if not trace_ids:
            return tsi.CallsUsageRes(call_usage={})

        # Get all calls in those traces
        all_calls_req = tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(trace_ids=trace_ids),
            include_costs=req.include_costs,
            limit=req.limit,
            columns=["id", "parent_id", "trace_id", "summary"],
        )
        all_calls = list(self.calls_query_stream(all_calls_req))

        # Compute rolled-up usage for each root call
        # First get usage for all calls, then extract just the root calls
        all_usage = aggregate_usage_with_descendants(
            all_calls, include_costs=req.include_costs
        )

        # Filter to just the requested root call IDs
        call_usage = {
            call_id: usage
            for call_id, usage in all_usage.items()
            if call_id in req.call_ids
        }

        return tsi.CallsUsageRes(call_usage=call_usage)

    # =========================================================================
    # Query Operations
    # =========================================================================

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """Read a single call."""
        res = self.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=req.project_id,
                filter=tsi.CallsFilter(call_ids=[req.id]),
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
        """Query calls and return all results."""
        stream = self.calls_query_stream(req)
        return tsi.CallsQueryRes(calls=list(stream))

    @ddtrace.tracer.wrap(name="calls_repository.calls_query_stream")
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Stream calls that match the given query."""
        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )
        cq = CallsQuery(
            project_id=req.project_id,
            read_table=read_table,
            include_costs=req.include_costs or False,
            include_storage_size=req.include_storage_size or False,
            include_total_storage_size=req.include_total_storage_size or False,
        )
        columns = ALL_CALL_SELECT_COLUMNS
        if req.columns:
            columns = [col.split(".")[0] for col in req.columns]
            if "summary" in columns or req.include_costs:
                columns += ["ended_at", "exception", "display_name"]
            columns = list(set(REQUIRED_CALL_COLUMNS + columns))

        columns = sorted(columns)

        if req.include_storage_size:
            columns.append("storage_size_bytes")
        if req.include_total_storage_size:
            columns.append("total_storage_size_bytes")

        if req.include_costs:
            set_current_span_dd_tags({"include_costs": "true"})
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

        if req.sort_by is not None:
            for sort_by in req.sort_by:
                cq.add_order(sort_by.field, sort_by.direction)
            if not any(sort_by.field == "id" for sort_by in req.sort_by):
                cq.add_order("id", "asc")
        else:
            cq.add_order("started_at", "asc")
            cq.add_order("id", "asc")

        if req.limit is not None:
            cq.set_limit(req.limit)
        if req.offset is not None:
            cq.set_offset(req.offset)

        pb = ParamBuilder()
        raw_res = self._ch_client.query_stream(cq.as_sql(pb), pb.get_params())

        select_columns = [c.field for c in cq.select_fields]
        expand_columns = req.expand_columns or []
        include_feedback = req.include_feedback or False

        if include_feedback:
            set_current_span_dd_tags({"include_feedback": "true"})
        if expand_columns:
            set_current_span_dd_tags({"expand_columns": "true"})

        def row_to_call_schema_dict(row: tuple[Any, ...]) -> dict[str, Any]:
            return ch_call_dict_to_call_schema_dict(
                dict(zip(select_columns, row, strict=False))
            )

        try:
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
        finally:
            if hasattr(raw_res, "close"):
                raw_res.close()

    @ddtrace.tracer.wrap(name="calls_repository.calls_query_stats")
    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Return stats for the given query."""
        read_table = self._table_routing_resolver.resolve_read_table(
            req.project_id, self._ch_client.ch_client
        )
        pb = ParamBuilder()
        query, columns = build_calls_stats_query(req, pb, read_table)
        raw_res = self._ch_client.query(query, pb.get_params())

        res_dict = (
            dict(zip(columns, raw_res.result_rows[0], strict=False))
            if raw_res.result_rows
            else {}
        )

        return tsi.CallsQueryStatsRes(
            count=res_dict.get("count", 0),
            total_storage_size_bytes=res_dict.get("total_storage_size_bytes"),
        )

    # =========================================================================
    # Delete and Update Operations
    # =========================================================================

    @ddtrace.tracer.wrap(name="calls_repository.calls_delete")
    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls and their descendants."""
        assert_non_null_wb_user_id(req)
        if len(req.call_ids) > ch_settings.MAX_DELETE_CALLS_COUNT:
            raise RequestTooLarge(
                f"Cannot delete more than {ch_settings.MAX_DELETE_CALLS_COUNT} calls at once"
            )

        set_current_span_dd_tags(
            {"calls_repository.calls_delete.count": str(len(req.call_ids))}
        )

        parents = list(
            self.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=req.project_id,
                    filter=tsi.CallsFilter(call_ids=req.call_ids),
                    columns=["id", "parent_id"],
                )
            )
        )
        parent_trace_ids = [p.trace_id for p in parents]

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

        write_target = self._table_routing_resolver.resolve_v1_write_target(
            req.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            self._delete_calls_complete(req.project_id, all_descendants)
            return tsi.CallsDeleteRes(num_deleted=len(all_descendants))

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

        with self._batch_manager.call_batch():
            for insertable in insertables:
                self._insert_call(insertable)

        return tsi.CallsDeleteRes(num_deleted=len(all_descendants))

    @ddtrace.tracer.wrap(name="calls_repository._delete_calls_complete")
    def _delete_calls_complete(self, project_id: str, call_ids: list[str]) -> None:
        """Delete calls from calls_complete table."""
        pb = ParamBuilder()
        project_id_param = pb.add_param(project_id)
        call_ids_param = pb.add_param(call_ids)
        delete_query = build_calls_complete_delete_query(
            "calls_complete",
            project_id_param,
            call_ids_param,
            cluster_name=self._ch_client.clickhouse_cluster_name,
        )
        self._ch_client.command(delete_query, parameters=pb.get_params())

    @ddtrace.tracer.wrap(name="calls_repository.call_update")
    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update a call's display name."""
        assert_non_null_wb_user_id(req)
        self._ensure_valid_update_field(req)

        write_target = self._table_routing_resolver.resolve_v1_write_target(
            req.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            self._update_calls_complete(req.project_id, req.call_id, req.display_name)
            return tsi.CallUpdateRes()

        renamed_insertable = CallUpdateCHInsertable(
            project_id=req.project_id,
            id=req.call_id,
            wb_user_id=req.wb_user_id,
            display_name=req.display_name,
        )
        self._insert_call(renamed_insertable)

        return tsi.CallUpdateRes()

    def _ensure_valid_update_field(self, req: tsi.CallUpdateReq) -> None:
        """Validate that a valid update field is provided."""
        valid_update_fields = ["display_name"]
        for field in valid_update_fields:
            if getattr(req, field, None) is not None:
                return
        raise ValueError(
            f"One of [{', '.join(valid_update_fields)}] is required for call update"
        )

    @ddtrace.tracer.wrap(name="calls_repository._update_calls_complete")
    def _update_calls_complete(
        self, project_id: str, call_id: str, display_name: str
    ) -> None:
        """Update a call in calls_complete table."""
        pb = ParamBuilder()
        project_id_param = pb.add_param(project_id)
        call_id_param = pb.add_param(call_id)
        display_name_param = pb.add_param(display_name)
        update_query = build_calls_complete_update_query(
            "calls_complete",
            project_id_param,
            call_id_param,
            display_name_param,
            cluster_name=self._ch_client.clickhouse_cluster_name,
        )
        self._ch_client.command(update_query, parameters=pb.get_params())

    # =========================================================================
    # Internal Insert Methods
    # =========================================================================

    def _insert_call(self, ch_call: CallCHInsertable) -> None:
        """Insert a call into the batch."""
        parameters = ch_call.model_dump()
        row = [parameters.get(key, None) for key in ALL_CALL_INSERT_COLUMNS]
        self._batch_manager.add_call_to_batch(row)

    def _insert_call_complete(self, ch_call: CallCompleteCHInsertable) -> None:
        """Insert a complete call into the batch."""
        parameters = ch_call.model_dump()
        row = [parameters.get(key, None) for key in ALL_CALL_COMPLETE_INSERT_COLUMNS]
        self._batch_manager.add_call_complete_to_batch(row)

    def _insert_call_to_v1(self, ch_call: CallCompleteCHInsertable) -> None:
        """Insert a complete call into the v1 call_parts table."""
        parameters = ch_call.model_dump()
        row = [parameters.get(key, None) for key in ALL_CALL_INSERT_COLUMNS]
        self._batch_manager.add_call_to_batch(row)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @ddtrace.tracer.wrap(name="calls_repository._add_feedback_to_calls")
    def _add_feedback_to_calls(
        self, project_id: str, calls: list[dict[str, Any]]
    ) -> None:
        """Add feedback to call dicts."""
        if len(calls) == 0:
            return

        feedback_query_req = make_feedback_query_req(project_id, calls)
        with self._ch_client.with_new_client():
            feedback = self._feedback_query_func(feedback_query_req)
        hydrate_calls_with_feedback(calls, feedback)

    def _get_refs_to_resolve(
        self, calls: list[dict[str, Any]], expand_columns: list[str]
    ) -> dict[tuple[int, str], ri.InternalObjectRef]:
        """Get refs that need to be resolved for expansion."""
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

    @ddtrace.tracer.wrap(name="calls_repository._expand_call_refs")
    def _expand_call_refs(
        self,
        project_id: str,
        calls: list[dict[str, Any]],
        expand_columns: list[str],
        ref_cache: LRUCache,
    ) -> None:
        """Expand ref columns in call dicts."""
        if len(calls) == 0:
            return

        expand_column_by_depth = defaultdict(list)
        for col in expand_columns:
            expand_column_by_depth[col.count(".")].append(col)

        for depth in sorted(expand_column_by_depth.keys()):
            refs_to_resolve = self._get_refs_to_resolve(
                calls, expand_column_by_depth[depth]
            )
            if not refs_to_resolve:
                continue

            with self._ch_client.with_new_client():
                unique_ref_map = {}
                for ref in refs_to_resolve.values():
                    if ref.uri() not in unique_ref_map:
                        unique_ref_map[ref.uri()] = ref

                vals = self._refs_read_batch_func(
                    project_id, list(unique_ref_map.values()), ref_cache
                )

                ref_val_map = {}
                for ref, val in zip(unique_ref_map.values(), vals, strict=False):
                    ref_val_map[ref.uri()] = val

                for (i, col), ref in refs_to_resolve.items():
                    val = ref_val_map.get(ref.uri())
                    if val is not None:
                        if isinstance(val, dict) and "_ref" not in val:
                            val["_ref"] = ref.uri()
                        set_nested_key(calls[i], col, val)


# =============================================================================
# Converters
# =============================================================================


def start_call_for_insert_to_ch_insertable(
    start_call: tsi.StartedCallSchemaForInsert,
) -> CallStartCHInsertable:
    """Convert a start call to CH insertable format."""
    call_id = start_call.id or generate_id()
    trace_id = start_call.trace_id or generate_id()
    inputs = start_call.inputs
    input_refs = extract_refs_from_values(inputs)

    otel_dump_str = None
    if start_call.otel_dump is not None:
        otel_dump_str = dict_value_to_dump(start_call.otel_dump)

    return CallStartCHInsertable(
        project_id=start_call.project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=start_call.parent_id,
        thread_id=start_call.thread_id,
        turn_id=start_call.turn_id,
        op_name=start_call.op_name,
        started_at=start_call.started_at,
        attributes_dump=dict_value_to_dump(start_call.attributes),
        inputs_dump=dict_value_to_dump(inputs),
        input_refs=input_refs,
        otel_dump=otel_dump_str,
        wb_run_id=start_call.wb_run_id,
        wb_run_step=start_call.wb_run_step,
        wb_user_id=start_call.wb_user_id,
        display_name=start_call.display_name,
    )


def end_call_for_insert_to_ch_insertable(
    end_call: tsi.EndedCallSchemaForInsert,
) -> CallEndCHInsertable:
    """Convert an end call to CH insertable format."""
    output = end_call.output
    output_refs = extract_refs_from_values(output)

    return CallEndCHInsertable(
        project_id=end_call.project_id,
        id=end_call.id,
        exception=end_call.exception,
        ended_at=end_call.ended_at,
        summary_dump=dict_value_to_dump(dict(end_call.summary)),
        output_dump=any_value_to_dump(output),
        output_refs=output_refs,
        wb_run_step_end=end_call.wb_run_step_end,
    )


def start_call_insertable_to_complete_start(
    ch_start: CallStartCHInsertable,
) -> CallCompleteCHInsertable:
    """Convert a start-only call into a calls_complete insertable row."""
    return CallCompleteCHInsertable(
        project_id=ch_start.project_id,
        id=ch_start.id,
        trace_id=ch_start.trace_id,
        parent_id=ch_start.parent_id,
        thread_id=ch_start.thread_id,
        turn_id=ch_start.turn_id,
        op_name=ch_start.op_name,
        display_name=ch_start.display_name,
        started_at=ch_start.started_at,
        ended_at=None,
        exception=None,
        attributes_dump=ch_start.attributes_dump,
        inputs_dump=ch_start.inputs_dump,
        input_refs=ch_start.input_refs,
        output_dump=any_value_to_dump(None),
        summary_dump=dict_value_to_dump({}),
        otel_dump=ch_start.otel_dump,
        output_refs=ch_start.output_refs,
        wb_user_id=ch_start.wb_user_id,
        wb_run_id=ch_start.wb_run_id,
        wb_run_step=ch_start.wb_run_step,
        wb_run_step_end=None,
    )


def complete_call_to_ch_insertable(
    complete_call: tsi.CompletedCallSchemaForInsert,
) -> CallCompleteCHInsertable:
    """Convert a completed call schema to CH insertable format."""
    inputs = complete_call.inputs
    input_refs = extract_refs_from_values(inputs)
    output = complete_call.output
    output_refs = extract_refs_from_values(output)

    otel_dump_str = None
    if complete_call.otel_dump is not None:
        otel_dump_str = dict_value_to_dump(complete_call.otel_dump)

    return CallCompleteCHInsertable(
        project_id=complete_call.project_id,
        id=complete_call.id,
        trace_id=complete_call.trace_id,
        parent_id=complete_call.parent_id,
        thread_id=complete_call.thread_id,
        turn_id=complete_call.turn_id,
        op_name=complete_call.op_name,
        display_name=complete_call.display_name,
        started_at=complete_call.started_at,
        ended_at=complete_call.ended_at,
        exception=complete_call.exception,
        attributes_dump=dict_value_to_dump(complete_call.attributes),
        inputs_dump=dict_value_to_dump(inputs),
        input_refs=input_refs,
        output_dump=any_value_to_dump(output),
        summary_dump=dict_value_to_dump(dict(complete_call.summary)),
        otel_dump=otel_dump_str,
        output_refs=output_refs,
        wb_user_id=complete_call.wb_user_id,
        wb_run_id=complete_call.wb_run_id,
        wb_run_step=complete_call.wb_run_step,
        wb_run_step_end=complete_call.wb_run_step_end,
    )


def ch_call_dict_to_call_schema_dict(ch_call_dict: dict) -> dict:
    """Convert a CH call dict to a CallSchema dict."""
    summary = nullable_any_dump_to_any(ch_call_dict.get("summary_dump"))
    started_at = ensure_datetimes_have_tz(ch_call_dict.get("started_at"))
    ended_at = ensure_datetimes_have_tz(ch_call_dict.get("ended_at"))
    display_name = empty_str_to_none(ch_call_dict.get("display_name"))

    attributes = dict_dump_to_dict(ch_call_dict.get("attributes_dump", "{}"))

    if otel_dump := ch_call_dict.get("otel_dump"):
        attributes["otel_span"] = dict_dump_to_dict(otel_dump)

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
        "inputs": dict_dump_to_dict(ch_call_dict.get("inputs_dump", "{}")),
        "output": nullable_any_dump_to_any(ch_call_dict.get("output_dump")),
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


def ch_call_to_row(ch_call: CallCHInsertable) -> list[Any]:
    """Convert a CH insertable call to a row for batch insertion."""
    call_dict = ch_call.model_dump()
    return [call_dict.get(col) for col in ALL_CALL_INSERT_COLUMNS]


def maybe_enqueue_minimal_call_end(
    kafka_producer: "KafkaProducer",
    project_id: str,
    id: str,
    ended_at: datetime.datetime,
    flush_immediately: bool = False,
) -> None:
    """Enqueue a minimal call end event to Kafka if online eval is enabled."""
    from weave.trace_server import environment as wf_env

    if not wf_env.wf_enable_online_eval():
        return

    minimal_end = tsi.EndedCallSchemaForInsert(
        project_id=project_id,
        id=id,
        ended_at=ended_at,
        output=None,
        summary={},
        exception=None,
    )
    kafka_producer.produce_call_end(minimal_end, flush_immediately)


@ddtrace.tracer.wrap(name="calls.find_call_descendants")
def find_call_descendants(
    root_ids: list[str],
    all_calls: list[tsi.CallSchema],
) -> list[str]:
    """Find all descendants of the given root call IDs."""
    set_current_span_dd_tags(
        {
            "calls.find_call_descendants.root_ids_count": str(len(root_ids)),
            "calls.find_call_descendants.all_calls_count": str(len(all_calls)),
        }
    )
    children_map = defaultdict(list)
    for call in all_calls:
        if call.parent_id is not None:
            children_map[call.parent_id].append(call.id)

    def find_all_descendants(root_ids: list[str]) -> set[str]:
        descendants = set()
        stack = root_ids

        while stack:
            current_id = stack.pop()
            if current_id not in descendants:
                descendants.add(current_id)
                stack += children_map.get(current_id, [])

        return descendants

    descendants = find_all_descendants(root_ids)
    return list(descendants)
