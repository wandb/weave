"""End-to-end TTL tests: set retention, insert via each call endpoint, raw-read expire_at.

Covers the four insert paths that compute expire_at:
  1. call_start + call_end           (v1)
  2. call_start_batch                (v1 batch)
  3. calls_complete                  (v2 upsert)
  4. call_start_v2 + call_end_v2     (v2 start + end)

Each test runs against whichever backend the test session is configured for
(ClickHouse or SQLite) via the shared `trace_server` fixture.
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import EXPIRE_AT_NEVER
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.sqlite_trace_server import SqliteTraceServer, get_conn_cursor
from weave.trace_server.ttl_settings import reset_ttl_cache

TEST_ENTITY = "ttl_entity"

# Retention policy → expected timedelta applied to the anchor.
# 0 sentinel is handled separately (far-future 2100-01-01).
RETENTION_CASES: list[tuple[int, datetime.timedelta | None]] = [
    (30, datetime.timedelta(days=30)),
    (0, None),
    (-5, datetime.timedelta(minutes=5)),
]


@pytest.fixture(autouse=True)
def _clear_ttl_cache():
    reset_ttl_cache()
    yield
    reset_ttl_cache()


@pytest.fixture
def internal_server(trace_server):
    server = trace_server._internal_trace_server
    if isinstance(server, ClickHouseTraceServer):
        server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return server


def _set_retention_days(
    server: ClickHouseTraceServer | SqliteTraceServer,
    internal_project_id: str,
    retention_days: int,
) -> None:
    """Persist a retention_days row for the project in the backend."""
    if isinstance(server, ClickHouseTraceServer):
        server.ch_client.insert(
            "project_ttl_settings",
            [[internal_project_id, retention_days]],
            column_names=["project_id", "retention_days"],
        )
    elif isinstance(server, SqliteTraceServer):
        conn, cursor = get_conn_cursor(server.db_path)
        cursor.execute(
            "INSERT INTO project_ttl_settings (project_id, retention_days) "
            "VALUES (?, ?)",
            (internal_project_id, retention_days),
        )
        conn.commit()
    else:
        raise TypeError(f"Unsupported server type: {type(server).__name__}")


def _read_expire_at(
    server: ClickHouseTraceServer | SqliteTraceServer,
    internal_project_id: str,
    call_id: str,
    table: str,
) -> list[datetime.datetime]:
    """Raw-read expire_at value(s) for a call.

    `table` selects the CH table (`call_parts`, `calls_merged`, `calls_complete`)
    and is ignored for SQLite, which only has a single `calls` table.
    Returns a list so CH v1 call_parts (which stores one row per start/end) can
    return multiple rows; SQLite and CH calls_complete always return a single entry.
    """
    if isinstance(server, ClickHouseTraceServer):
        result = server.ch_client.query(
            f"SELECT expire_at FROM {table} "
            "WHERE project_id = {project_id:String} AND id = {call_id:String} "
            "ORDER BY expire_at",
            parameters={"project_id": internal_project_id, "call_id": call_id},
        )
        return [row[0] for row in result.result_rows]
    if isinstance(server, SqliteTraceServer):
        _, cursor = get_conn_cursor(server.db_path)
        cursor.execute(
            "SELECT expire_at FROM calls WHERE project_id = ? AND id = ?",
            (internal_project_id, call_id),
        )
        return [_parse_sqlite_datetime(row[0]) for row in cursor.fetchall()]
    raise TypeError(f"Unsupported server type: {type(server).__name__}")


def _parse_sqlite_datetime(raw: str) -> datetime.datetime:
    parsed = datetime.datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _v1_read_table(server: ClickHouseTraceServer | SqliteTraceServer) -> str:
    return "call_parts" if isinstance(server, ClickHouseTraceServer) else "calls"


def _v2_read_table(server: ClickHouseTraceServer | SqliteTraceServer) -> str:
    return "calls_complete" if isinstance(server, ClickHouseTraceServer) else "calls"


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    """Tag naive datetimes as UTC without shifting wall-clock; normalize aware to UTC.

    Both backends store expire_at as UTC but differ in whether the driver returns
    a naive or aware datetime (CH returns naive, SQLite strings come back naive).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _assert_expire_at_matches(
    actual: list[datetime.datetime],
    anchor: datetime.datetime,
    retention_days: int,
    expected_delta: datetime.timedelta | None,
) -> None:
    """Assert every expire_at row equals anchor+delta (or sentinel when retention=0)."""
    assert actual, "expected at least one expire_at row from the raw read"
    expected = EXPIRE_AT_NEVER if expected_delta is None else anchor + expected_delta
    expected_utc = _as_utc(expected)
    for value in actual:
        assert _as_utc(value) == expected_utc, (
            f"retention_days={retention_days}: expected {expected_utc}, got {value!r}"
        )


