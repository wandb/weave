from unittest.mock import Mock, patch

from weave.trace_server import sqlite_trace_server as slts
from weave.trace_server import trace_server_interface as tsi


def test_sqlite_storage_size_query_generation():
    """Test that SQLite storage size query generation works correctly."""
    # Mock the query builder and cursor.execute
    with patch.object(slts, "get_conn_cursor") as mock_get_conn_cursor:
        # Mock cursor and connection
        mock_cursor = Mock()
        mock_get_conn_cursor.return_value = (Mock(), mock_cursor)

        # Mock cursor.fetchall() return value
        mock_cursor.fetchall.return_value = []

        # Create a request with storage size fields
        req = tsi.CallsQueryReq(
            project_id="test_project",
            include_storage_size=True,
            include_total_storage_size=True,
        )

        # Create server instance
        server = slts.SqliteTraceServer("test.db")

        # Call the method that generates the query and consume the generator
        list(server.calls_query_stream(req))

        # Verify that cursor.execute was called with the correct query
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        sql = call_args[0]
        print(sql)
        assert "storage_size_bytes" in sql  # Query should include storage_size_bytes
        assert (
            "total_storage_size_bytes" in sql
        )  # Query should include total_storage_size_bytes
