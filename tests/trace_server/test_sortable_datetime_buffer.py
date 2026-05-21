"""Verifies the `started_at`-on-call-end fix for the `sortable_datetime`
optimization buffer in `calls_merged`.

The materialized `sortable_datetime` column on `calls_merged` is fed by
`anySimpleState(coalesce(started_at, ended_at, created_at))` from each
`call_parts` row. Before the fix, `end_call_for_insert_to_ch_insertable` dropped
`started_at` on the call-end row, so that row's per-row `coalesce` collapsed to
`ended_at`. When call_end arrived in `call_parts` before call_start (out-of-
order ingestion), `any()` locked onto `ended_at`, and queries with a
`started_at < ...` predicate dropped the call whenever its duration exceeded
the 5-minute buffer in `optimization_builder.DATETIME_BUFFER_TIME_SECONDS`.

The fix moves `started_at` onto the parent `EndedCallSchemaForInsert` and
plumbs it through the converter so both call_parts rows yield
`sortable_datetime == started_at`, making the post-merge aggregate
deterministic across all ingestion orders. All 21 (scenario x duration) cases
below now pass; pre-fix, the 3 `end_first x duration > buffer + query offset`
cases were dropped. See sister PR #6932 for the bug demo.

Run against real ClickHouse:
    nox --no-install -e "tests-3.12(shard='trace_server')" -- \
        tests/trace_server/test_sortable_datetime_buffer.py -v -s \
        --trace-server=clickhouse
"""

import datetime
import uuid

import pytest

from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

BASE_TIME = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
QUERY_OFFSET_SECONDS = 60

SCENARIO_START_FIRST = "start_first"
SCENARIO_SINGLE_BATCH = "single_batch"
SCENARIO_END_FIRST = "end_first"


@pytest.fixture
def ch_internal_server(trace_server):
    """Internal ClickHouseTraceServer with AUTO routing, or skip on SQLite."""
    internal_server = trace_server._internal_trace_server
    if isinstance(internal_server, SqliteTraceServer):
        pytest.skip("ClickHouse-only test")
    internal_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return internal_server


def _start_req(
    project_id: str, call_id: str, trace_id: str, started_at: datetime.datetime
) -> tsi.CallStartReq:
    return tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            trace_id=trace_id,
            op_name="test_op",
            started_at=started_at,
            attributes={},
            inputs={},
        )
    )


def _end_req(
    project_id: str,
    call_id: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
) -> tsi.CallEndReq:
    """End request that carries `started_at`, mirroring the post-fix Python SDK."""
    return tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            started_at=started_at,
            ended_at=ended_at,
            summary={"usage": {}, "status_counts": {}},
        )
    )


def _insert_call(
    trace_server,
    ch_internal_server,
    project_id: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    scenario: str,
) -> str:
    """Insert call_start + call_end under the named ingestion pattern."""
    call_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    start_req = _start_req(project_id, call_id, trace_id, started_at)
    end_req = _end_req(project_id, call_id, started_at, ended_at)

    if scenario == SCENARIO_START_FIRST:
        trace_server.call_start(start_req)
        trace_server.call_end(end_req)
    elif scenario == SCENARIO_END_FIRST:
        trace_server.call_end(end_req)
        trace_server.call_start(start_req)
    elif scenario == SCENARIO_SINGLE_BATCH:
        ch_internal_server._flush_immediately = False
        try:
            trace_server.call_start(start_req)
            trace_server.call_end(end_req)
            ch_internal_server._flush_calls()
        finally:
            ch_internal_server._flush_immediately = True
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return call_id


def _fetch_merged_row(
    ch_client, internal_project_id: str, call_id: str
) -> tuple[datetime.datetime, datetime.datetime, datetime.datetime, int] | None:
    """Read sortable_datetime / started_at / ended_at post-merge, plus part count."""
    pb = ParamBuilder()
    project_slot = param_slot(pb.add_param(internal_project_id), "String")
    id_slot = param_slot(pb.add_param(call_id), "String")
    query = f"""
        SELECT any(sortable_datetime),
               any(started_at),
               any(ended_at),
               count() AS part_count
        FROM calls_merged FINAL
        WHERE project_id = {project_slot} AND id = {id_slot}
    """
    rows = ch_client.query(query, parameters=pb.get_params()).result_rows
    if not rows or rows[0][3] == 0:
        return None
    return rows[0]


def _started_at_lt(threshold: datetime.datetime) -> tsi_query.Query:
    return tsi_query.Query.model_validate(
        {
            "$expr": {
                "$lt": [
                    {"$getField": "started_at"},
                    {"$literal": threshold.timestamp()},
                ]
            }
        }
    )


@pytest.mark.parametrize(
    "scenario",
    [SCENARIO_START_FIRST, SCENARIO_SINGLE_BATCH, SCENARIO_END_FIRST],
)
@pytest.mark.parametrize(
    "duration_seconds",
    [30, 4 * 60, 299, 301, 10 * 60, 30 * 60, 2 * 3600],
    ids=lambda s: f"dur={s}s",
)
def test_sortable_datetime_deterministic_with_started_at(
    trace_server,
    ch_internal_server,
    duration_seconds: int,
    scenario: str,
) -> None:
    """`sortable_datetime` must lock onto `started_at` regardless of ingestion order."""
    project_suffix = f"sortable_dt_fix_{scenario}_{duration_seconds}"
    project_id = f"{TEST_ENTITY}/{project_suffix}"
    internal_project_id = b64(project_id)
    started_at = BASE_TIME
    ended_at = BASE_TIME + datetime.timedelta(seconds=duration_seconds)
    call_id = _insert_call(
        trace_server, ch_internal_server, project_id, started_at, ended_at, scenario
    )

    ch_internal_server.ch_client.command("OPTIMIZE TABLE calls_merged FINAL")

    row = _fetch_merged_row(ch_internal_server.ch_client, internal_project_id, call_id)
    assert row is not None, "call row missing from calls_merged"
    materialized_sd, merged_started_at, merged_ended_at, _ = row

    if merged_started_at.tzinfo is None:
        merged_started_at = merged_started_at.replace(tzinfo=datetime.timezone.utc)
    if merged_ended_at.tzinfo is None:
        merged_ended_at = merged_ended_at.replace(tzinfo=datetime.timezone.utc)
    if materialized_sd.tzinfo is None:
        materialized_sd = materialized_sd.replace(tzinfo=datetime.timezone.utc)

    assert merged_started_at == started_at
    assert merged_ended_at == ended_at
    assert abs((materialized_sd - started_at).total_seconds()) < 1, (
        f"sortable_datetime={materialized_sd.isoformat()} did not lock onto "
        f"started_at={started_at.isoformat()} (scenario={scenario}, "
        f"duration={duration_seconds}s)"
    )

    # User filter `started_at < BASE_TIME + 60s` is true (started_at == BASE_TIME).
    # Pre-fix, this filter dropped the call under end_first + duration > 360s.
    threshold = BASE_TIME + datetime.timedelta(seconds=QUERY_OFFSET_SECONDS)
    calls = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                query=_started_at_lt(threshold),
            )
        )
    )
    assert len(calls) == 1, (
        f"call dropped by sortable_datetime optimization (scenario={scenario}, "
        f"duration={duration_seconds}s, sortable_datetime={materialized_sd.isoformat()})"
    )
