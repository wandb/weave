"""Tests for dual write constraints and table routing with OTEL and normal spans.

These tests verify that:
1. OTEL spans are always written only to calls_merged (no dual write)
2. Normal spans follow the write_target routing (can dual write with WriteTarget.BOTH)
3. When WriteTarget.BOTH, we never write to only one table (data consistency)
"""

import base64
import uuid
from datetime import datetime

import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
)

from tests.trace.util import client_is_sqlite
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.opentelemetry.python_spans import StatusCode
from weave.trace_server.project_version.clickhouse_project_version import (
    get_project_data_residence,
)
from weave.trace_server.project_version.types import (
    CallsStorageServerMode,
    ProjectDataResidence,
)


def make_project_id(name: str) -> str:
    """Create a project ID from a name."""
    return base64.b64encode(f"test_entity/{name}".encode()).decode()


def count_calls_in_table(ch_client, table: str, project_id: str) -> int:
    """Count the number of calls in a specific table for a project."""
    result = ch_client.query(
        f"SELECT COUNT(*) as count FROM {table} WHERE project_id = %(project_id)s",
        {"project_id": project_id},
    )
    return result.result_rows[0][0] if result.result_rows else 0


def create_otel_span(name: str = "test_otel_span") -> Span:
    """Create a test OpenTelemetry Span."""
    span = Span()
    span.name = name
    span.trace_id = uuid.uuid4().bytes
    span.span_id = uuid.uuid4().bytes[:8]
    span.start_time_unix_nano = int(datetime.now().timestamp() * 1_000_000_000)
    span.end_time_unix_nano = span.start_time_unix_nano + 1_000_000_000  # 1 second
    span.kind = 1  # type: ignore

    # Add some test attributes
    kv1 = KeyValue()
    kv1.key = "test.attribute"
    kv1.value.string_value = "test_value"
    span.attributes.append(kv1)

    # Set status
    span.status.code = StatusCode.OK.value  # type: ignore
    span.status.message = "Success"

    return span


def create_otel_export_request(
    project_id: str, span_name: str = "test_otel_span"
) -> tsi.OtelExportReq:
    """Create an OTEL export request with a test span."""
    span = create_otel_span(span_name)

    # Create resource with attributes
    resource = Resource()
    kv = KeyValue()
    kv.key = "service.name"
    kv.value.string_value = "test_service"
    resource.attributes.append(kv)

    # Create scope spans
    scope_spans = ScopeSpans()
    scope_spans.spans.append(span)

    # Create resource spans
    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(resource)
    resource_spans.scope_spans.append(scope_spans)

    # Create export request
    request = ExportTraceServiceRequest()
    request.resource_spans.append(resource_spans)

    wb_user_id = base64.b64encode(b"test_user").decode()
    return tsi.OtelExportReq(
        project_id=project_id, traces=request, wb_user_id=wb_user_id
    )


@pytest.mark.skip_clickhouse_client
def test_otel_then_normal_spans_dual_write_mode(client, trace_server):
    """Test that OTEL spans go only to calls_merged, then normal spans follow routing."""
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    resolver._mode = CallsStorageServerMode.DUAL_WRITE_READ_MERGED

    project_id = make_project_id(f"otel_then_normal_{uuid.uuid4().hex[:8]}")

    # Step 1: OTEL span writes to calls_merged only
    otel_req = create_otel_export_request(project_id, "otel_span_1")
    response = ch_server.otel_export(otel_req)
    assert isinstance(response, tsi.OtelExportRes)

    merged_count = count_calls_in_table(ch_server.ch_client, "calls_merged", project_id)
    complete_count = count_calls_in_table(
        ch_server.ch_client, "calls_complete", project_id
    )

    assert merged_count == 1, f"Expected 1 call in calls_merged, got {merged_count}"
    assert complete_count == 0, (
        f"Expected 0 calls in calls_complete (OTEL should not dual write), got {complete_count}"
    )

    residence = get_project_data_residence(project_id, ch_server.ch_client)
    assert residence == ProjectDataResidence.MERGED_ONLY, (
        f"Expected MERGED_ONLY, got {residence}"
    )

    # Step 2: Normal span stays in calls_merged (MERGED_ONLY residence)
    wb_user_id = base64.b64encode(b"test_user").decode()
    call_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=str(uuid.uuid4()),
                        op_name="test_op",
                        started_at=datetime.now(),
                        trace_id=str(uuid.uuid4()),
                        wb_user_id=wb_user_id,
                        attributes={},
                        inputs={},
                    )
                )
            )
        ],
    )
    ch_server.calls_start_batch(call_req)

    merged_count_after = count_calls_in_table(
        ch_server.ch_client, "calls_merged", project_id
    )
    complete_count_after = count_calls_in_table(
        ch_server.ch_client, "calls_complete", project_id
    )

    assert merged_count_after == 2, (
        f"Expected 2 calls in calls_merged, got {merged_count_after}"
    )
    assert complete_count_after == 0, (
        f"Expected 0 calls in calls_complete (residence is MERGED_ONLY), got {complete_count_after}"
    )


