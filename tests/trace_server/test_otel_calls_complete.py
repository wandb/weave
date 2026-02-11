"""Tests for OTel export integration with calls_complete table routing.

These tests verify that OTel export correctly routes calls to either
calls_complete or calls_merged based on project data residence.

Key scenarios:
1. Empty project -> OTel writes to calls_complete
2. Project with calls_merged data -> OTel writes to calls_merged
3. Project with calls_complete data -> OTel writes to calls_complete
4. V1 API (call_start/call_end) raises error for calls_complete projects

These tests should FAIL when the OTel calls_complete write path is disabled
(i.e., when otel_export always falls back to calls_merged).
"""

import datetime
import uuid
from binascii import hexlify

import pytest
from opentelemetry.proto.common.v1.common_pb2 import (
    InstrumentationScope,
    KeyValue,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import (
    ResourceSpans,
    ScopeSpans,
    Span,
)

from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.errors import CallsCompleteModeRequired
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """Get internal ClickHouse server with AUTO routing mode enabled."""
    internal_server = trace_server._internal_trace_server
    if isinstance(internal_server, SqliteTraceServer):
        pytest.skip("ClickHouse-only test")
    internal_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return internal_server


# =============================================================================
# Helpers
# =============================================================================


def _count_project_rows(ch_client, table: str, project_id: str) -> int:
    """Count rows for a project in a ClickHouse table."""
    pb = ParamBuilder()
    project_param = pb.add_param(project_id)
    project_slot = param_slot(project_param, "String")
    query = f"SELECT count() FROM {table} WHERE project_id = {project_slot}"
    return ch_client.query(query, parameters=pb.get_params()).result_rows[0][0]


def _insert_merged_call(ch_client, project_id: str) -> str:
    """Insert a minimal row into calls_merged to establish residence."""
    call_id = str(uuid.uuid4())
    ch_client.command(
        f"""
        INSERT INTO calls_merged (
            project_id, id, op_name, started_at, trace_id, parent_id,
            attributes_dump, inputs_dump, output_dump, summary_dump
        ) VALUES (
            '{project_id}', '{call_id}', 'seed_op', now(), '{uuid.uuid4()}', '',
            '{{}}', '{{}}', 'null', '{{}}'
        )
        """
    )
    return call_id


def _insert_complete_call(ch_client, project_id: str) -> str:
    """Insert a minimal row into calls_complete to establish residence."""
    call_id = str(uuid.uuid4())
    ch_client.command(
        f"""
        INSERT INTO calls_complete (
            project_id, id, op_name, started_at, ended_at, trace_id, parent_id,
            attributes_dump, inputs_dump, output_dump, summary_dump
        ) VALUES (
            '{project_id}', '{call_id}', 'seed_op', now(), now(), '{uuid.uuid4()}', '',
            '{{}}', '{{}}', 'null', '{{}}'
        )
        """
    )
    return call_id


def _create_otel_span(name: str = "test_span") -> Span:
    """Create a minimal OTel span for testing."""
    span = Span()
    span.name = name
    span.trace_id = uuid.uuid4().bytes
    span.span_id = uuid.uuid4().bytes[:8]
    span.start_time_unix_nano = int(datetime.datetime.now().timestamp() * 1_000_000_000)
    span.end_time_unix_nano = span.start_time_unix_nano + 1_000_000_000
    span.kind = 1  # INTERNAL

    # Add a basic attribute
    kv = KeyValue()
    kv.key = "test.attr"
    kv.value.string_value = "test_value"
    span.attributes.append(kv)

    return span


def _create_otel_export_req(
    project_id: str, spans: list[Span] | None = None
) -> tsi.OTelExportReq:
    """Create an OTelExportReq with the given spans."""
    if spans is None:
        spans = [_create_otel_span()]

    scope = InstrumentationScope()
    scope.name = "test"
    scope.version = "1.0"

    scope_spans = ScopeSpans()
    scope_spans.scope.CopyFrom(scope)
    for span in spans:
        scope_spans.spans.append(span)

    resource = Resource()
    kv = KeyValue()
    kv.key = "service.name"
    kv.value.string_value = "test_service"
    resource.attributes.append(kv)

    resource_spans = ResourceSpans()
    resource_spans.resource.CopyFrom(resource)
    resource_spans.scope_spans.append(scope_spans)

    processed = tsi.ProcessedResourceSpans(
        entity=TEST_ENTITY,
        project=project_id.split("/")[-1],
        run_id=None,
        resource_spans=resource_spans,
    )

    return tsi.OTelExportReq(
        project_id=project_id, processed_spans=[processed], wb_user_id="test_user"
    )


def _fetch_calls_stream(trace_server, project_id: str) -> list[tsi.CallSchema]:
    """Fetch all calls for a project via streaming."""
    return list(
        trace_server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))
    )


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.parametrize(
    ("suffix", "seed_complete", "seed_merged", "expect_complete", "expect_merged"),
    [
        # Empty project: OTel should write to calls_complete
        ("otel_empty", 0, 0, 1, 0),
        # calls_complete only: OTel should write to calls_complete
        ("otel_complete_only", 1, 0, 2, 0),
        # calls_merged only: OTel should write to calls_merged (keep data together)
        ("otel_merged_only", 0, 1, 0, 2),
    ],
)
def test_otel_export_routing_by_residence(
    trace_server,
    clickhouse_trace_server,
    suffix: str,
    seed_complete: int,
    seed_merged: int,
    expect_complete: int,
    expect_merged: int,
):
    """OTel export routes to correct table based on project data residence.

    This test will FAIL when OTel always writes to calls_merged (fallback behavior).
    It will PASS when OTel respects the write_target from resolve_v2_write_target.
    """
    project_id = f"{TEST_ENTITY}/{suffix}"
    internal_project_id = b64(project_id)

    # Seed the project with existing data if needed
    for _ in range(seed_merged):
        _insert_merged_call(clickhouse_trace_server.ch_client, internal_project_id)
    for _ in range(seed_complete):
        _insert_complete_call(clickhouse_trace_server.ch_client, internal_project_id)

    # Export OTel span
    req = _create_otel_export_req(project_id)
    res = trace_server.otel_export(req)
    assert isinstance(res, tsi.OTelExportRes)
    assert res.partial_success is None  # No errors

    # Verify row counts in each table
    complete_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    merged_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
    )
    assert complete_count == expect_complete, (
        f"Expected {expect_complete} in calls_complete, got {complete_count}"
    )
    assert merged_count == expect_merged, (
        f"Expected {expect_merged} in calls_merged, got {merged_count}"
    )

    # Verify the call is readable
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) >= 1


