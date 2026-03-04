"""Tests for annotation queue APIs.

These tests cover the queue-based call annotation system introduced in
commit 7fd5bfd24bccce8f97449bee1676ac55e74fd993.
"""

import base64
import datetime
import time
from typing import NamedTuple

import pytest

import weave
from tests.trace.util import client_is_sqlite
from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import AnnotationQueueItemsFilter, SortBy
from weave.trace_server.errors import NotFoundError
from weave.trace_server.ids import generate_id
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


class CallsFixture(NamedTuple):
    """Container for test calls data."""

    call_ids: list[str]
    calls: list


class QueueWithCallsFixture(NamedTuple):
    """Container for queue with calls data."""

    queue_id: str
    call_ids: list[str]
    calls: list


# Utility functions for test setup


def create_test_calls(
    client, count: int, op_name_prefix: str = "test_op"
) -> CallsFixture:
    """Create test calls and return their IDs.

    Args:
        client: Weave client instance
        count: Number of calls to create
        op_name_prefix: Prefix for the operation name

    Returns:
        CallsFixture with call_ids and calls list
    """

    @weave.op(name=f"{op_name_prefix}_{count}")
    def test_op(x: int) -> int:
        return x * 2

    for i in range(count):
        test_op(i)

    calls = list(client.get_calls())
    # Get only the calls we just created (last 'count' calls)
    new_calls = calls[-count:] if len(calls) >= count else calls
    call_ids = [call.id for call in new_calls]

    return CallsFixture(call_ids=call_ids, calls=new_calls)


def create_annotation_queue(
    client,
    name: str = "Test Queue",
    description: str | None = "A test annotation queue",
    scorer_refs: list[str] | None = None,
) -> str:
    """Create an annotation queue and return its ID.

    Args:
        client: Weave client instance
        name: Queue name
        description: Queue description
        scorer_refs: List of scorer references

    Returns:
        Queue ID
    """
    if scorer_refs is None:
        scorer_refs = ["weave:///entity/project/scorer/test:abc123"]

    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name=name,
        description=description,
        scorer_refs=scorer_refs,
        wb_user_id="test_user",
    )

    create_res = client.server.annotation_queue_create(create_req)
    return create_res.id


def create_queue_with_calls(
    client,
    num_calls: int = 5,
    queue_name: str = "Test Queue",
    display_fields: list[str] | None = None,
) -> QueueWithCallsFixture:
    """Create a queue and add calls to it.

    Args:
        client: Weave client instance
        num_calls: Number of calls to create and add
        queue_name: Name for the queue
        display_fields: Fields to display (defaults to ["input.x", "output"])

    Returns:
        QueueWithCallsFixture containing queue_id, call_ids, and calls
    """
    if display_fields is None:
        display_fields = ["input.x", "output"]

    # Create calls
    calls_fixture = create_test_calls(client, num_calls, op_name_prefix=queue_name)

    # Create queue
    queue_id = create_annotation_queue(client, name=queue_name)

    # Add calls to queue
    add_req = tsi.AnnotationQueueAddCallsReq(
        project_id=client._project_id(),
        queue_id=queue_id,
        call_ids=calls_fixture.call_ids,
        display_fields=display_fields,
        wb_user_id="test_user",
    )
    client.server.annotation_queue_add_calls(add_req)

    return QueueWithCallsFixture(
        queue_id=queue_id,
        call_ids=calls_fixture.call_ids,
        calls=calls_fixture.calls,
    )


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


def test_annotation_queue_update_all_fields(client):
    """Test updating all fields of an annotation queue."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Original Queue",
        description="Original description",
        scorer_refs=["weave:///entity/project/scorer/original:abc123"],
        wb_user_id="test_user_123",
    )
    create_res = client.server.annotation_queue_create(create_req)
    original_queue_id = create_res.id

    # Update all fields
    update_req = tsi.AnnotationQueueUpdateReq(
        project_id=client._project_id(),
        queue_id=original_queue_id,
        name="Updated Queue",
        description="Updated description",
        scorer_refs=[
            "weave:///entity/project/scorer/new1:def456",
            "weave:///entity/project/scorer/new2:ghi789",
        ],
        wb_user_id="test_user_123",
    )
    update_res = client.server.annotation_queue_update(update_req)

    # Verify update response
    assert update_res.queue.id == original_queue_id
    assert update_res.queue.name == "Updated Queue"
    assert update_res.queue.description == "Updated description"
    assert len(update_res.queue.scorer_refs) == 2
    assert "weave:///entity/project/scorer/new1:def456" in update_res.queue.scorer_refs
    assert "weave:///entity/project/scorer/new2:ghi789" in update_res.queue.scorer_refs
    assert update_res.queue.created_by == "test_user_123"
    assert update_res.queue.deleted_at is None

    # Read back to verify persistence
    read_req = tsi.AnnotationQueueReadReq(
        project_id=client._project_id(),
        queue_id=original_queue_id,
    )
    read_res = client.server.annotation_queue_read(read_req)

    assert read_res.queue.name == "Updated Queue"
    assert read_res.queue.description == "Updated description"
    assert len(read_res.queue.scorer_refs) == 2


def test_annotation_queue_update_partial(client):
    """Test updating only some fields (partial update)."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Original Queue",
        description="Original description",
        scorer_refs=["weave:///entity/project/scorer/test:abc123"],
        wb_user_id="test_user_123",
    )
    create_res = client.server.annotation_queue_create(create_req)
    original_queue_id = create_res.id

    # Update only name
    update_req = tsi.AnnotationQueueUpdateReq(
        project_id=client._project_id(),
        queue_id=original_queue_id,
        name="New Name Only",
        description=None,  # Not updating
        scorer_refs=None,  # Not updating
        wb_user_id="test_user_123",
    )
    update_res = client.server.annotation_queue_update(update_req)

    # Verify only name changed
    assert update_res.queue.name == "New Name Only"
    assert update_res.queue.description == "Original description"
    assert update_res.queue.scorer_refs == [
        "weave:///entity/project/scorer/test:abc123"
    ]


