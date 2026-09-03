"""Sync/async parity for the shared ClickHouse call logic.

`ClickHouseTraceServer._insert` and `AsyncClickHouseTraceServer._ainsert` are
deliberately separate loops over the same `prepare_insert` /
`insert_retry_or_raise` / `record_insert_success` functions. These tests drive
both against a recording transport and assert they cannot drift, including on
the retry and error paths.
"""

import asyncio

import pytest
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server.async_clickhouse_trace_server import (
    AsyncClickHouseTraceServer,
)
from weave.trace_server.clickhouse import transport as ch_transport
from weave.trace_server.clickhouse.transport import AsyncClickHouseTransport
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import InsertTooLarge
from weave.trace_server.ids import generate_id

TABLE = "intent_signatures"
COLUMNS = ["project_id"]
DATA = [["project-1"]]
SUMMARY = QuerySummary({"query_id": "qid"})
# Minted per call, so parity compares everything else.
PER_CALL_SETTINGS = ("insert_deduplication_token", "log_comment")


class RecordingTransport:
    """Records each prepared insert and fails the first `fail_times` of them."""

    def __init__(self, fail_times: int = 0, error: Exception | None = None) -> None:
        self.prepared = []
        self._fail_times = fail_times
        self._error = error or UnicodeEncodeError("utf-8", "x", 0, 1, "invalid")

    def insert(self, prepared):
        self.prepared.append(prepared)
        if len(self.prepared) <= self._fail_times:
            raise self._error
        return SUMMARY


class RecordingAsyncTransport(RecordingTransport):
    async def insert(self, prepared):
        return super().insert(prepared)


def drive_both(fail_times=0, error=None):
    """Run the same insert through both servers. Returns {arm: (transport, result)}."""
    recorded = {}

    sync_server = ClickHouseTraceServer(host="test_host", use_async_insert=False)
    sync_server._use_replicated_tables = True
    sync_transport = RecordingTransport(fail_times, error)
    sync_server._transport = sync_transport
    recorded["sync"] = (
        sync_transport,
        sync_server._insert(TABLE, DATA, COLUMNS),
    )

    async_server = AsyncClickHouseTraceServer(host="test_host", use_async_insert=False)
    async_server._use_replicated_tables = True
    async_transport = RecordingAsyncTransport(fail_times, error)
    async_server._atransport = async_transport
    recorded["async"] = (
        async_transport,
        asyncio.run(async_server._ainsert(TABLE, DATA, COLUMNS)),
    )
    return recorded


def drive_one(arm, fail_times=0, error=None):
    """Run the insert through exactly one arm.

    `drive_both` runs sync first and returns both results, which is fine while
    both succeed -- but on an error path the sync raise means the async arm is
    never reached. Error tests must drive each arm on its own, or they assert
    "both paths" while proving one.
    """
    if arm == "sync":
        server = ClickHouseTraceServer(host="test_host", use_async_insert=False)
        server._use_replicated_tables = True
        server._transport = RecordingTransport(fail_times, error)
        return server._insert(TABLE, DATA, COLUMNS)
    server = AsyncClickHouseTraceServer(host="test_host", use_async_insert=False)
    server._use_replicated_tables = True
    server._atransport = RecordingAsyncTransport(fail_times, error)
    return asyncio.run(server._ainsert(TABLE, DATA, COLUMNS))


def stable(settings):
    return {k: v for k, v in settings.items() if k not in PER_CALL_SETTINGS}


def test_both_paths_issue_the_same_insert():
    recorded = drive_both()
    (sync_t, sync_res), (async_t, async_res) = recorded["sync"], recorded["async"]

    assert sync_res is async_res is SUMMARY
    assert len(sync_t.prepared) == len(async_t.prepared) == 1
    sync_op, async_op = sync_t.prepared[0], async_t.prepared[0]
    assert sync_op.table == async_op.table == TABLE
    assert sync_op.data == async_op.data == DATA
    assert sync_op.column_names == async_op.column_names == COLUMNS
    assert sync_op.async_insert is async_op.async_insert is False
    assert stable(sync_op.settings) == stable(async_op.settings)
    for op in (sync_op, async_op):
        assert set(PER_CALL_SETTINGS) <= op.settings.keys()


def test_both_paths_retry_invalid_utf8_exactly_once():
    """The sanitize-and-retry is the semantics most at risk of drifting."""
    recorded = drive_both(fail_times=1)
    (sync_t, sync_res), (async_t, async_res) = recorded["sync"], recorded["async"]

    assert sync_res is async_res is SUMMARY
    assert len(sync_t.prepared) == len(async_t.prepared) == 2
    for prepared in (sync_t.prepared, async_t.prepared):
        # One correlation id covers both attempts: it is the same logical write.
        assert prepared[0].correlation_id == prepared[1].correlation_id


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("arm", ["sync", "async"])
@pytest.mark.parametrize(
    ("fail_times", "error", "expected"),
    [
        # A second invalid-utf8 failure is not retried again.
        (2, None, UnicodeEncodeError),
        (1, RuntimeError("driver down"), RuntimeError),
        # ValueError, but the oversized-insert one: mapped, not propagated.
        (1, ValueError("negative shift count"), InsertTooLarge),
    ],
)
def test_both_paths_raise_the_same_way(arm, fail_times, error, expected):
    with pytest.raises(expected):
        drive_one(arm, fail_times=fail_times, error=error)


@pytest.mark.asyncio
async def test_async_transport_round_trips_against_clickhouse(ch_server) -> None:
    """The parity tests above stub the transport, so nothing there ever reaches a
    real `AsyncClient`. This drives every method on the real thing: `start`
    (which runs CREATE DATABASE), `command`, `insert`, `query`, `close`.
    """
    transport = AsyncClickHouseTransport(ch_server._config)
    table = f"transport_round_trip_{generate_id()[:8]}"

    # Outside the try: a failed `start` closes its own client and leaves nothing
    # to clean up.
    client = await transport.start()
    assert client.database == ch_server._config.database

    try:
        await transport.command(
            ch_transport.prepare_command(
                f"CREATE TABLE {table} (project_id String) ENGINE = Memory", {}, None
            )
        )
        summary = await transport.insert(
            ch_transport.prepare_insert(
                table,
                data=[["p1"], ["p2"]],
                column_names=["project_id"],
                settings=None,
                use_async_insert=False,
                use_replicated_tables=False,
            )
        )
        assert summary is not None
        result = await transport.query(
            ch_transport.prepare_query(
                f"SELECT project_id FROM {table} ORDER BY project_id", {}, None, None
            )
        )
        assert [row[0] for row in result.result_rows] == ["p1", "p2"]
    finally:
        await transport.command(
            ch_transport.prepare_command(f"DROP TABLE IF EXISTS {table}", {}, None)
        )
        await transport.close()

    assert transport._client is None
