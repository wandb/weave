import datetime
import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

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


# ── "latest" alias write semantics ────────────────────────────────────


@pytest.fixture
def sqlite_db_path():
    """Yield a fresh on-disk SQLite path; cleanup the file and the cached conn."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        yield path
    finally:
        slts.close_conn_cursor(path)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def _make_obj_create_req(
    project_id: str, object_id: str, val: dict
) -> tsi.ObjCreateReq:
    return tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(project_id=project_id, object_id=object_id, val=val)
    )


class _CursorProxy:
    """Wraps a sqlite3.Cursor and raises on execute() when sql matches `fail_on`."""

    def __init__(self, real_cursor, fail_on: str, error: Exception):
        self._real = real_cursor
        self._fail_on = fail_on
        self._error = error

    def execute(self, sql, *args, **kwargs):
        if self._fail_on in sql:
            raise self._error
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._real, item)


def test_obj_create_atomic_on_alias_failure(sqlite_db_path):
    """obj_create's IMMEDIATE TRANSACTION must roll back the version row when
    the alias INSERT fails — neither the new objects row nor the alias row lands.
    """
    server = slts.SqliteTraceServer(sqlite_db_path)
    server.setup_tables()

    project_id = "p"
    object_id = "atomic_obj"

    # Establish a prior version so we can verify "latest" is unchanged.
    r1 = server.obj_create(_make_obj_create_req(project_id, object_id, {"v": 1}))

    # Replace the cached cursor with a proxy that raises on the alias INSERT.
    # The version-row INSERT and the alias INSERT both run inside
    # `BEGIN IMMEDIATE TRANSACTION`, so a failure before `conn.commit()`
    # should roll back both.
    real_conn, real_cursor = slts.get_conn_cursor(sqlite_db_path)
    proxy = _CursorProxy(
        real_cursor,
        fail_on="INSERT OR REPLACE INTO aliases",
        error=RuntimeError("simulated alias write failure"),
    )
    conn_map = slts._get_conn_map()
    saved = conn_map[sqlite_db_path]
    conn_map[sqlite_db_path] = slts.ConnCursor(real_conn, proxy)
    try:
        with pytest.raises(RuntimeError, match="simulated alias write failure"):
            server.obj_create(_make_obj_create_req(project_id, object_id, {"v": 2}))
    finally:
        conn_map[sqlite_db_path] = saved
        # Defensive: clear any lingering open transaction from the failed call.
        try:
            real_conn.rollback()
        except Exception:
            pass

    # The version row for v=2 must NOT have landed (transaction rolled back).
    real_cursor.execute(
        "SELECT COUNT(*) FROM objects WHERE project_id = ? AND object_id = ?",
        (project_id, object_id),
    )
    assert real_cursor.fetchone()[0] == 1

    # And "latest" still resolves to the prior digest (only v=1 exists).
    read_res = server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id=object_id, digest="latest")
    )
    assert read_res.obj.digest == r1.digest


def test_direct_delete_of_latest_alias_falls_back_to_is_latest_column(sqlite_db_path):
    """Directly hard-delete the 'latest' alias row from `aliases` (bypassing
    `obj_delete`'s cascade and `remove_aliases` — which the public validation
    layer would reject for 'latest' anyway).

    The hybrid `_IS_LATEST_FROM_ALIASES_SQL` expression must transparently
    fall back to the column-based `objects.is_latest = 1` branch.  This
    exercises that branch in isolation, without going through `obj_delete`
    (which both re-points the column AND removes the alias row, so it
    leaves both branches consistent and doesn't tell you which one
    answered the query).

    Catches: anyone removing the column fallback from
    `_IS_LATEST_FROM_ALIASES_SQL`, or anyone removing `obj_create`'s
    maintenance of `objects.is_latest` on insert.
    """
    server = slts.SqliteTraceServer(sqlite_db_path)
    server.setup_tables()

    project_id = "p"
    object_id = "fallback_obj"

    r0 = server.obj_create(_make_obj_create_req(project_id, object_id, {"v": 0}))
    r1 = server.obj_create(_make_obj_create_req(project_id, object_id, {"v": 1}))

    # Sanity: alias path wins normally.
    read_pre = server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id=object_id, digest="latest")
    )
    assert read_pre.obj.digest == r1.digest

    # Hard-delete the alias row directly.  This is below the public API —
    # `remove_aliases` would reject the reserved 'latest' name, and
    # `obj_delete` would cascade other state we don't want to touch here.
    conn, cursor = slts.get_conn_cursor(sqlite_db_path)
    cursor.execute(
        "DELETE FROM aliases WHERE project_id = ? AND object_id = ? AND alias = ?",
        (project_id, object_id, "latest"),
    )
    conn.commit()

    # Now the alias-row branch of _IS_LATEST_FROM_ALIASES_SQL is empty;
    # resolution must come from `objects.is_latest = 1` (column set by
    # obj_create).  r1 was inserted second, so its column is 1; r0 was
    # marked 0 by `_mark_existing_objects_as_not_latest`.
    read_post = server.obj_read(
        tsi.ObjReadReq(project_id=project_id, object_id=object_id, digest="latest")
    )
    assert read_post.obj.digest == r1.digest, (
        f"after deleting the 'latest' alias row, obj_read('latest') resolved "
        f"to {read_post.obj.digest!r}; expected {r1.digest!r} via the "
        f"objects.is_latest column fallback.  Either obj_create stopped "
        f"maintaining is_latest on insert, or `_IS_LATEST_FROM_ALIASES_SQL` "
        f"no longer ORs in the column branch."
    )

    # Same answer through the latest_only query path.
    latest_only = server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id], latest_only=True),
        )
    ).objs
    assert [o.digest for o in latest_only] == [r1.digest]
    # r0 must NOT also be is_latest=1 — exactly one row per object.
    assert latest_only[0].is_latest == 1

    # And through aliases=['latest'] — also routes through _IS_LATEST_FROM_ALIASES_SQL.
    via_alias_filter = server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id], aliases=["latest"]),
        )
    ).objs
    assert [o.digest for o in via_alias_filter] == [r1.digest]