def test_annotation_queue_update_nonexistent(client):
    """Test updating a non-existent queue raises NotFoundError."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Try to update a non-existent queue
    update_req = tsi.AnnotationQueueUpdateReq(
        project_id=client._project_id(),
        queue_id=generate_id(),  # Random non-existent ID
        name="New Name",
        wb_user_id="test_user_123",
    )

    with pytest.raises(NotFoundError):
        client.server.annotation_queue_update(update_req)


def test_annotation_queue_update_no_fields(client):
    """Test updating with no fields provided returns existing queue."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create a queue
    create_req = tsi.AnnotationQueueCreateReq(
        project_id=client._project_id(),
        name="Test Queue",
        description="Test description",
        scorer_refs=["weave:///entity/project/scorer/test:abc123"],
        wb_user_id="test_user_123",
    )
    create_res = client.server.annotation_queue_create(create_req)
    original_queue_id = create_res.id

    # Update with no fields
    update_req = tsi.AnnotationQueueUpdateReq(
        project_id=client._project_id(),
        queue_id=original_queue_id,
        name=None,
        description=None,
        scorer_refs=None,
        wb_user_id="test_user_123",
    )
    update_res = client.server.annotation_queue_update(update_req)

    # Verify nothing changed
    assert update_res.queue.id == original_queue_id
    assert update_res.queue.name == "Test Queue"
    assert update_res.queue.description == "Test description"
    assert update_res.queue.scorer_refs == [
        "weave:///entity/project/scorer/test:abc123"
    ]


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


def test_annotation_queue_items_query_basic(client):
    """Test basic querying of annotation queue items."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Items Query Test Queue"
    )

    # Query items
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Verify we got all 5 items
    assert len(query_res.items) == 5

    # Verify item structure
    for item in query_res.items:
        assert item.id is not None
        assert item.queue_id == fixture.queue_id
        assert item.call_id in fixture.call_ids
        assert item.display_fields == ["input.x", "output"]
        assert item.added_by == "test_user"
        assert item.deleted_at is None


def test_annotation_queue_items_query_with_pagination(client):
    """Test querying queue items with limit and offset."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 10 calls
    fixture = create_queue_with_calls(
        client, num_calls=10, queue_name="Items Pagination Queue"
    )

    # Query first page (limit 3)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        limit=3,
        offset=0,
    )
    page1_res = client.server.annotation_queue_items_query(query_req)
    assert len(page1_res.items) == 3

    # Query second page (offset 3)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        limit=3,
        offset=3,
    )
    page2_res = client.server.annotation_queue_items_query(query_req)
    assert len(page2_res.items) == 3

    # Pages should have different items
    page1_ids = {item.id for item in page1_res.items}
    page2_ids = {item.id for item in page2_res.items}
    assert page1_ids.isdisjoint(page2_ids)


def test_annotation_queue_items_query_with_sorting(client):
    """Test querying queue items with different sort orders."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 3 calls
    fixture = create_queue_with_calls(
        client,
        num_calls=3,
        queue_name="Items Sorting Queue",
        display_fields=["input.x"],
    )

    # Query with default sort (created_at ASC)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Items should be sorted by created_at ascending
    for i in range(len(query_res.items) - 1):
        assert query_res.items[i].created_at <= query_res.items[i + 1].created_at

    # Query with call_started_at DESC sort
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        sort_by=[SortBy(field="call_started_at", direction="desc")],
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Items should be sorted by call_started_at descending
    for i in range(len(query_res.items) - 1):
        assert (
            query_res.items[i].call_started_at >= query_res.items[i + 1].call_started_at
        )


def test_annotation_queue_items_query_empty_queue(client):
    """Test querying items from an empty queue."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create an empty queue
    queue_id = create_annotation_queue(client, name="Empty Items Queue")

    # Query items from empty queue
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return empty list
    assert len(query_res.items) == 0