def test_otel_export_establishes_residence_for_subsequent_calls(
    trace_server, clickhouse_trace_server
):
    """OTel export to empty project establishes calls_complete residence.

    After OTel writes to calls_complete, subsequent V2 API calls should also
    go to calls_complete, and V1 API should raise CallsCompleteModeRequired.
    """
    project_id = f"{TEST_ENTITY}/otel_establishes_residence"
    internal_project_id = b64(project_id)

    # OTel export to empty project -> should go to calls_complete
    otel_req = _create_otel_export_req(project_id)
    trace_server.otel_export(otel_req)

    # This assertion will FAIL if OTel writes to calls_merged instead
    complete_after_otel = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    assert complete_after_otel == 1, (
        f"OTel should write to calls_complete for empty project, got {complete_after_otel}"
    )

    # V2 API call should also go to calls_complete (residence established)
    call_id = str(uuid.uuid4())
    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=str(uuid.uuid4()),
                op_name="v2_op",
                started_at=datetime.datetime.now(datetime.timezone.utc),
                attributes={},
                inputs={},
            )
        )
    )

    complete_after_v2 = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    assert complete_after_v2 == 2, "V2 call should go to calls_complete"

    # V1 API should raise error since project is now calls_complete mode
    with pytest.raises(CallsCompleteModeRequired):
        trace_server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    trace_id=str(uuid.uuid4()),
                    op_name="v1_op",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )


