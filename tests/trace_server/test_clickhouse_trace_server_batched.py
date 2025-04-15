from datetime import datetime, timezone
from unittest.mock import Mock, patch

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import trace_server_interface as tsi


def test_clickhouse_storage_size_query_generation():
    """Test that ClickHouse storage size query generation works correctly."""
    # Mock the query builder and query stream
    with (
        patch(
            "weave.trace_server.clickhouse_trace_server_batched.CallsQuery",
            autospec=True,
        ) as mock_cq,
        patch.object(chts.ClickHouseTraceServer, "_query_stream") as mock_query_stream,
    ):
        # Create a mock CallsQuery instance
        mock_calls_query = Mock()
        # Mock the CallsQuery class to return our mock instance
        mock_cq.return_value = mock_calls_query

        # Mock the query stream to return empty list
        mock_query_stream.return_value = []
        # Mock the select_fields property to return an empty columns list
        mock_calls_query.select_fields = []

        # Create a request with storage size fields
        req = tsi.CallsQueryReq(
            project_id="test_project",
            include_storage_size=True,
            include_total_storage_size=True,
        )

        # Create server instance
        server = chts.ClickHouseTraceServer(host="test_host")

        # Call the method that generates the query and consume the generator
        list(server.calls_query_stream(req))

        # Verify that storage size fields were added
        mock_calls_query.add_field.assert_any_call("storage_size_bytes")
        mock_calls_query.add_field.assert_any_call("total_storage_size_bytes")

        # Verify that _query_stream was called once
        mock_query_stream.assert_called_once()
        call_args = mock_query_stream.call_args[0]
        assert (
            call_args[0] == mock_calls_query.as_sql()
        )  # First argument should be the query
        # with mocks, we don't have any params generated
        assert call_args[1] == {}  # Second argument should be project_id


def test_clickhouse_storage_size_schema_conversion():
    """Test that storage size fields are correctly converted in ClickHouse schema."""
    # Test data with proper datetime structures
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ended_at = datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    test_data = {
        "storage_size_bytes": 1000,
        "total_storage_size_bytes": 2000,
        "id": "test_id",
        "name": "test_name",
        "project_id": "test_project",
        "trace_id": "test_trace",
        "parent_id": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "inputs": {},
        "outputs": {},
        "error": None,
        "summary": None,
        "summary_dump": None,
        "cost": None,
        "wb_run_id": None,
        "wb_user_id": None,
    }

    # Test ClickHouse conversion
    ch_schema = chts._ch_call_dict_to_call_schema_dict(test_data)
    assert ch_schema["storage_size_bytes"] == 1000
    assert ch_schema["total_storage_size_bytes"] == 2000


def test_clickhouse_storage_size_null_handling():
    """Test that NULL values in storage size fields are handled correctly in ClickHouse."""
    # Test data with NULL values and proper datetime structures
    started_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ended_at = datetime(2024, 1, 1, 0, 1, 0, tzinfo=timezone.utc)
    test_data = {
        "storage_size_bytes": None,
        "total_storage_size_bytes": None,
        "id": "test_id",
        "name": "test_name",
        "project_id": "test_project",
        "trace_id": "test_trace",
        "parent_id": None,
        "started_at": started_at,
        "ended_at": ended_at,
        "inputs": {},
        "outputs": {},
        "error": None,
        "summary": None,
        "summary_dump": None,
        "cost": None,
        "wb_run_id": None,
        "wb_user_id": None,
    }

    # Test ClickHouse conversion
    ch_schema = chts._ch_call_dict_to_call_schema_dict(test_data)
    assert ch_schema["storage_size_bytes"] is None
    assert ch_schema["total_storage_size_bytes"] is None