@pytest.mark.skip_clickhouse_client
def test_normal_then_otel_spans_dual_write_mode(client, trace_server):
    """Test that normal spans follow routing, then OTEL spans go only to calls_merged."""
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    resolver._mode = CallsStorageServerMode.DUAL_WRITE_READ_MERGED

    project_id = make_project_id(f"normal_then_otel_{uuid.uuid4().hex[:8]}")

    # Step 1: Normal span dual writes for empty project
    wb_user_id = base64.b64encode(b"test_user").decode()
    call_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=str(uuid.uuid4()),
                        op_name="test_op",
                        started_at=datetime.now(),
                        trace_id=str(uuid.uuid4()),
                        wb_user_id=wb_user_id,
                        attributes={},
                        inputs={},
                    )
                )
            )
        ],
    )
    ch_server.calls_start_batch(call_req)

    merged_count = count_calls_in_table(ch_server.ch_client, "calls_merged", project_id)
    complete_count = count_calls_in_table(
        ch_server.ch_client, "calls_complete", project_id
    )

    assert merged_count == 1, f"Expected 1 call in calls_merged, got {merged_count}"
    assert complete_count == 1, (
        f"Expected 1 call in calls_complete (dual write), got {complete_count}"
    )

    residence = get_project_data_residence(project_id, ch_server.ch_client)
    assert residence == ProjectDataResidence.BOTH, f"Expected BOTH, got {residence}"

    # Step 2: OTEL span writes to calls_merged only
    otel_req = create_otel_export_request(project_id, "otel_span_1")
    response = ch_server.otel_export(otel_req)
    assert isinstance(response, tsi.OtelExportRes)

    merged_count_after = count_calls_in_table(
        ch_server.ch_client, "calls_merged", project_id
    )
    complete_count_after = count_calls_in_table(
        ch_server.ch_client, "calls_complete", project_id
    )

    assert merged_count_after == 2, (
        f"Expected 2 calls in calls_merged, got {merged_count_after}"
    )
    assert complete_count_after == 1, (
        f"Expected 1 call in calls_complete (OTEL should not write here), got {complete_count_after}"
    )

    residence_after = get_project_data_residence(project_id, ch_server.ch_client)
    assert residence_after == ProjectDataResidence.BOTH, (
        f"Expected BOTH, got {residence_after}"
    )


@pytest.mark.skip_clickhouse_client
def test_dual_write_constraint_enforcement(client, trace_server):
    """Test that WriteTarget.BOTH enforces dual write to both tables."""
    if client_is_sqlite(client):
        pytest.skip("ClickHouse-only test")

    ch_server = trace_server._internal_trace_server
    resolver = ch_server.table_routing_resolver
    resolver._mode = CallsStorageServerMode.DUAL_WRITE_READ_MERGED

    project_id = make_project_id(f"constraint_test_{uuid.uuid4().hex[:8]}")

    # Step 1: First span establishes BOTH residence
    wb_user_id = base64.b64encode(b"test_user").decode()
    call_req = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=str(uuid.uuid4()),
                        op_name="test_op",
                        started_at=datetime.now(),
                        trace_id=str(uuid.uuid4()),
                        wb_user_id=wb_user_id,
                        attributes={},
                        inputs={},
                    )
                )
            )
        ],
    )
    ch_server.calls_start_batch(call_req)

    residence = get_project_data_residence(project_id, ch_server.ch_client)
    assert residence == ProjectDataResidence.BOTH

    # Step 2: Second span continues dual writing
    call_req2 = tsi.CallsStartBatchReq(
        project_id=project_id,
        batch=[
            tsi.CallBatchStartMode(
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=str(uuid.uuid4()),
                        op_name="test_op_2",
                        started_at=datetime.now(),
                        trace_id=str(uuid.uuid4()),
                        wb_user_id=wb_user_id,
                        attributes={},
                        inputs={},
                    )
                )
            )
        ],
    )
    ch_server.calls_start_batch(call_req2)

    merged_count = count_calls_in_table(ch_server.ch_client, "calls_merged", project_id)
    complete_count = count_calls_in_table(
        ch_server.ch_client, "calls_complete", project_id
    )

    assert merged_count == 2, f"Expected 2 calls in calls_merged, got {merged_count}"
    assert complete_count == 2, (
        f"Expected 2 calls in calls_complete, got {complete_count}"
    )