def test_annotation_queue_items_query_with_multiple_sort_fields(client):
    """Test querying with multiple sort fields."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Multi Sort Queue"
    )

    # Query with multiple sort fields
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        sort_by=[
            SortBy(field="call_op_name", direction="asc"),
            SortBy(field="created_at", direction="desc"),
        ],
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return all items
    assert len(query_res.items) == 5


def test_annotation_queue_items_query_filter_by_call_id(client):
    """Test filtering queue items by call_id."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter By Call ID Queue"
    )

    # Pick one call_id to filter by
    target_call_id = fixture.call_ids[2]

    # Query with call_id filter
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(call_id=target_call_id),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return only 1 item
    assert len(query_res.items) == 1
    assert query_res.items[0].call_id == target_call_id


def test_annotation_queue_items_query_filter_by_call_op_name(client):
    """Test filtering queue items by call_op_name."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create two different sets of calls with different op names
    fixture1 = create_queue_with_calls(
        client, num_calls=3, queue_name="Filter Op Name Queue A"
    )
    fixture2 = create_queue_with_calls(
        client, num_calls=2, queue_name="Filter Op Name Queue B"
    )

    # Get the op_name from first fixture
    calls = list(client.get_calls())
    target_op_name = None
    for call in calls:
        if call.id in fixture1.call_ids:
            target_op_name = call.op_name
            break

    assert target_op_name is not None

    # Query fixture1's queue filtered by op_name
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture1.queue_id,
        filter=AnnotationQueueItemsFilter(call_op_name=target_op_name),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return all items from fixture1 (they all have same op_name)
    assert len(query_res.items) == 3
    for item in query_res.items:
        assert item.call_op_name == target_op_name


def test_annotation_queue_items_query_filter_by_call_trace_id(client):
    """Test filtering queue items by call_trace_id."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter By Trace ID Queue"
    )

    # Get trace_id from one of the calls
    calls = list(client.get_calls())
    target_trace_id = None
    for call in calls:
        if call.id in fixture.call_ids:
            target_trace_id = call.trace_id
            break

    assert target_trace_id is not None

    # Query with trace_id filter
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(call_trace_id=target_trace_id),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return at least 1 item (might be more if multiple calls share trace)
    assert len(query_res.items) >= 1
    for item in query_res.items:
        assert item.call_trace_id == target_trace_id


def test_annotation_queue_items_query_filter_by_added_by(client):
    """Test filtering queue items by added_by."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls added by test_user
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter By Added By Queue"
    )

    # Query with added_by filter
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(added_by="test_user"),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return all 5 items
    assert len(query_res.items) == 5
    for item in query_res.items:
        assert item.added_by == "test_user"

    # Query with non-existent added_by
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(added_by="nonexistent_user"),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return no items
    assert len(query_res.items) == 0


def test_annotation_queue_items_query_filter_by_annotation_states(client):
    """Test filtering queue items by annotation_states.

    Note: This test only validates filtering for 'unstarted' state.
    Tests for other states (in_progress, completed, skipped) will be added
    once the queue item progress update API is available.
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter By States Queue"
    )

    # Query for unstarted items (all items should be unstarted initially)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(annotation_states=["unstarted"]),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return all 5 items
    assert len(query_res.items) == 5
    for item in query_res.items:
        assert item.annotation_state == "unstarted"

    # Query for completed items (should be none)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(annotation_states=["completed"]),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return no items
    assert len(query_res.items) == 0


def test_annotation_queue_items_query_filter_combined(client):
    """Test filtering queue items with multiple filters combined."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter Combined Queue"
    )

    # Get call info
    calls = list(client.get_calls())
    target_call = None
    for call in calls:
        if call.id in fixture.call_ids:
            target_call = call
            break

    assert target_call is not None

    # Query with multiple filters: call_id + added_by + annotation_states
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(
            call_id=target_call.id,
            added_by="test_user",
            annotation_states=["unstarted"],
        ),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return exactly 1 item matching all criteria
    assert len(query_res.items) == 1
    assert query_res.items[0].call_id == target_call.id
    assert query_res.items[0].added_by == "test_user"
    assert query_res.items[0].annotation_state == "unstarted"

    # Query with conflicting filters (specific call_id + wrong annotation state)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(
            call_id=target_call.id,
            annotation_states=["completed"],  # Item is unstarted, not completed
        ),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return no items
    assert len(query_res.items) == 0


def test_annotation_queue_items_query_filter_empty_results(client):
    """Test filtering queue items that returns no results."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter Empty Results Queue"
    )

    # Query with non-existent call_id
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(call_id="nonexistent_call_id"),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return no items
    assert len(query_res.items) == 0

    # Query with non-existent op_name
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(call_op_name="NonexistentOp"),
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return no items
    assert len(query_res.items) == 0


