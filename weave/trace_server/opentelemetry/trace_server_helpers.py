from collections import defaultdict
from typing import NamedTuple

from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans

from weave.shared import refs_internal as ri
from weave.shared.digest import compute_file_digest
from weave.trace_server import object_creation_utils
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.opentelemetry.helpers import AttributePathConflictError
from weave.trace_server.opentelemetry.python_spans import Resource, Span

CallPair = tuple[tsi.StartedCallSchemaForInsert, tsi.EndedCallSchemaForInsert]


class OtelSpanProcessingResult(NamedTuple):
    calls: list[CallPair]
    rejected_spans: int
    error_messages: list[str]


class OtelOpResolutionResult(NamedTuple):
    obj_creation_batch: list[tsi.ObjSchemaForInsert]
    obj_id_idx_map: dict[str, list[int]]


def process_otel_spans_to_calls(
    req: tsi.OTelExportReq,
) -> OtelSpanProcessingResult:
    """Convert OTel proto spans to Weave call tuples."""
    calls: list[CallPair] = []
    rejected_spans = 0
    error_messages: list[str] = []
    for processed_span in req.processed_spans:
        wb_run_id = processed_span.run_id

        if not isinstance(processed_span.resource_spans, ResourceSpans):
            raise TypeError(
                f"Expected resource_spans as ResourceSpans, got {type(processed_span.resource_spans)}"
            )

        proto_resource_spans = processed_span.resource_spans
        resource = Resource.from_proto(proto_resource_spans.resource)
        for proto_scope_spans in proto_resource_spans.scope_spans:
            for proto_span in proto_scope_spans.spans:
                try:
                    span = Span.from_proto(proto_span, resource)
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
                    continue

                calls.append(
                    span.to_call(
                        req.project_id,
                        wb_user_id=req.wb_user_id,
                        wb_run_id=wb_run_id,
                    )
                )

    return OtelSpanProcessingResult(calls, rejected_spans, error_messages)


def resolve_and_prepare_new_otel_ops(
    calls: list[CallPair],
    project_id: str,
    wb_user_id: str | None,
    existing_ops: dict[str, str],
    trace_server: tsi.TraceServerInterface,
) -> OtelOpResolutionResult:
    """Resolve existing ops and prepare batch for new op creation.

    Applies existing op refs to calls in-place, creates the placeholder ops
    file if needed, and builds the batch of new ops to be created.

    Args:
        calls: List of (start, end) call tuples. Modified in-place.
        project_id: Project ID.
        wb_user_id: User ID for new ops.
        existing_ops: Map of op_name -> op_ref_uri from cache/lookup.
        trace_server: Trace server instance for file_create.

    Returns:
        OtelOpResolutionResult with obj_creation_batch for new ops to create,
        and obj_id_idx_map containing only the new (not yet created) op names.
    """
    obj_id_idx_map: dict[str, list[int]] = defaultdict(list)
    for idx, (start_call, _) in enumerate(calls):
        op_name = object_creation_utils.make_safe_name(start_call.op_name)
        obj_id_idx_map[op_name].append(idx)

    for op_name, op_ref_uri in existing_ops.items():
        for idx in obj_id_idx_map[op_name]:
            calls[idx][0].op_name = op_ref_uri
        obj_id_idx_map.pop(op_name)

    # OTel always uses the placeholder source. Reuse existing file if we know
    # ops already exist, otherwise create it.
    if len(existing_ops) == 0:
        digest = _create_placeholder_ops_digest(project_id, trace_server)
    else:
        digest = compute_file_digest(
            (object_creation_utils.PLACEHOLDER_OP_SOURCE).encode("utf-8")
        )

    obj_creation_batch = []
    for op_obj_id in obj_id_idx_map.keys():
        op_val = object_creation_utils.build_op_val(digest)
        obj_creation_batch.append(
            tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id=op_obj_id,
                val=op_val,
                wb_user_id=wb_user_id,
            )
        )

    return OtelOpResolutionResult(obj_creation_batch, obj_id_idx_map)


def apply_created_ops_to_calls(
    obj_id_idx_map: dict[str, list[int]],
    calls: list[CallPair],
    create_results: list[tsi.ObjCreateRes],
    project_id: str,
) -> list[tuple[str, str]]:
    """Apply newly created op refs to calls.

    Args:
        obj_id_idx_map: Map of op_name -> call indices for new ops.
        calls: List of (start, end) call tuples. Modified in-place.
        create_results: Results from obj_create_batch.
        project_id: Project ID.

    Returns:
        List of (op_name, op_ref_uri) tuples for the caller to cache.
    """
    new_ops: list[tuple[str, str]] = []
    for result in create_results:
        if result.object_id is None:
            raise RuntimeError("Otel Export - Expected object_id but got None")

        op_ref_uri = ri.InternalOpRef(
            project_id=project_id,
            name=result.object_id,
            version=result.digest,
        ).uri()
        for idx in obj_id_idx_map[result.object_id]:
            calls[idx][0].op_name = op_ref_uri
        new_ops.append((result.object_id, op_ref_uri))

    return new_ops


def build_otel_export_response(
    rejected_spans: int,
    error_messages: list[str],
) -> tsi.OTelExportRes:
    """Build the OTel export response with optional partial success info."""
    if rejected_spans > 0:
        joined_errors = "; ".join(error_messages[:20]) + (
            "; ..." if len(error_messages) > 20 else ""
        )
        return tsi.OTelExportRes(
            partial_success=tsi.ExportTracePartialSuccess(
                rejected_spans=rejected_spans,
                error_message=joined_errors,
            )
        )
    return tsi.OTelExportRes()


def _create_placeholder_ops_digest(
    project_id: str,
    trace_server: tsi.TraceServerInterface,
) -> str:
    """Create the placeholder op source file and return its digest."""
    source_code = object_creation_utils.PLACEHOLDER_OP_SOURCE
    source_file_req = tsi.FileCreateReq(
        project_id=project_id,
        name=object_creation_utils.OP_SOURCE_FILE_NAME,
        content=source_code.encode("utf-8"),
    )
    return trace_server.file_create(source_file_req).digest
