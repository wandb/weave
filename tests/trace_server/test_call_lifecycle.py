import datetime
import uuid

import pytest

from tests.trace.util import FAKE_NOT_IMPLEMENTED, NOT_CLICKHOUSE_BACKEND
from tests.trace_server.helpers import force_optimize_calls_merged
from weave.trace import weave_client
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface import query as tsi_query


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_call_update_out_of_order(client: weave_client.WeaveClient):
    # Here, we are going to do an out of order sequence:
    # 1. Name a call
    # 2. Finish the call
    # 3. Start the call
    # 4. Delete the call
    #
    # Only step 3 should actually have the result in the query.

    call_id = str(uuid.uuid4())
    project_id = client.project_id

    def get_calls():
        res = client.server.calls_query(
            tsi.CallsQueryReq(
                project_id=project_id,
            )
        )
        return res.calls

    client.server.call_update(
        tsi.CallUpdateReq(
            project_id=project_id,
            call_id=call_id,
            display_name="test_display_name",
        )
    )

    assert len(get_calls()) == 0

    client.server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                ended_at=datetime.datetime.now(),
                exception=None,
                output=None,
                summary={},
            )
        )
    )

    assert len(get_calls()) == 0

    client.server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=call_id,
                started_at=datetime.datetime.now(),
                op_name="test_op_name",
                attributes={},
                inputs={},
            )
        )
    )

    assert len(get_calls()) == 1

    client.server.calls_delete(
        tsi.CallsDeleteReq(
            project_id=project_id,
            call_ids=[call_id],
        )
    )

    assert len(get_calls()) == 0


@pytest.mark.parametrize("end_arrives_first", [False, True])
@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: calls_merged columns"
)
def test_call_end_started_at_anchors_sortable_datetime(
    client: weave_client.WeaveClient, end_arrives_first: bool
) -> None:
    """`started_at` on the call_end row pins `calls_merged.sortable_datetime`.

    When `end_call_for_insert_to_ch_insertable` propagates `started_at` to the
    call_end's `call_parts` row, every per-row `coalesce(started_at, ended_at,
    created_at)` collapses to `started_at`, so the post-merge
    `anySimpleState(...)` is deterministic regardless of which part landed
    first. The `started_at < threshold` predicate in the calls query then
    cannot drop a long-running call merely because `any()` picked the end-row
    contribution -- the buggy path repro'd in #6932.
    """
    ch_client = client.server._next_trace_server.ch_client
    project_id = client.project_id
    call_id = str(uuid.uuid4())
    started_at = datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    # 1 hour duration -- comfortably past DATETIME_BUFFER_TIME_SECONDS (5 min).
    ended_at = started_at + datetime.timedelta(hours=1)

    start_req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            trace_id=call_id,
            op_name="test_op",
            started_at=started_at,
            attributes={},
            inputs={},
        )
    )
    end_req = tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=call_id,
            started_at=started_at,
            ended_at=ended_at,
            summary={},
        )
    )
    if end_arrives_first:
        client.server.call_end(end_req)
        client.server.call_start(start_req)
    else:
        client.server.call_start(start_req)
        client.server.call_end(end_req)

    # Force background merge: pre-merge, the start-batch row still has
    # sortable_datetime = started_at and rescues the WHERE on its own, hiding
    # the bug. The bug only surfaces once the merge collapses the two parts
    # into a single row whose `any(sortable_datetime)` could be ended_at.
    force_optimize_calls_merged(ch_client)

    threshold = started_at + datetime.timedelta(seconds=60)
    res = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=project_id,
            query=tsi_query.Query.model_validate(
                {
                    "$expr": {
                        "$lt": [
                            {"$getField": "started_at"},
                            {"$literal": threshold.timestamp()},
                        ]
                    }
                }
            ),
        )
    )
    # Pre-fix, the end_arrives_first case dropped the call: `any()` locked
    # onto `ended_at = started_at + 1h`, so `sortable_datetime < threshold + 5m`
    # evaluated false and the granule was skipped.
    assert len(res.calls) == 1
    assert res.calls[0].id == call_id