def test_annotation_queue_items_query_filter_with_pagination(client):
    """Test filtering with pagination."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 10 calls
    fixture = create_queue_with_calls(
        client, num_calls=10, queue_name="Filter With Pagination Queue"
    )

    # Query for unstarted items with limit
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(annotation_states=["unstarted"]),
        limit=3,
        offset=0,
    )
    page1_res = client.server.annotation_queue_items_query(query_req)

    # Should return 3 items
    assert len(page1_res.items) == 3

    # Query second page
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(annotation_states=["unstarted"]),
        limit=3,
        offset=3,
    )
    page2_res = client.server.annotation_queue_items_query(query_req)

    # Should return 3 different items
    assert len(page2_res.items) == 3
    page1_ids = {item.id for item in page1_res.items}
    page2_ids = {item.id for item in page2_res.items}
    assert page1_ids.isdisjoint(page2_ids)


def test_annotation_queue_items_query_filter_with_sorting(client):
    """Test filtering with sorting."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Filter With Sorting Queue"
    )

    # Query with filter and sort
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(
            added_by="test_user", annotation_states=["unstarted"]
        ),
        sort_by=[SortBy(field="call_started_at", direction="desc")],
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return all 5 items sorted by call_started_at descending
    assert len(query_res.items) == 5
    for i in range(len(query_res.items) - 1):
        assert (
            query_res.items[i].call_started_at >= query_res.items[i + 1].call_started_at
        )


def test_annotation_queue_items_query_with_position_basic(client):
    """Test querying queue items with position tracking enabled."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Position Basic Queue"
    )

    # Query items with include_position=True
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        include_position=True,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Verify we got all 5 items
    assert len(query_res.items) == 5

    # Verify position_in_queue is present and sequential (1-based)
    for i, item in enumerate(query_res.items):
        assert item.position_in_queue is not None
        assert item.position_in_queue == i + 1  # 1-based indexing

    # Verify positions are 1 through 5
    positions = {item.position_in_queue for item in query_res.items}
    assert positions == {1, 2, 3, 4, 5}


def test_annotation_queue_items_query_without_position(client):
    """Test that position_in_queue is None when include_position=False."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 3 calls
    fixture = create_queue_with_calls(
        client, num_calls=3, queue_name="No Position Queue"
    )

    # Query items without include_position (defaults to False)
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Verify position_in_queue is None for all items
    assert len(query_res.items) == 3
    for item in query_res.items:
        assert item.position_in_queue is None


def test_annotation_queue_items_query_position_with_sorting(client):
    """Test that position respects custom sort order."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Position With Sort Queue"
    )

    # Query with DESC sort and position
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        sort_by=[SortBy(field="call_started_at", direction="desc")],
        include_position=True,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Verify positions are still sequential 1-5 in the DESC order
    assert len(query_res.items) == 5
    for i, item in enumerate(query_res.items):
        assert item.position_in_queue == i + 1

    # Verify items are sorted by call_started_at DESC
    for i in range(len(query_res.items) - 1):
        assert (
            query_res.items[i].call_started_at >= query_res.items[i + 1].call_started_at
        )


def test_annotation_queue_items_query_position_with_filter_unstarted(client):
    """Test position calculation with annotation_states filter.

    Position should be calculated on the full unfiltered result set,
    then the filter is applied. This allows users to see the true
    position of items in the queue even when viewing a filtered subset.
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Position With Filter Queue"
    )

    # All items are initially unstarted
    # Query with filter for unstarted and position
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        filter=AnnotationQueueItemsFilter(annotation_states=["unstarted"]),
        include_position=True,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Should return all 5 items with positions 1-5
    assert len(query_res.items) == 5
    positions = sorted([item.position_in_queue for item in query_res.items])
    assert positions == [1, 2, 3, 4, 5]


# ============================================================================
# Tests for annotator_queue_items_progress_update
# ============================================================================


def test_annotator_queue_items_progress_update_completed(client):
    """Test updating queue item state to 'completed'."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="Progress Update Completed Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # Verify initial state is unstarted with no annotator
    # ClickHouse String default value is empty string, not NULL
    assert item.annotation_state == "unstarted"
    assert item.annotator_user_id == ""

    # Update state to completed
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="completed",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)

    # Verify response contains updated item with annotator_user_id
    # Note: wb_user_id is stored in base64 format in the database
    expected_annotator_id = base64.b64encode(b"test_annotator").decode()
    assert update_res.item.id == item.id
    assert update_res.item.annotation_state == "completed"
    assert update_res.item.annotator_user_id == expected_annotator_id

    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )

    # Query again to verify the state and annotator_user_id persisted
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    assert query_res.items[0].annotation_state == "completed"
    assert query_res.items[0].annotator_user_id == expected_annotator_id


def test_annotator_queue_items_progress_update_skipped(client):
    """Test updating queue item state to 'skipped'."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="Progress Update Skipped Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # Update state to skipped
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="skipped",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)

    # Verify response contains updated item
    assert update_res.item.id == item.id
    assert update_res.item.annotation_state == "skipped"


