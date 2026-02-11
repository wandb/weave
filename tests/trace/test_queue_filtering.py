"""Tests for filtering calls by annotation queues.

These tests verify the queue filtering functionality added to calls_query_builder.py:
- CallsMergedQueueItemField class for annotation_queue_items.queue_id field
- INNER JOIN behavior that excludes calls not in the queue
- Queue ID extraction optimization from filter conditions
"""

import datetime

import pytest

import weave
from tests.trace.util import client_is_sqlite
from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_filter_calls_by_queue_inner_join_behavior(client):
    """Test that INNER JOIN correctly filters calls by queue membership.

    This is the core test for the queue filtering feature, verifying:
    - Only calls in the queue are returned
    - Calls not in the queue are excluded (INNER JOIN behavior)
    - The CallsMergedQueueItemField and queue_id extraction work correctly
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create 10 calls
    @weave.op(name="test_queue_filter")
    def test_op(x: int) -> int:
        return x * 2

    for i in range(10):
        test_op(i)

    calls = list(client.get_calls())[-10:]
    call_ids = [call.id for call in calls]

    # Create queue and add only calls 2-6 (5 calls out of 10)
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Test Queue",
        description="Test queue filtering",
        scorer_refs=["weave:///entity/project/scorer/test:abc123"],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(create_req)
    queue_id = queue_res.id

    add_req = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_id,
        call_ids=call_ids[2:7],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    client.server.annotation_queue_add_calls(add_req)

    # Query for calls in the queue
    query = tsi.Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "annotation_queue_items.queue_id"},
                    {"$literal": queue_id},
                ]
            }
        }
    )

    res = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id(), query=query)
    )

    # Should return exactly the 5 calls we added
    assert len(res.calls) == 5
    returned_ids = {call.id for call in res.calls}
    expected_ids = set(call_ids[2:7])
    assert returned_ids == expected_ids

    # Verify excluded calls are NOT in results (INNER JOIN excludes them)
    excluded_ids = set(call_ids[:2] + call_ids[7:])
    assert returned_ids.isdisjoint(excluded_ids)


def test_filter_calls_by_multiple_distinct_queues(client):
    """Test that queue filtering correctly isolates calls by queue_id.

    Verifies the queue_id extraction optimization works when filtering
    by different queues in separate queries.
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create 6 calls
    @weave.op(name="multi_queue_test")
    def test_op(x: int) -> int:
        return x

    for i in range(6):
        test_op(i)

    calls = list(client.get_calls())[-6:]
    call_ids = [call.id for call in calls]

    # Create two queues with non-overlapping calls
    queue1_res = client.server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name="Queue 1",
            scorer_refs=["weave:///entity/project/scorer/test:abc"],
            wb_user_id="test_user",
        )
    )
    queue2_res = client.server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name="Queue 2",
            scorer_refs=["weave:///entity/project/scorer/test:def"],
            wb_user_id="test_user",
        )
    )

    # Add calls 0-2 to queue1, calls 3-5 to queue2
    client.server.annotation_queue_add_calls(
        tsi.AnnotationQueueAddCallsReq(
            project_id=client._project_id(),
            queue_id=queue1_res.id,
            call_ids=call_ids[:3],
            display_fields=["input.x"],
            wb_user_id="test_user",
        )
    )
    client.server.annotation_queue_add_calls(
        tsi.AnnotationQueueAddCallsReq(
            project_id=client._project_id(),
            queue_id=queue2_res.id,
            call_ids=call_ids[3:],
            display_fields=["input.x"],
            wb_user_id="test_user",
        )
    )

    # Query queue1
    res1 = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            query=tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "annotation_queue_items.queue_id"},
                            {"$literal": queue1_res.id},
                        ]
                    }
                }
            ),
        )
    )

    # Query queue2
    res2 = client.server.calls_query(
        tsi.CallsQueryReq(
            project_id=client._project_id(),
            query=tsi.Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "annotation_queue_items.queue_id"},
                            {"$literal": queue2_res.id},
                        ]
                    }
                }
            ),
        )
    )

    # Each queue should return exactly its 3 calls
    assert len(res1.calls) == 3
    assert len(res2.calls) == 3
    assert {call.id for call in res1.calls} == set(call_ids[:3])
    assert {call.id for call in res2.calls} == set(call_ids[3:])
    assert {call.id for call in res1.calls}.isdisjoint({call.id for call in res2.calls})