def test_otel_export_multiple_spans_batch(trace_server, clickhouse_trace_server):
    """OTel export handles multiple spans in a single batch correctly."""
    project_id = f"{TEST_ENTITY}/otel_batch"
    internal_project_id = b64(project_id)

    # Create multiple spans
    spans = [_create_otel_span(f"span_{i}") for i in range(3)]
    req = _create_otel_export_req(project_id, spans)
    trace_server.otel_export(req)

    # For empty project, all should go to calls_complete
    complete_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    merged_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_merged", internal_project_id
    )

    # This will FAIL if OTel writes to calls_merged
    assert complete_count == 3, f"Expected 3 in calls_complete, got {complete_count}"
    assert merged_count == 0, f"Expected 0 in calls_merged, got {merged_count}"

    # Verify all calls are readable
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 3


def test_otel_export_data_integrity(trace_server, clickhouse_trace_server):
    """OTel export preserves span data when writing to calls_complete."""
    project_id = f"{TEST_ENTITY}/otel_data_integrity"

    # Create span with specific attributes
    span = _create_otel_span("integrity_test")

    # Add custom attributes
    kv = KeyValue()
    kv.key = "custom.value"
    kv.value.int_value = 42
    span.attributes.append(kv)

    span_id = hexlify(span.span_id).decode("ascii")
    trace_id = hexlify(span.trace_id).decode("ascii")

    req = _create_otel_export_req(project_id, [span])
    trace_server.otel_export(req)

    # Verify data is preserved in calls_complete path
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 1

    call = calls[0]
    assert call.id == span_id
    assert call.trace_id == trace_id
    # OTel spans get transformed to op refs like weave:///entity/project/op/name:hash
    assert "integrity_test" in call.op_name
    assert "custom" in call.attributes
    assert call.attributes["custom"]["value"] == 42


def test_v1_api_raises_error_for_otel_established_project(
    trace_server, clickhouse_trace_server
):
    """V1 call_start and call_end raise CallsCompleteModeRequired for OTel projects.

    When OTel has established a project as calls_complete mode, legacy V1 APIs
    should fail with a clear error message directing users to upgrade.
    """
    project_id = f"{TEST_ENTITY}/otel_v1_error"

    # OTel establishes project in calls_complete mode
    req = _create_otel_export_req(project_id)
    trace_server.otel_export(req)

    # This will only fail if OTel wrote to calls_complete (not calls_merged)
    # V1 call_start should raise
    with pytest.raises(CallsCompleteModeRequired) as exc_info:
        trace_server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    trace_id=str(uuid.uuid4()),
                    op_name="v1_op",
                    started_at=datetime.datetime.now(datetime.timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
    assert "complete" in str(exc_info.value).lower()

    # V1 call_end should also raise
    with pytest.raises(CallsCompleteModeRequired):
        trace_server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=str(uuid.uuid4()),
                    ended_at=datetime.datetime.now(datetime.timezone.utc),
                    summary={"usage": {}, "status_counts": {}},
                )
            )
        )


def test_otel_and_calls_complete_api_interoperability(
    trace_server, clickhouse_trace_server
):
    """OTel export and calls_complete API can coexist on the same project."""
    project_id = f"{TEST_ENTITY}/otel_api_interop"
    internal_project_id = b64(project_id)

    # Start with OTel export
    otel_req = _create_otel_export_req(project_id)
    trace_server.otel_export(otel_req)

    # Add via calls_complete API
    api_call = tsi.CompletedCallSchemaForInsert(
        project_id=project_id,
        id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        op_name="api_op",
        started_at=datetime.datetime.now(datetime.timezone.utc),
        ended_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=1),
        attributes={},
        inputs={},
        summary={"usage": {}, "status_counts": {}},
    )
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=[api_call]))

    # Both should be in calls_complete
    complete_count = _count_project_rows(
        clickhouse_trace_server.ch_client, "calls_complete", internal_project_id
    )
    assert complete_count == 2, f"Expected 2 in calls_complete, got {complete_count}"

    # Both should be readable
    calls = _fetch_calls_stream(trace_server, project_id)
    assert len(calls) == 2
    op_names = {c.op_name for c in calls}
    # OTel spans get transformed to op refs, API calls keep original name
    assert any("test_span" in name for name in op_names)
    assert "api_op" in op_names