def test_annotator_queue_items_progress_update_invalid_state(client):
    """Test that updating to invalid state raises error."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="Invalid State Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    item = query_res.items[0]

    # Try to update to invalid state
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="invalid_state",
        wb_user_id="test_annotator",
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="Invalid annotation_state"):
        client.server.annotator_queue_items_progress_update(update_req)


def test_annotator_queue_items_progress_update_nonexistent_item(client):
    """Test that updating nonexistent item raises error."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create an empty queue
    queue_id = create_annotation_queue(client, name="Nonexistent Item Queue")

    # Try to update nonexistent item
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=queue_id,
        item_id="nonexistent_item_id",
        annotation_state="completed",
        wb_user_id="test_annotator",
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="Queue item .* not found"):
        client.server.annotator_queue_items_progress_update(update_req)


def test_annotator_queue_items_progress_update_no_user_id(client):
    """Test that updating without user_id raises error."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="No User ID Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    item = query_res.items[0]

    # Try to update without user_id
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="completed",
        wb_user_id=None,
    )

    # Should raise ValueError
    with pytest.raises(ValueError, match="wb_user_id is required"):
        client.server.annotator_queue_items_progress_update(update_req)


def test_annotator_queue_items_progress_update_transition_from_in_progress(client):
    """Test valid state transition from in_progress to completed."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="Transition From In Progress Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    item = query_res.items[0]

    # First, mark as in_progress using the API
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="in_progress",
        wb_user_id="test_annotator",
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Verify state is in_progress
    # Create new query_req to avoid mutation issues
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert query_res.items[0].annotation_state == "in_progress"

    # Update from in_progress to completed should succeed
    # Create new update_req to avoid mutation issues
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="completed",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)

    # Verify state is now completed
    assert update_res.item.annotation_state == "completed"


def test_annotator_queue_items_progress_update_invalid_transition_from_completed(
    client,
):
    """Test invalid state transition from completed to skipped."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="Invalid Transition Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    item = query_res.items[0]

    # First, mark as completed
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="completed",
        wb_user_id="test_annotator",
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Try to transition from completed to skipped (should fail)
    update_req2 = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="skipped",
        wb_user_id="test_annotator",
    )

    # Should raise ValueError about invalid state transition
    with pytest.raises(ValueError, match="Invalid state transition"):
        client.server.annotator_queue_items_progress_update(update_req2)


@pytest.mark.parametrize("state", ["completed", "skipped"])
def test_annotator_queue_items_progress_update_idempotent(client, state):
    """Test that setting the same state twice is idempotent (no error, no-op).

    This simulates retry scenarios where the first request succeeded but the
    response was lost (e.g., network timeout).
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call - use unique queue name without state name
    # to avoid any potential name-based issues
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="State Idempotency Test Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # First call sets the state
    update_req1 = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state=state,
        wb_user_id="test_annotator",
    )
    update_res1 = client.server.annotator_queue_items_progress_update(update_req1)
    assert update_res1.item.annotation_state == state

    # Second call with same state should succeed (idempotent)
    # Note: Must create a new request object because the adapter mutates
    # req.project_id in place (external -> internal conversion)
    update_req2 = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state=state,
        wb_user_id="test_annotator",
    )
    update_res2 = client.server.annotator_queue_items_progress_update(update_req2)
    assert update_res2.item.annotation_state == state


def test_annotator_queue_items_progress_update_stats_integration(client):
    """Test that progress updates correctly affect queue stats."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 5 calls
    fixture = create_queue_with_calls(
        client, num_calls=5, queue_name="Stats Integration Queue"
    )

    # Get initial stats (should be 0 completed)
    stats_req = tsi.AnnotationQueuesStatsReq(
        project_id=client._project_id(),
        queue_ids=[fixture.queue_id],
    )
    stats_res = client.server.annotation_queues_stats(stats_req)
    assert len(stats_res.stats) == 1
    assert stats_res.stats[0].total_items == 5
    assert stats_res.stats[0].completed_items == 0

    # Get queue items
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)

    # Mark 2 items as completed
    for i in range(2):
        update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
            project_id=client._project_id(),
            queue_id=fixture.queue_id,
            item_id=query_res.items[i].id,
            annotation_state="completed",
            wb_user_id="test_annotator",
        )
        client.server.annotator_queue_items_progress_update(update_req)

    # Mark 1 item as skipped
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=query_res.items[2].id,
        annotation_state="skipped",
        wb_user_id="test_annotator",
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Get updated stats (should be 3 completed: 2 completed + 1 skipped)
    # Create new stats_req to avoid mutation issues
    stats_req = tsi.AnnotationQueuesStatsReq(
        project_id=client._project_id(),
        queue_ids=[fixture.queue_id],
    )
    stats_res = client.server.annotation_queues_stats(stats_req)
    assert len(stats_res.stats) == 1
    assert stats_res.stats[0].total_items == 5
    assert stats_res.stats[0].completed_items == 3


def test_annotator_queue_items_progress_update_in_progress_new(client):
    """Test updating queue item state to 'in_progress' for a new record."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="In Progress New Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # Verify initial state is unstarted
    assert item.annotation_state == "unstarted"

    # Update state to in_progress (should succeed for new record)
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="in_progress",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)

    # Verify response contains updated item
    assert update_res.item.id == item.id
    assert update_res.item.annotation_state == "in_progress"

    # Query again to verify the state persisted
    # Create new query_req to avoid mutation issues
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    assert query_res.items[0].annotation_state == "in_progress"


