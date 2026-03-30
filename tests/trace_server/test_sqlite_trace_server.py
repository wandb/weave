import datetime
import json
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


def _make_server_with_call(
    project_id: str = "test_project",
    call_id: str = "call_1",
    trace_id: str = "trace_1",
    parent_id: str | None = None,
    attributes: dict | None = None,
    inputs: dict | None = None,
    output: dict | None = None,
    summary: dict | None = None,
    thread_id: str | None = None,
) -> tuple[slts.SqliteTraceServer, str]:
    """Helper: create an in-memory SQLite server, insert one completed call, return (server, call_id)."""
    server = slts.SqliteTraceServer(":memory:")
    server.drop_tables()
    server.setup_tables()

    now = datetime.datetime.now(datetime.timezone.utc)
    server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=trace_id,
                parent_id=parent_id,
                op_name="test_op",
                started_at=now,
                attributes=attributes or {},
                inputs=inputs or {},
                thread_id=thread_id,
            )
        )
    )
    server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=now,
                output=output,
                summary=summary or {},
            )
        )
    )
    return server, call_id


def test_sqlite_storage_size_bytes_populated_on_call_end():
    """storage_size_bytes column is populated when a call is started then ended."""
    server, call_id = _make_server_with_call(
        attributes={"key": "value"},
        inputs={"prompt": "hello world"},
        output={"result": "goodbye"},
        summary={"tokens": 10},
    )
    try:
        result = server.calls_query(
            tsi.CallsQueryReq(
                project_id="test_project",
                include_storage_size=True,
            )
        )
        assert len(result.calls) == 1
        call = result.calls[0]
        assert call.storage_size_bytes is not None
        assert call.storage_size_bytes > 0

        # Verify the value matches the expected sum of JSON-serialized field lengths
        expected = (
            len(json.dumps({"key": "value"}))
            + len(json.dumps({"prompt": "hello world"}))
            + len(json.dumps({"result": "goodbye"}))
            + len(json.dumps({"tokens": 10}))
        )
        assert call.storage_size_bytes == expected
    finally:
        server.close()


def test_sqlite_storage_size_bytes_populated_via_calls_complete():
    """storage_size_bytes is populated when using the calls_complete path."""
    server = slts.SqliteTraceServer(":memory:")
    server.drop_tables()
    server.setup_tables()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        attrs = {"model": "gpt-4"}
        inputs = {"prompt": "test"}
        output = {"response": "ok"}
        summary = {"latency": 0.5}
        server.calls_complete(
            tsi.CallsUpsertCompleteReq(
                project_id="test_project",
                batch=[
                    tsi.CompletedCallSchemaForInsert(
                        project_id="test_project",
                        id="call_complete_1",
                        trace_id="trace_1",
                        op_name="test_op",
                        started_at=now,
                        ended_at=now,
                        attributes=attrs,
                        inputs=inputs,
                        output=output,
                        summary=summary,
                    )
                ],
            )
        )

        result = server.calls_query(
            tsi.CallsQueryReq(
                project_id="test_project",
                include_storage_size=True,
            )
        )
        assert len(result.calls) == 1

        expected = (
            len(json.dumps(attrs))
            + len(json.dumps(inputs))
            + len(json.dumps(output))
            + len(json.dumps(summary))
        )
        assert result.calls[0].storage_size_bytes == expected
    finally:
        server.close()


def test_sqlite_storage_size_bytes_not_returned_without_flag():
    """storage_size_bytes is None when include_storage_size is not set."""
    server, _ = _make_server_with_call(
        inputs={"x": 1},
        output={"y": 2},
    )
    try:
        result = server.calls_query(
            tsi.CallsQueryReq(
                project_id="test_project",
                include_storage_size=False,
            )
        )
        assert len(result.calls) == 1
        assert result.calls[0].storage_size_bytes is None
    finally:
        server.close()


def test_sqlite_total_storage_size_bytes_aggregates_trace():
    """total_storage_size_bytes sums storage across all calls in a trace."""
    server = slts.SqliteTraceServer(":memory:")
    server.drop_tables()
    server.setup_tables()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        trace_id = "trace_shared"
        project_id = "test_project"

        # Root call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="root_call",
                    trace_id=trace_id,
                    op_name="root",
                    started_at=now,
                    attributes={"a": 1},
                    inputs={"b": 2},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="root_call",
                    ended_at=now,
                    output={"c": 3},
                    summary={"d": 4},
                )
            )
        )

        # Child call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="child_call",
                    trace_id=trace_id,
                    parent_id="root_call",
                    op_name="child",
                    started_at=now,
                    attributes={"e": 5},
                    inputs={"f": 6},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="child_call",
                    ended_at=now,
                    output={"g": 7},
                    summary={"h": 8},
                )
            )
        )

        result = server.calls_query(
            tsi.CallsQueryReq(
                project_id=project_id,
                include_storage_size=True,
                include_total_storage_size=True,
            )
        )
        calls_by_id = {c.id: c for c in result.calls}

        # Root call should have total_storage_size_bytes (sum of both calls)
        root = calls_by_id["root_call"]
        child = calls_by_id["child_call"]
        assert root.total_storage_size_bytes is not None
        assert root.storage_size_bytes is not None
        assert child.storage_size_bytes is not None
        # Child should have None total_storage_size (only root gets it)
        assert child.total_storage_size_bytes is None
        # total = root storage + child storage
        assert root.total_storage_size_bytes == (
            root.storage_size_bytes + child.storage_size_bytes
        )
    finally:
        server.close()


def test_sqlite_calls_query_stats_total_storage_size():
    """calls_query_stats returns the correct total_storage_size_bytes."""
    server = slts.SqliteTraceServer(":memory:")
    server.drop_tables()
    server.setup_tables()
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        project_id = "test_project"

        for i in range(3):
            server.call_start(
                tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=f"call_{i}",
                        trace_id=f"trace_{i}",
                        op_name="op",
                        started_at=now,
                        attributes={"idx": i},
                        inputs={"val": i * 10},
                    )
                )
            )
            server.call_end(
                tsi.CallEndReq(
                    end=tsi.EndedCallSchemaForInsert(
                        project_id=project_id,
                        id=f"call_{i}",
                        ended_at=now,
                        output={"out": i},
                        summary={},
                    )
                )
            )

        stats = server.calls_query_stats(
            tsi.CallsQueryStatsReq(
                project_id=project_id,
                include_total_storage_size=True,
            )
        )
        assert stats.count == 3
        assert stats.total_storage_size_bytes is not None
        assert stats.total_storage_size_bytes > 0
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
