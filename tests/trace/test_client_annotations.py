"""Tests for annotation queue APIs.

These tests cover the queue-based call annotation system introduced in
commit 7fd5bfd24bccce8f97449bee1676ac55e74fd993.
"""

import pytest

import weave
from tests.trace.util import client_is_sqlite
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id


def test_annotation_queue_create_and_read(client):
    """Test creating and reading an annotation queue."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Test Queue",
        description="A test annotation queue",
        scorer_refs=["weave:///entity/project/scorer/test:abc123"],
        wb_user_id="test_user_123",
    )

    create_res = client.server.annotation_queue_create(create_req)

    # Verify create response
    assert create_res.id is not None
    assert len(create_res.id) > 0

    # Read the queue back
    read_req = tsi.AnnotationQueueReadReq(
        project_id=client._project_id(),
        queue_id=create_res.id,
    )
    read_res = client.server.annotation_queue_read(read_req)

    # Verify all queue data matches what we created
    assert read_res.queue.id == create_res.id
    assert read_res.queue.name == "Test Queue"
    assert read_res.queue.description == "A test annotation queue"
    assert read_res.queue.scorer_refs == ["weave:///entity/project/scorer/test:abc123"]
    assert read_res.queue.created_by == "test_user_123"
    assert read_res.queue.deleted_at is None


def test_annotation_queue_multiple_scorer_refs(client):
    """Test creating a queue with multiple scorer refs."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Multi Scorer Queue",
        description="Queue with multiple scorers",
        scorer_refs=[
            "weave:///entity/project/scorer/accuracy:abc123",
            "weave:///entity/project/scorer/relevance:def456",
            "weave:///entity/project/scorer/safety:ghi789",
        ],
        wb_user_id="test_user",
    )

    res = client.server.annotation_queue_create(req)
    assert res.id is not None

    # Read it back to verify scorer_refs
    read_req = tsi.AnnotationQueueReadReq(
        project_id=client._project_id(),
        queue_id=res.id,
    )
    read_res = client.server.annotation_queue_read(read_req)

    assert len(read_res.queue.scorer_refs) == 3
    assert (
        "weave:///entity/project/scorer/accuracy:abc123" in read_res.queue.scorer_refs
    )
    assert (
        "weave:///entity/project/scorer/relevance:def456" in read_res.queue.scorer_refs
    )
    assert "weave:///entity/project/scorer/safety:ghi789" in read_res.queue.scorer_refs


def test_annotation_queues_query_stream_all(client):
    """Test querying all annotation queues for a project."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create multiple queues
    for i in range(3):
        req = tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name=f"Queue {i}",
            description=f"Test queue number {i}",
            scorer_refs=[f"weave:///entity/project/scorer/test{i}:hash{i}"],
            wb_user_id="test_user_789",
        )
        client.server.annotation_queue_create(req)

    # Query all queues
    query_req = tsi.AnnotationQueuesQueryReq(
        project_id=client._project_id(),
    )

    queues = list(client.server.annotation_queues_query_stream(query_req))

    # Should have at least the 3 we just created
    assert len(queues) >= 3

    # Verify queues are sorted by created_at DESC (newest first)
    for i in range(len(queues) - 1):
        assert queues[i].created_at >= queues[i + 1].created_at


def test_annotation_queues_query_stream_with_name_filter(client):
    """Test querying queues with name filter."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queues with different names
    req1 = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Error Review Queue",
        scorer_refs=["weave:///entity/project/scorer/error:abc"],
        wb_user_id="test_user",
    )
    client.server.annotation_queue_create(req1)

    req2 = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Quality Check Queue",
        scorer_refs=["weave:///entity/project/scorer/quality:def"],
        wb_user_id="test_user",
    )
    client.server.annotation_queue_create(req2)

    # Query with name filter (case-insensitive partial match)
    query_req = tsi.AnnotationQueuesQueryReq(
        project_id=client._project_id(),
        name="error",  # Should match "Error Review Queue"
    )

    queues = list(client.server.annotation_queues_query_stream(query_req))

    # Should find the error queue
    assert len(queues) >= 1
    assert any(q.name == "Error Review Queue" for q in queues)
    # Should not find quality queue
    assert not any(q.name == "Quality Check Queue" for q in queues)