def test_annotator_queue_items_progress_update_in_progress_existing(client):
    """Test that in_progress -> in_progress is idempotent (no-op, succeeds)."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="In Progress Existing Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # First, mark it as in_progress
    update_req1 = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="in_progress",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req1)
    assert update_res.item.annotation_state == "in_progress"

    # Update to in_progress again - should be idempotent (succeed as no-op)
    # Note: Must create a new request object because the adapter mutates
    # req.project_id in place (external -> internal conversion)
    update_req2 = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="in_progress",
        wb_user_id="test_annotator",
    )
    update_res2 = client.server.annotator_queue_items_progress_update(update_req2)
    assert update_res2.item.annotation_state == "in_progress"


def test_annotator_queue_items_progress_update_in_progress_from_completed(client):
    """Test that completed -> in_progress fails (can't restart a finished item)."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="In Progress From Completed Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # First, mark it as completed
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="completed",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)
    assert update_res.item.annotation_state == "completed"

    # Try to transition from completed to in_progress (should fail)
    update_req2 = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="in_progress",
        wb_user_id="test_annotator",
    )
    with pytest.raises(Exception) as exc_info:
        client.server.annotator_queue_items_progress_update(update_req2)

    assert "Cannot transition to 'in_progress' when a record already exists" in str(
        exc_info.value
    )


def test_annotator_queue_items_progress_in_progress_to_completed(client):
    """Test transitioning from 'in_progress' to 'completed'."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 1 call
    fixture = create_queue_with_calls(
        client, num_calls=1, queue_name="In Progress to Completed Queue"
    )

    # Get the queue item
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    item = query_res.items[0]

    # First, mark it as in_progress
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="in_progress",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)
    assert update_res.item.annotation_state == "in_progress"

    # Now update to completed (should succeed)
    # Create new update_req to avoid mutation issues
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item.id,
        annotation_state="completed",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)
    assert update_res.item.annotation_state == "completed"

    # Query again to verify
    # Create new query_req to avoid mutation issues
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 1
    assert query_res.items[0].annotation_state == "completed"


def test_annotator_queue_items_progress_in_progress_workflow(client):
    """Test the full workflow: mark in_progress, then complete."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 3 calls
    fixture = create_queue_with_calls(
        client, num_calls=3, queue_name="In Progress Workflow Queue"
    )

    # Get queue items
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 3

    annotator = "workflow_annotator"

    # Workflow for item 1: mark in_progress, then complete
    item1_id = query_res.items[0].id
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item1_id,
        annotation_state="in_progress",
        wb_user_id=annotator,
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Complete item 1
    # Create new update_req to avoid mutation issues
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item1_id,
        annotation_state="completed",
        wb_user_id=annotator,
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Workflow for item 2: mark in_progress, then skip
    item2_id = query_res.items[1].id
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item2_id,
        annotation_state="in_progress",
        wb_user_id=annotator,
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Skip item 2
    # Create new update_req to avoid mutation issues
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item2_id,
        annotation_state="skipped",
        wb_user_id=annotator,
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Item 3: leave as in_progress
    item3_id = query_res.items[2].id
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=item3_id,
        annotation_state="in_progress",
        wb_user_id=annotator,
    )
    client.server.annotator_queue_items_progress_update(update_req)

    # Query all items and verify states
    # Create new query_req to avoid mutation issues
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 3

    # wb_user_id is stored in base64 format
    expected_annotator_id = base64.b64encode(annotator.encode()).decode()

    items_by_id = {item.id: item for item in query_res.items}
    assert items_by_id[item1_id].annotation_state == "completed"
    assert items_by_id[item1_id].annotator_user_id == expected_annotator_id
    assert items_by_id[item2_id].annotation_state == "skipped"
    assert items_by_id[item2_id].annotator_user_id == expected_annotator_id
    assert items_by_id[item3_id].annotation_state == "in_progress"
    assert items_by_id[item3_id].annotator_user_id == expected_annotator_id

    # Verify stats (completed count includes skipped)
    stats_req = tsi.AnnotationQueuesStatsReq(
        project_id=client._project_id(),
        queue_ids=[fixture.queue_id],
    )
    stats_res = client.server.annotation_queues_stats(stats_req)
    assert len(stats_res.stats) == 1
    assert stats_res.stats[0].total_items == 3
    # Completed count includes both 'completed' and 'skipped'
    assert stats_res.stats[0].completed_items == 2


