# ClickHouse OTel - OpenTelemetry export operations

from collections import defaultdict
from functools import partial
from typing import TYPE_CHECKING, Any

import ddtrace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

from weave.trace_server import object_creation_utils
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.batching import BatchManager
from weave.trace_server.clickhouse_query_layer.calls import (
    ch_call_to_row,
    end_call_for_insert_to_ch_insertable,
    maybe_enqueue_minimal_call_end,
    start_call_for_insert_to_ch_insertable,
)
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span
from weave.trace_server.project_version.project_version import TableRoutingResolver
from weave.trace_server.project_version.types import WriteTarget
from weave.trace_server.trace_server_interface_util import assert_non_null_wb_user_id

if TYPE_CHECKING:
    from weave.trace_server.kafka import KafkaProducer


class OtelRepository:
    """Repository for OpenTelemetry export operations."""

    def __init__(
        self,
        ch_client: ClickHouseClient,
        batch_manager: BatchManager,
        table_routing_resolver: TableRoutingResolver,
        kafka_producer_getter: "callable[[], KafkaProducer]",
        obj_create_batch_func: "callable[[list[tsi.ObjSchemaForInsert]], list[tsi.ObjCreateRes]]",
        get_existing_ops_func: "callable[[set[str], str, int], list[Any]]",
        create_placeholder_ops_digest_func: "callable[[str, bool], str]",
        file_create_func: "callable[[tsi.FileCreateReq], tsi.FileCreateRes]",
    ):
        self._ch_client = ch_client
        self._batch_manager = batch_manager
        self._table_routing_resolver = table_routing_resolver
        self._kafka_producer_getter = kafka_producer_getter
        self._obj_create_batch = obj_create_batch_func
        self._get_existing_ops = get_existing_ops_func
        self._create_placeholder_ops_digest = create_placeholder_ops_digest_func
        self._file_create = file_create_func

    @ddtrace.tracer.wrap(name="otel_repository.otel_export")
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        """Export OpenTelemetry traces to Weave."""
        assert_non_null_wb_user_id(req)

        if not isinstance(req.traces, ExportTraceServiceRequest):
            raise TypeError(
                f"Expected traces as ExportTraceServiceRequest, got {type(req.traces)}"
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
                        # Record and skip malformed spans
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

        existing_objects = self._get_existing_ops(
            seen_ids=set(obj_id_idx_map.keys()),
            project_id=req.project_id,
            limit=len(calls),
        )

        # Reuse existing placeholder file or create it once
        if len(existing_objects) == 0:
            digest = self._create_placeholder_ops_digest(
                project_id=req.project_id, create=True
            )
        else:
            digest = self._create_placeholder_ops_digest(
                project_id=req.project_id, create=False
            )

        for obj in existing_objects:
            op_ref_uri = ri.InternalOpRef(
                project_id=req.project_id,
                name=obj.object_id,
                version=obj.digest,
            ).uri()

            for idx in obj_id_idx_map[obj.object_id]:
                calls[idx][0].op_name = op_ref_uri
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
        res = self._obj_create_batch(obj_creation_batch)

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

        write_target = self._table_routing_resolver.resolve_v2_write_target(
            req.project_id,
            self._ch_client.ch_client,
        )
        if write_target == WriteTarget.CALLS_COMPLETE:
            write_target = WriteTarget.CALLS_MERGED

        # Convert calls to CH insertable format
        batch_rows = []
        event_callback_list = []
        for start_call, end_call in calls:
            ch_start = start_call_for_insert_to_ch_insertable(start_call)
            ch_end = end_call_for_insert_to_ch_insertable(end_call)
            batch_rows.append(ch_call_to_row(ch_start))
            batch_rows.append(ch_call_to_row(ch_end))
            event_callback_list.append(
                partial(
                    maybe_enqueue_minimal_call_end,
                    self._kafka_producer_getter(),
                    end_call.project_id,
                    end_call.id,
                    end_call.ended_at,
                    False,
                )
            )

        if write_target == WriteTarget.CALLS_MERGED:
            # Insert directly without async_insert for OTEL calls
            self._batch_manager.insert_call_batch(
                batch_rows, settings=None, do_sync_insert=True
            )
            # Run callbacks and flush
            for cb in event_callback_list:
                cb()
            self._flush_kafka_producer()

        if rejected_spans > 0:
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

    def _flush_kafka_producer(self) -> None:
        """Flush Kafka producer if online eval is enabled."""
        from weave.trace_server import environment as wf_env

        if wf_env.wf_enable_online_eval():
            self._kafka_producer_getter().flush()