def test_annotation_queues_query_stream_with_pagination(client):
    """Test querying queues with limit and offset."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create 5 queues
    for i in range(5):
        req = tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name=f"Pagination Queue {i}",
            scorer_refs=[f"weave:///entity/project/scorer/test{i}:hash"],
            wb_user_id="test_user",
        )
        client.server.annotation_queue_create(req)

    # Query first page (limit 2)
    query_req = tsi.AnnotationQueuesQueryReq(
        project_id=client._project_id(),
        limit=2,
        offset=0,
    )
    page1 = list(client.server.annotation_queues_query_stream(query_req))
    assert len(page1) == 2

    # Query second page (offset 2)
    query_req = tsi.AnnotationQueuesQueryReq(
        project_id=client._project_id(),
        limit=2,
        offset=2,
    )
    page2 = list(client.server.annotation_queues_query_stream(query_req))
    assert len(page2) == 2

    # Pages should have different queues
    page1_ids = {q.id for q in page1}
    page2_ids = {q.id for q in page2}
    assert page1_ids.isdisjoint(page2_ids)


def test_annotation_queue_add_calls(client):
    """Test adding calls to an annotation queue."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create some test calls
    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    # Execute ops to create calls
    test_op(1)
    test_op(2)
    test_op(3)

    # Get call IDs
    calls = list(client.get_calls())
    assert len(calls) == 3
    call_ids = [call.id for call in calls]

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Add Calls Test Queue",
        scorer_refs=["weave:///entity/project/scorer/test:abc"],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(create_req)

    # Add calls to queue
    add_req = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_res.id,
        call_ids=call_ids,
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res = client.server.annotation_queue_add_calls(add_req)

    # Verify response
    assert add_res.added_count == 3
    assert add_res.duplicates == 0


def test_annotation_queue_add_calls_duplicate_prevention(client):
    """Test that adding duplicate calls is handled correctly."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    project_id = client._project_id()

    # Create a test call
    @weave.op
    def test_op(x: int) -> int:
        return x * 2

    test_op(42)

    calls = list(client.get_calls())
    assert len(calls) == 1
    call_id = calls[0].id

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=project_id,
        name="Duplicate Test Queue",
        scorer_refs=["weave:///entity/project/scorer/test:abc"],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(create_req)

    # Add call first time
    add_req = tsi.AnnotationQueueAddCallsReq(
        project_id=project_id,
        queue_id=queue_res.id,
        call_ids=[call_id],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res1 = client.server.annotation_queue_add_calls(add_req)
    assert add_res1.added_count == 1
    assert add_res1.duplicates == 0

    # Try to add the same call again (create new request to avoid mutation issues)
    add_req2 = tsi.AnnotationQueueAddCallsReq(
        project_id=project_id,
        queue_id=queue_res.id,
        call_ids=[call_id],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res2 = client.server.annotation_queue_add_calls(add_req2)
    assert add_res2.added_count == 0
    assert add_res2.duplicates == 1


def test_annotation_queue_add_calls_batch(client):
    """Test adding multiple calls in batch."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create many test calls
    @weave.op
    def batch_op(x: int) -> int:
        return x + 10

    # Create 20 calls
    for i in range(20):
        batch_op(i)

    calls = list(client.get_calls())
    assert len(calls) == 20
    call_ids = [call.id for call in calls]

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Batch Test Queue",
        scorer_refs=["weave:///entity/project/scorer/batch:xyz"],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(create_req)

    # Add all calls in one batch
    add_req = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_res.id,
        call_ids=call_ids,
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res = client.server.annotation_queue_add_calls(add_req)

    assert add_res.added_count == 20
    assert add_res.duplicates == 0


