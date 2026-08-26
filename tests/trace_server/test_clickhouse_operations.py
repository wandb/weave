"""Transport parity for the shared ClickHouse call protocols.

`run_sync` and `run_async` exist so the blocking and aiohttp servers cannot
drift. These tests drive one sequence through both runners and assert they
issue the same operations, including on the retry and error paths — the parts
that used to be duplicated by hand.
"""

import asyncio

import pytest
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server.clickhouse import operations as ch_ops

TABLE = "intent_signatures"
COLUMNS = ["project_id"]
DATA = [["project-1"]]
# Minted per sequence, so parity compares everything else.
PER_RUN_SETTINGS = ("insert_deduplication_token", "log_comment")


def insert_sequence():
    return ch_ops.insert_sequence(
        TABLE,
        DATA,
        COLUMNS,
        None,
        False,
        use_async_insert=False,
        use_replicated_tables=True,
    )


def stable(settings):
    return {k: v for k, v in settings.items() if k not in PER_RUN_SETTINGS}


def drive_both(make_sequence, fail_times, result):
    """Run the same sequence through both runners, failing the first N ops."""
    recorded = {}
    for arm in ("sync", "async"):
        ops = []

        def execute(operation, ops=ops):
            ops.append(operation)
            if len(ops) <= fail_times:
                raise UnicodeEncodeError("utf-8", "x", 0, 1, "invalid")
            return result

        if arm == "sync":
            got = ch_ops.run_sync(make_sequence(), execute)
        else:

            async def aexecute(operation):
                return execute(operation)

            got = asyncio.run(ch_ops.run_async(make_sequence(), aexecute))
        recorded[arm] = (ops, got)
    return recorded


def test_both_runners_issue_the_same_insert():
    summary = QuerySummary({"query_id": "qid"})
    recorded = drive_both(insert_sequence, fail_times=0, result=summary)

    (sync_ops, sync_res), (async_ops, async_res) = recorded["sync"], recorded["async"]
    assert sync_res is async_res is summary
    assert len(sync_ops) == len(async_ops) == 1
    assert sync_ops[0].table == async_ops[0].table == TABLE
    assert sync_ops[0].data == async_ops[0].data == DATA
    assert sync_ops[0].column_names == async_ops[0].column_names == COLUMNS
    assert stable(sync_ops[0].settings) == stable(async_ops[0].settings)
    for op in (sync_ops[0], async_ops[0]):
        assert set(PER_RUN_SETTINGS) <= op.settings.keys()


def test_both_runners_retry_invalid_utf8_exactly_once():
    """The sanitize-and-retry is the semantics most at risk of drifting."""
    summary = QuerySummary({"query_id": "qid"})
    recorded = drive_both(insert_sequence, fail_times=1, result=summary)

    (sync_ops, sync_res), (async_ops, async_res) = recorded["sync"], recorded["async"]
    assert len(sync_ops) == len(async_ops) == 2
    assert sync_res is async_res is summary
    # One correlation id covers both attempts: it is the same logical write.
    assert sync_ops[0].settings["log_comment"] == sync_ops[1].settings["log_comment"]
    assert async_ops[0].settings["log_comment"] == async_ops[1].settings["log_comment"]


@pytest.mark.disable_logging_error_check
def test_both_runners_stop_after_a_second_invalid_utf8():
    with pytest.raises(UnicodeEncodeError):
        ch_ops.run_sync(insert_sequence(), _always_invalid_utf8)
    with pytest.raises(UnicodeEncodeError):
        asyncio.run(ch_ops.run_async(insert_sequence(), _always_invalid_utf8_async))


@pytest.mark.disable_logging_error_check
def test_both_runners_propagate_a_non_retryable_error():
    with pytest.raises(RuntimeError, match="driver down"):
        ch_ops.run_sync(insert_sequence(), _boom)
    with pytest.raises(RuntimeError, match="driver down"):
        asyncio.run(ch_ops.run_async(insert_sequence(), _boom_async))


def test_query_sequence_yields_one_query_op_with_merged_settings():
    sequence = ch_ops.query_sequence("SELECT 1", {"project_id": "project-1"})
    operation = next(sequence)

    assert isinstance(operation, ch_ops.QueryOp)
    assert operation.query == "SELECT 1"
    assert operation.parameters == {"project_id": "project-1"}
    assert "log_comment" in operation.settings
    sequence.close()


def _always_invalid_utf8(operation):
    raise UnicodeEncodeError("utf-8", "x", 0, 1, "invalid")


async def _always_invalid_utf8_async(operation):
    raise UnicodeEncodeError("utf-8", "x", 0, 1, "invalid")


def _boom(operation):
    raise RuntimeError("driver down")


async def _boom_async(operation):
    raise RuntimeError("driver down")