def _make_project(suffix: str) -> tuple[str, str]:
    """Return (external_project_id, internal_project_id) for an isolated test project."""
    external = f"{TEST_ENTITY}/ttl_{suffix}_{uuid.uuid4().hex[:8]}"
    return external, b64(external)


def _now_utc() -> datetime.datetime:
    # Millisecond precision so CH round-trip comparisons line up exactly.
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
def test_ttl_call_start_end_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start + call_end: expire_at populated on v1 insert paths.

    For ClickHouse this asserts on the two call_parts rows (start and end). For
    SQLite this asserts on the single `calls` row (call_end is an UPDATE and
    must leave expire_at from call_start untouched).
    """
    external_project_id, internal_project_id = _make_project("start_end")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                ended_at=ended_at,
                output={},
                summary={},
            )
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, _v1_read_table(internal_server)
    )
    if isinstance(internal_server, ClickHouseTraceServer):
        # Two rows: start (anchor=started_at) and end (anchor=ended_at).
        assert len(values) == 2
        _assert_expire_at_matches(
            [values[0]], started_at, retention_days, expected_delta
        )
        _assert_expire_at_matches([values[1]], ended_at, retention_days, expected_delta)
    else:
        # SQLite is a single row seeded by call_start, call_end leaves it alone.
        assert len(values) == 1
        _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
def test_ttl_call_start_batch_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start_batch: batched start/end items both populate expire_at.

    The external adapter does not wrap call_start_batch, so we hit the internal
    server directly with pre-encoded project ids.
    """
    _, internal_project_id = _make_project("batch")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    internal_server.call_start_batch(
        tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            trace_id=trace_id,
                            op_name="op",
                            started_at=started_at,
                            attributes={},
                            inputs={},
                        )
                    ),
                ),
                tsi.CallBatchEndMode(
                    req=tsi.CallEndReq(
                        end=tsi.EndedCallSchemaForInsert(
                            project_id=internal_project_id,
                            id=call_id,
                            ended_at=ended_at,
                            output={},
                            summary={},
                        )
                    ),
                ),
            ]
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, _v1_read_table(internal_server)
    )
    if isinstance(internal_server, ClickHouseTraceServer):
        assert len(values) == 2
        _assert_expire_at_matches(
            [values[0]], started_at, retention_days, expected_delta
        )
        _assert_expire_at_matches([values[1]], ended_at, retention_days, expected_delta)
    else:
        assert len(values) == 1
        _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
def test_ttl_calls_complete_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """calls_complete: single-row v2 insert populates expire_at from started_at."""
    external_project_id, internal_project_id = _make_project("complete")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.calls_complete(
        tsi.CallsUpsertCompleteReq(
            batch=[
                tsi.CompletedCallSchemaForInsert(
                    project_id=external_project_id,
                    id=call_id,
                    trace_id=trace_id,
                    op_name="op",
                    started_at=started_at,
                    ended_at=ended_at,
                    attributes={},
                    inputs={},
                    output=None,
                    summary={"usage": {}, "status_counts": {}},
                )
            ]
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, _v2_read_table(internal_server)
    )
    assert len(values) == 1
    _assert_expire_at_matches(values, started_at, retention_days, expected_delta)


@pytest.mark.parametrize(("retention_days", "expected_delta"), RETENTION_CASES)
def test_ttl_call_start_v2_end_v2_sets_expire_at(
    trace_server, internal_server, retention_days, expected_delta
):
    """call_start_v2 + call_end_v2: start seeds expire_at; end UPDATE leaves it intact."""
    external_project_id, internal_project_id = _make_project("v2")
    _set_retention_days(internal_server, internal_project_id, retention_days)

    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    started_at = _now_utc()
    ended_at = started_at + datetime.timedelta(seconds=1)

    trace_server.call_start_v2(
        tsi.CallStartV2Req(
            start=tsi.StartedCallSchemaForInsert(
                project_id=external_project_id,
                id=call_id,
                trace_id=trace_id,
                op_name="op",
                started_at=started_at,
                attributes={},
                inputs={},
            )
        )
    )
    trace_server.call_end_v2(
        tsi.CallEndV2Req(
            end=tsi.EndedCallSchemaForInsertWithStartedAt(
                project_id=external_project_id,
                id=call_id,
                started_at=started_at,
                ended_at=ended_at,
                output={},
                summary={"usage": {}, "status_counts": {}},
            )
        )
    )

    values = _read_expire_at(
        internal_server, internal_project_id, call_id, _v2_read_table(internal_server)
    )
    assert len(values) == 1
    _assert_expire_at_matches(values, started_at, retention_days, expected_delta)