def test_annotation_queue_add_calls_partial_duplicates(client):
    """Test adding calls where some are duplicates and some are new."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create test calls
    @weave.op
    def partial_op(x: int) -> int:
        return x * 3

    for i in range(5):
        partial_op(i)

    calls = list(client.get_calls())
    assert len(calls) == 5
    call_ids = [call.id for call in calls]

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Partial Duplicate Queue",
        scorer_refs=["weave:///entity/project/scorer/test:abc"],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(create_req)

    # Add first 3 calls
    add_req1 = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_res.id,
        call_ids=call_ids[:3],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res1 = client.server.annotation_queue_add_calls(add_req1)
    assert add_res1.added_count == 3
    assert add_res1.duplicates == 0

    # Add all 5 calls (3 duplicates + 2 new)
    add_req2 = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_res.id,
        call_ids=call_ids,
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res2 = client.server.annotation_queue_add_calls(add_req2)
    assert add_res2.added_count == 2  # Only 2 new calls added
    assert add_res2.duplicates == 3  # 3 were duplicates


def test_annotation_queues_stats(client):
    """Test getting stats for multiple annotation queues with partial completion."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create test calls
    @weave.op
    def stats_test_op(x: int) -> int:
        return x * 10

    for i in range(10):
        stats_test_op(i)

    calls = list(client.get_calls())
    assert len(calls) == 10
    call_ids = [call.id for call in calls]

    # Create three queues
    queue_ids = []
    for i in range(3):
        req = tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name=f"Stats Test Queue {i}",
            scorer_refs=[f"weave:///entity/project/scorer/test{i}:abc"],
            wb_user_id="test_user",
        )
        res = client.server.annotation_queue_create(req)
        queue_ids.append(res.id)

    # Add different numbers of calls to each queue
    # Queue 0: 3 calls
    add_req1 = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_ids[0],
        call_ids=call_ids[:3],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res1 = client.server.annotation_queue_add_calls(add_req1)
    assert add_res1.added_count == 3

    # Queue 1: 5 calls
    add_req2 = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_ids[1],
        call_ids=call_ids[:5],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res2 = client.server.annotation_queue_add_calls(add_req2)
    assert add_res2.added_count == 5

    # Queue 2: 7 calls
    add_req3 = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_ids[2],
        call_ids=call_ids[:7],
        display_fields=["input.x", "output"],
        wb_user_id="test_user",
    )
    add_res3 = client.server.annotation_queue_add_calls(add_req3)
    assert add_res3.added_count == 7

    # Now mark some items as completed/skipped by inserting progress records
    # This simulates the annotation workflow where annotators work on items
    # Progress records are only created when an annotator interacts with an item

    # For Queue 0 (3 items): Mark 2 as completed, 1 stays pending (no progress record)
    # For Queue 1 (5 items): Mark 3 as completed, 1 as skipped, 1 stays pending (no progress record)
    # For Queue 2 (7 items): Mark 4 as skipped, 3 stay pending (no progress record)

    # We need to insert into the annotator_queue_items_progress table
    # Access the ClickHouse client through the server wrapper chain
    # The pattern is: client.server (caching middleware) -> _next_trace_server (actual CH server)
    try:
        ch_client = client.server._next_trace_server.ch_client
    except AttributeError:
        # For non-ClickHouse backends (e.g., SQLite), skip the direct DB manipulation
        pytest.skip("Direct DB manipulation only works with ClickHouse server")

    # Ensure writes are flushed
    import time

    time.sleep(0.5)

    # Use internal project_id (base64 encoded format)
    # TODO: Use proper ID converter once available
    internal_project_id = "c2hhd24vdGVzdC1wcm9qZWN0"  # base64 of "shawn/test-project"

    # Get queue_item_ids for Queue 0
    result = ch_client.query(
        f"SELECT id FROM annotation_queue_items WHERE project_id = '{internal_project_id}' AND queue_id = '{queue_ids[0]}' AND deleted_at IS NULL ORDER BY created_at LIMIT 3"
    )
    queue0_items = [row[0] for row in result.result_rows]
    assert len(queue0_items) == 3

    # Mark first 2 items of Queue 0 as completed by inserting progress records
    for item_id in queue0_items[:2]:
        progress_id = generate_id()
        ch_client.command(
            f"""
            INSERT INTO annotator_queue_items_progress (id, project_id, queue_item_id, queue_id, annotator_id, annotation_state)
            VALUES ('{progress_id}', '{internal_project_id}', '{item_id}', '{queue_ids[0]}', 'test_annotator', 'completed')
            """
        )

    # Get queue_item_ids for Queue 1
    result = ch_client.query(
        f"SELECT id FROM annotation_queue_items WHERE project_id = '{internal_project_id}' AND queue_id = '{queue_ids[1]}' AND deleted_at IS NULL ORDER BY created_at LIMIT 5"
    )
    queue1_items = [row[0] for row in result.result_rows]
    assert len(queue1_items) == 5

    # Mark first 3 items of Queue 1 as completed by inserting progress records
    for item_id in queue1_items[:3]:
        progress_id = generate_id()
        ch_client.command(
            f"""
            INSERT INTO annotator_queue_items_progress (id, project_id, queue_item_id, queue_id, annotator_id, annotation_state)
            VALUES ('{progress_id}', '{internal_project_id}', '{item_id}', '{queue_ids[1]}', 'test_annotator', 'completed')
            """
        )

    # Mark 4th item of Queue 1 as skipped by inserting a progress record
    item_id = queue1_items[3]
    progress_id = generate_id()
    ch_client.command(
        f"""
        INSERT INTO annotator_queue_items_progress (id, project_id, queue_item_id, queue_id, annotator_id, annotation_state)
        VALUES ('{progress_id}', '{internal_project_id}', '{item_id}', '{queue_ids[1]}', 'test_annotator', 'skipped')
        """
    )

    # Get queue_item_ids for Queue 2
    result = ch_client.query(
        f"SELECT id FROM annotation_queue_items WHERE project_id = '{internal_project_id}' AND queue_id = '{queue_ids[2]}' AND deleted_at IS NULL ORDER BY created_at LIMIT 7"
    )
    queue2_items = [row[0] for row in result.result_rows]
    assert len(queue2_items) == 7

    # Mark first 4 items of Queue 2 as skipped by inserting progress records
    for item_id in queue2_items[:4]:
        progress_id = generate_id()
        ch_client.command(
            f"""
            INSERT INTO annotator_queue_items_progress (id, project_id, queue_item_id, queue_id, annotator_id, annotation_state)
            VALUES ('{progress_id}', '{internal_project_id}', '{item_id}', '{queue_ids[2]}', 'test_annotator', 'skipped')
            """
        )

    # Get stats for all queues
    stats_req = tsi.AnnotationQueuesStatsReq(
        project_id=client._project_id(),
        queue_ids=queue_ids,
    )
    stats_res = client.server.annotation_queues_stats(stats_req)

    # Verify we got stats for all 3 queues
    assert len(stats_res.stats) == 3

    # Create a map of queue_id to stats for easier verification
    stats_map = {stat.queue_id: stat for stat in stats_res.stats}

    # Verify stats for each queue
    # Queue 0: 3 total, 2 completed
    assert stats_map[queue_ids[0]].total_items == 3
    assert stats_map[queue_ids[0]].completed_items == 2

    # Queue 1: 5 total, 4 completed (3 completed + 1 skipped)
    assert stats_map[queue_ids[1]].total_items == 5
    assert stats_map[queue_ids[1]].completed_items == 4

    # Queue 2: 7 total, 4 skipped
    assert stats_map[queue_ids[2]].total_items == 7
    assert stats_map[queue_ids[2]].completed_items == 4


