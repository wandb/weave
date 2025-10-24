"""Tests for project version service integration with trace server."""

import datetime
import uuid

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
    externalize_trace_server,
)
from tests.trace_server.workers.evaluate_model_test_worker import (
    EvaluateModelTestDispatcher,
)
from weave.trace_server import clickhouse_trace_server_batched
from weave.trace_server import trace_server_interface as tsi

TEST_ENTITY = "test_entity"


def test_trace_server_accepts_project_version_resolver(ensure_clickhouse_db):
    """Test that ClickHouseTraceServer initializes with a ProjectVersionResolver."""
    host, port = next(ensure_clickhouse_db())
    id_converter = DummyIdConverter()

    # Test server creation
    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        host=host,
        port=port,
        evaluate_model_dispatcher=EvaluateModelTestDispatcher(
            id_converter=id_converter
        ),
    )
    ch_server._run_migrations()

    # Should have a ProjectVersionResolver initialized
    assert ch_server._project_version_service is not None
    assert hasattr(ch_server._project_version_service, "get_project_version_sync")


def test_trace_server_call_start_with_project_version(ensure_clickhouse_db):
    """Test that call_start operations work with project version routing."""
    host, port = next(ensure_clickhouse_db())
    id_converter = DummyIdConverter()

    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer(
        host=host,
        port=port,
        evaluate_model_dispatcher=EvaluateModelTestDispatcher(
            id_converter=id_converter
        ),
    )
    ch_server._run_migrations()

    external_server = externalize_trace_server(
        ch_server, TEST_ENTITY, id_converter=id_converter
    )

    # Create a call - should succeed regardless of project version
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id="test-project",
            id=call_id,
            op_name="test_op",
            trace_id=trace_id,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            attributes={},
            inputs={},
        )
    )
    result = external_server.call_start(req)

    # Should return valid response
    assert result is not None