def test_annotator_queue_items_progress_update_returns_correct_item(client):
    """Test that progress update returns the specific item that was updated."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create queue with 3 items - we need multiple items to expose the bug
    fixture = create_queue_with_calls(
        client, num_calls=3, queue_name="Returns Correct Item Queue"
    )

    # Get all queue items
    query_req = tsi.AnnotationQueueItemsQueryReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
    )
    query_res = client.server.annotation_queue_items_query(query_req)
    assert len(query_res.items) == 3

    items = query_res.items
    target_item = items[2]  # Update the last item, not the first
    first_item = items[0]

    assert target_item.id != first_item.id, "Test requires items to have different IDs"

    # Update the last item to completed
    update_req = tsi.AnnotatorQueueItemsProgressUpdateReq(
        project_id=client._project_id(),
        queue_id=fixture.queue_id,
        item_id=target_item.id,
        annotation_state="completed",
        wb_user_id="test_annotator",
    )
    update_res = client.server.annotator_queue_items_progress_update(update_req)

    # Verify the returned item is the one we updated
    assert update_res.item.id == target_item.id

    # Also verify the state was updated correctly
    assert update_res.item.annotation_state == "completed"


def test_annotation_queue_add_calls_with_calls_complete_table(trace_server):
    """Test adding calls to annotation queue when using calls_complete table.

    This test verifies that annotation_queue_add_calls correctly handles
    the calls_complete table by using the right query (no GROUP BY, no aggregation)
    when fetching call details to populate the annotation_queue_items table.

    Steps:
    1. Seed project with calls_complete data to establish COMPLETE_ONLY residence
    2. Create annotation queue
    3. Add calls to queue using annotation_queue_add_calls
    4. Verify items are correctly added with proper display_data
    5. Query items back to confirm correct data population
    """
    if isinstance(trace_server._internal_trace_server, SqliteTraceServer):
        pytest.skip("ClickHouse-only test")

    project_id = f"{TEST_ENTITY}/test_queue_add_calls_complete"

    # Step 1: Seed project with calls_complete data
    seed_calls = []
    started_at = datetime.datetime.now()

    for i in range(5):
        call_id = generate_id()
        seed_calls.append(
            tsi.CompletedCallSchemaForInsert(
                project_id=project_id,
                id=call_id,
                trace_id=generate_id(),
                op_name="test_calls_complete_add_to_queue",
                started_at=started_at,
                ended_at=started_at + datetime.timedelta(seconds=1),
                attributes={},
                inputs={"x": i, "name": f"call_{i}"},
                output={"result": i * 2},
                summary={"usage": {}, "status_counts": {}},
            )
        )

    call_ids = [call.id for call in seed_calls]
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=seed_calls))

    # Step 2: Verify calls are queryable
    all_calls = list(
        trace_server.calls_query_stream(tsi.CallsQueryReq(project_id=project_id))
    )
    assert len(all_calls) == 5, f"Expected 5 calls, got {len(all_calls)}"

    # Step 3: Create annotation queue
    queue_res = trace_server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=project_id,
            name="calls_complete_test_queue",
            description="Test queue for calls_complete table",
            scorer_refs=["weave:///entity/project/scorer/test:xyz"],
            wb_user_id="test_user",
        )
    )
    queue_id = queue_res.id

    # Step 4: Add 3 of the 5 calls to the queue with display_fields
    queue_call_ids = call_ids[:3]
    add_res = trace_server.annotation_queue_add_calls(
        tsi.AnnotationQueueAddCallsReq(
            project_id=project_id,
            queue_id=queue_id,
            call_ids=queue_call_ids,
            display_fields=["input.x", "input.name", "output.result"],
            wb_user_id="test_user",
        )
    )

    # Step 5: Verify add operation succeeded
    assert add_res.added_count == 3, (
        f"Expected 3 calls added, got {add_res.added_count}"
    )
    assert add_res.duplicates == 0, f"Expected 0 duplicates, got {add_res.duplicates}"

    # Step 6: Query queue items to verify they were added correctly
    items_res = trace_server.annotation_queue_items_query(
        tsi.AnnotationQueueItemsQueryReq(
            project_id=project_id,
            queue_id=queue_id,
        )
    )

    assert len(items_res.items) == 3, (
        f"Expected 3 queue items, got {len(items_res.items)}"
    )

    # Step 7: Verify each item has correct call_id and attributes
    items_by_call_id = {item.call_id: item for item in items_res.items}

    for call_id in queue_call_ids:
        assert call_id in items_by_call_id, f"Call {call_id} not found in queue items"
        item = items_by_call_id[call_id]

        # Verify the item has the correct queue_id
        assert item.queue_id == queue_id

        # Verify display_fields contains the requested fields
        # These fields were specified when adding calls to the queue
        assert item.display_fields == ["input.x", "input.name", "output.result"], (
            f"Item {item.id} has wrong display_fields: {item.display_fields}"
        )

        # Verify call_op_name was populated correctly from calls_complete table
        assert item.call_op_name == "test_calls_complete_add_to_queue", (
            f"Item {item.id} has wrong call_op_name: {item.call_op_name}"
        )

        # Verify call_started_at and call_trace_id were populated
        assert item.call_started_at is not None, (
            f"Item {item.id} has no call_started_at"
        )
        assert item.call_trace_id is not None, f"Item {item.id} has no call_trace_id"

    # Step 8: Verify stats reflect the added calls
    stats_res = trace_server.annotation_queues_stats(
        tsi.AnnotationQueuesStatsReq(
            project_id=project_id,
            queue_ids=[queue_id],
        )
    )

    assert len(stats_res.stats) == 1
    assert stats_res.stats[0].total_items == 3, (
        f"Expected 3 total items in stats, got {stats_res.stats[0].total_items}"
    )
    assert stats_res.stats[0].completed_items == 0, (
        f"Expected 0 completed items, got {stats_res.stats[0].completed_items}"
    )


def test_annotation_queue_read_nonexistent(client):
    """Test that reading a non-existent annotation queue raises NotFoundError.

    This test validates the iterator handling fix in annotation_queue_read where
    an empty result set (iterator with no items) correctly raises NotFoundError
    instead of raising StopIteration.
    """
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    project_id = client._project_id()
    nonexistent_queue_id = "00000000-0000-0000-0000-000000000000"

    # Attempt to read a queue that doesn't exist
    with pytest.raises(NotFoundError, match=f"Queue {nonexistent_queue_id} not found"):
        client.server.annotation_queue_read(
            tsi.AnnotationQueueReadReq(
                project_id=project_id,
                queue_id=nonexistent_queue_id,
            )
        )


# ============================================================================
# Tests for annotation_queue_delete
# ============================================================================


def test_annotation_queue_delete_basic(client):
    """Test complete deletion lifecycle: delete, verify response, verify cannot read/delete again."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create a queue
    queue_id = create_annotation_queue(
        client, name="Delete Test Queue", description="Queue to be deleted"
    )

    # Read the queue to verify it exists and capture original timestamps
    read_req = tsi.AnnotationQueueReadReq(
        project_id=client._project_id(),
        queue_id=queue_id,
    )
    read_res = client.server.annotation_queue_read(read_req)
    assert read_res.queue.id == queue_id
    assert read_res.queue.deleted_at is None
    original_created_at = read_res.queue.created_at

    # Delete the queue
    delete_req = tsi.AnnotationQueueDeleteReq(
        project_id=client._project_id(),
        queue_id=queue_id,
        wb_user_id="test_user",
    )
    delete_res = client.server.annotation_queue_delete(delete_req)

    # Verify response contains the deleted queue with deleted_at set
    assert delete_res.queue.id == queue_id
    assert delete_res.queue.name == "Delete Test Queue"
    assert delete_res.queue.description == "Queue to be deleted"
    assert delete_res.queue.deleted_at is not None
    assert delete_res.queue.updated_at is not None

    # Verify deleted_at and updated_at are timestamps
    assert isinstance(delete_res.queue.deleted_at, datetime.datetime)
    assert isinstance(delete_res.queue.updated_at, datetime.datetime)

    # Verify created_at doesn't change
    assert delete_res.queue.created_at == original_created_at

    # Verify deleted queue cannot be read
    read_req = tsi.AnnotationQueueReadReq(
        project_id=client._project_id(),
        queue_id=queue_id,
    )
    with pytest.raises(NotFoundError, match=f"Queue {queue_id} not found"):
        client.server.annotation_queue_read(read_req)

    # Verify already-deleted queue cannot be deleted again (idempotency)
    delete_req = tsi.AnnotationQueueDeleteReq(
        project_id=client._project_id(),
        queue_id=queue_id,
        wb_user_id="test_user",
    )
    with pytest.raises(
        NotFoundError, match=f"Queue {queue_id} not found or already deleted"
    ):
        client.server.annotation_queue_delete(delete_req)