def test_annotation_queues_stats_empty_queues(client):
    """Test getting stats for queues with no items."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create two empty queues
    queue_ids = []
    for i in range(2):
        req = tsi.AnnotationQueueCreateReq(
            project_id=client._project_id(),
            name=f"Empty Stats Queue {i}",
            scorer_refs=[f"weave:///entity/project/scorer/empty{i}:abc"],
            wb_user_id="test_user",
        )
        res = client.server.annotation_queue_create(req)
        queue_ids.append(res.id)

    # Get stats for empty queues
    stats_req = tsi.AnnotationQueuesStatsReq(
        project_id=client._project_id(),
        queue_ids=queue_ids,
    )
    stats_res = client.server.annotation_queues_stats(stats_req)

    # Verify we got stats for both queues with zero items
    assert len(stats_res.stats) == 2
    for stat in stats_res.stats:
        assert stat.total_items == 0
        assert stat.completed_items == 0


def test_annotation_queues_stats_no_queue_ids(client):
    """Test getting stats with empty queue_ids list."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Request stats with no queue IDs
    stats_req = tsi.AnnotationQueuesStatsReq(
        project_id=client._project_id(),
        queue_ids=[],
    )
    stats_res = client.server.annotation_queues_stats(stats_req)

    # Should return empty stats list
    assert len(stats_res.stats) == 0