def test_filter_calls_by_queue_combined_with_other_filters(client):
    """Test queue filter works correctly when combined with other query conditions.

    Verifies that the INNER JOIN for queue items integrates properly with
    other filter conditions in complex queries.
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create calls with two different op names
    @weave.op(name="op_include")
    def op_include(x: int) -> int:
        return x

    @weave.op(name="op_exclude")
    def op_exclude(x: int) -> int:
        return x * 2

    include_ids = []
    for i in range(3):
        op_include(i)
    include_calls = list(client.get_calls())[-3:]
    include_ids = [call.id for call in include_calls]

    exclude_ids = []
    for i in range(3):
        op_exclude(i)
    exclude_calls = list(client.get_calls())[-3:]
    exclude_ids = [call.id for call in exclude_calls]

    # Create queue with 2 calls from each op
    queue_res = client.server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name="Mixed Queue",
            scorer_refs=["weave:///entity/project/scorer/test:xyz"],
            wb_user_id="test_user",
        )
    )

    client.server.annotation_queue_add_calls(
        tsi.AnnotationQueueAddCallsReq(
            project_id=client._project_id(),
            queue_id=queue_res.id,
            call_ids=include_ids[:2] + exclude_ids[:2],
            display_fields=["input.x"],
            wb_user_id="test_user",
        )
    )

    # Query for queue + op_include (should return 2 calls)
    # Note: op_name is a full ref like "weave:///entity/project/op/op_include:hash"
    # so we use contains instead of equals
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "annotation_queue_items.queue_id"},
                            {"$literal": queue_res.id},
                        ]
                    },
                    {
                        "$contains": {
                            "input": {"$getField": "op_name"},
                            "substr": {"$literal": "/op/op_include:"},
                        }
                    },
                ]
            }
        }
    )

    res = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id(), query=query)
    )

    # Should return only the 2 op_include calls in the queue
    assert len(res.calls) == 2
    assert {call.id for call in res.calls} == set(include_ids[:2])


def test_filter_calls_by_nonexistent_queue(client):
    """Test that filtering by a non-existent queue returns empty results.

    Verifies INNER JOIN behavior when no matching queue items exist.
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create some calls
    @weave.op(name="test_nonexistent")
    def test_op(x: int) -> int:
        return x

    for i in range(3):
        test_op(i)

    # Use a random queue ID that doesn't exist
    nonexistent_queue_id = generate_id()

    query = tsi.Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "annotation_queue_items.queue_id"},
                    {"$literal": nonexistent_queue_id},
                ]
            }
        }
    )

    res = client.server.calls_query(
        tsi.CallsQueryReq(project_id=client._project_id(), query=query)
    )

    # Should return no calls
    assert len(res.calls) == 0


def test_filter_calls_by_queue_with_calls_complete_table(trace_server):
    """Integration test: queue filtering works correctly with calls_complete table.

    This test verifies that the queue filtering implementation works when
    the project uses calls_complete table (no GROUP BY, no aggregation).

    Steps:
    1. Seed project with calls_complete data to establish COMPLETE_ONLY residence
    2. Verify calls can be queried back
    3. Create queue and add some calls
    4. Query by queue_id - should automatically use calls_complete table
    5. Verify INNER JOIN correctly filters results
    """
    if isinstance(trace_server._internal_trace_server, SqliteTraceServer):
        pytest.skip("ClickHouse-only test")

    project_id = f"{TEST_ENTITY}/test_queue_calls_complete"

    # Step 1: Seed project with calls_complete data to establish residence
    seed_calls = []
    started_at = datetime.datetime.now()

    for i in range(5):
        call_id = generate_id()
        seed_calls.append(
            tsi.CompletedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=generate_id(),
                op_name="test_calls_complete_queue",
                started_at=started_at,
                ended_at=started_at + datetime.timedelta(seconds=1),
                attributes={},
                inputs={"x": i},
                output=i * 2,
                summary={"usage": {}, "status_counts": {}},
            )
        )

    call_ids = [call.id for call in seed_calls]
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=seed_calls))

    # Step 2: Verify we can query all calls back
    all_calls = list(
        trace_server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))
    )
    assert len(all_calls) == 5, f"Expected 5 calls, got {len(all_calls)}"
    returned_ids = {call.id for call in all_calls}
    assert returned_ids == set(call_ids)

    # Step 3: Create annotation queue
    queue_res = trace_server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=project_id,
            name="test_queue",
            description="Test queue for calls_complete filtering",
            scorer_refs=["weave:///entity/project/scorer/test:xyz"],
            wb_user_id="test_user",
        )
    )
    queue_id = queue_res.id

    # Step 4: Add 3 of the 5 calls to the queue
    queue_call_ids = call_ids[:3]
    trace_server.annotation_queue_add_calls(
        tsi.AnnotationQueueAddCallsReq(
            project_id=project_id,
            queue_id=queue_id,
            call_ids=queue_call_ids,
            display_fields=["input.x"],
            wb_user_id="test_user",
        )
    )

    query = tsi.Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "annotation_queue_items.queue_id"},
                    {"$literal": queue_id},
                ]
            }
        }
    )

    # Step 5: Query with queue filter - should return only the 3 calls in queue
    filtered_calls = list(
        trace_server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=project_id,
                query=query,
            )
        )
    )

    assert len(filtered_calls) == 3, (
        f"Expected 3 calls with queue filter, got {len(filtered_calls)}"
    )
    filtered_ids = {call.id for call in filtered_calls}
    assert filtered_ids == set(queue_call_ids), (
        f"Queue filtered calls mismatch. "
        f"Expected: {set(queue_call_ids)}, Got: {filtered_ids}"
    )
