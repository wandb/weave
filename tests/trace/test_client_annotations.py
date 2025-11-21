"""Tests for annotation queue APIs.

These tests cover the queue-based call annotation system introduced in
commit 7fd5bfd24bccce8f97449bee1676ac55e74fd993.
"""

import pytest

import weave
from tests.trace.util import client_is_sqlite
from weave.trace_server import trace_server_interface as tsi


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
