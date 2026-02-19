import datetime
from unittest.mock import Mock, patch

from weave.trace_server import sqlite_trace_server as slts
from weave.trace_server import trace_server_interface as tsi


def test_sqlite_calls_query_filter_by_thread_ids():
    """Test that calls_query applies thread_ids filter in the SQL WHERE clause."""
    with patch.object(slts, "get_conn_cursor") as mock_get_conn_cursor:
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_get_conn_cursor.return_value = (Mock(), mock_cursor)

        server = slts.SqliteTraceServer(":memory:")
        try:
            req = tsi.CallsQueryReq(
                project_id="test_project",
                filter=tsi.CallsFilter(thread_ids=["thread_a_abc", "thread_b_def"]),
                limit=100,
            )

            list(server.calls_query_stream(req))

            mock_cursor.execute.assert_called_once()
            sql = mock_cursor.execute.call_args[0][0]
            assert "thread_id IN ('thread_a_abc', 'thread_b_def')" in sql
        finally:
            server.close()


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
        try:
            # Call the method that generates the query and consume the generator
            list(server.calls_query_stream(req))

            # Verify that cursor.execute was called with the correct query
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            sql = call_args[0]
            print(sql)
            assert (
                "storage_size_bytes" in sql
            )  # Query should include storage_size_bytes
            assert (
                "total_storage_size_bytes" in sql
            )  # Query should include total_storage_size_bytes
        finally:
            server.close()


def test_sqlite_calls_query_empty_thread_ids_against_real_db():
    """Filter with thread_ids=[] against real SQLite: query runs and returns no rows.

    Empty thread_ids means "no threads", so no calls match. Uses an in-memory SQLite DB,
    inserts one call, then queries with thread_ids=[]; expects 0 results.
    """
    server = slts.SqliteTraceServer(":memory:")
    try:
        server.drop_tables()
        server.setup_tables()

        project_id = "p_empty_thread_test"
        call_id = "call_1"
        trace_id = "trace_1"
        now = datetime.datetime.now(datetime.timezone.utc)

        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    trace_id=trace_id,
                    op_name="test_op",
                    started_at=now,
                    attributes={},
                    inputs={},
                    thread_id="thread_xyz",
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id=call_id,
                    ended_at=now,
                    output=None,
                    summary={},
                )
            )
        )

        req = tsi.CallsQueryReq(
            project_id=project_id,
            filter=tsi.CallsFilter(thread_ids=[]),
            limit=10,
        )
        result = list(server.calls_query_stream(req))

        assert len(result) == 0
    finally:
        server.close()
