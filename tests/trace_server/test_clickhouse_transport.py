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
from weave.trace_server.clickhouse.transport import (
    AsyncClickHouseTransport,
    ClickHouseConfig,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import InsertTooLarge

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
def test_both_paths_stop_after_a_second_invalid_utf8(arm):
    with pytest.raises(UnicodeEncodeError):
        drive_one(arm, fail_times=2)


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("arm", ["sync", "async"])
def test_both_paths_propagate_a_non_retryable_error(arm):
    with pytest.raises(RuntimeError, match="driver down"):
        drive_one(arm, fail_times=1, error=RuntimeError("driver down"))


@pytest.mark.disable_logging_error_check
@pytest.mark.parametrize("arm", ["sync", "async"])
def test_both_paths_convert_an_oversized_insert(arm):
    with pytest.raises(InsertTooLarge):
        drive_one(arm, fail_times=1, error=ValueError("negative shift count"))


def test_async_transport_close_clears_the_session():
    transport = AsyncClickHouseTransport(ClickHouseConfig(host="test_host"))
    closed = []

    class FakeClient:
        async def close(self):
            closed.append(True)

    async def run():
        transport._client = FakeClient()
        await transport.close()

    asyncio.run(run())
    assert closed == [True]
    assert transport._client is None