def test_annotation_queue_delete_not_in_query(client):
    """Test that deleted queues don't appear in query results."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    # Create two queues
    queue1_id = create_annotation_queue(client, name="Queue 1")
    queue2_id = create_annotation_queue(client, name="Queue 2")

    # Query all queues - should see both
    query_req = tsi.AnnotationQueuesQueryReq(
        project_id=client._project_id(),
    )
    queues = list(client.server.annotation_queues_query_stream(query_req))
    queue_ids = {q.id for q in queues}
    assert queue1_id in queue_ids
    assert queue2_id in queue_ids

    # Delete queue1
    delete_req = tsi.AnnotationQueueDeleteReq(
        project_id=client._project_id(),
        queue_id=queue1_id,
        wb_user_id="test_user",
    )
    client.server.annotation_queue_delete(delete_req)

    # Query again - should only see queue2
    query_req = tsi.AnnotationQueuesQueryReq(
        project_id=client._project_id(),
    )
    queues = list(client.server.annotation_queues_query_stream(query_req))
    queue_ids = {q.id for q in queues}
    assert queue1_id not in queue_ids
    assert queue2_id in queue_ids


def test_annotation_queue_delete_nonexistent(client):
    """Test that deleting a non-existent queue raises NotFoundError."""
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    nonexistent_queue_id = "00000000-0000-0000-0000-000000000000"

    # Try to delete non-existent queue
    delete_req = tsi.AnnotationQueueDeleteReq(
        project_id=client._project_id(),
        queue_id=nonexistent_queue_id,
        wb_user_id="test_user",
    )

    with pytest.raises(
        NotFoundError,
        match=f"Queue {nonexistent_queue_id} not found or already deleted",
    ):
        client.server.annotation_queue_delete(delete_req)
