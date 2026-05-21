"""Tests for WeaveClient annotation queue convenience methods."""

import pytest

from tests.trace.util import client_is_sqlite
from weave.trace.call import Call
from weave.trace_server.common_interface import AnnotationQueueItemsFilter, SortBy
from weave.trace_server.errors import NotFoundError


def _create_finished_calls(client, count: int) -> list[Call]:
    calls = []
    for i in range(count):
        call = client.create_call(
            "annotation_queue_sdk_test_op",
            inputs={"prompt": f"prompt {i}"},
        )
        client.finish_call(call, output={"text": f"response {i}"})
        calls.append(call)
    client.flush()
    return calls


def test_annotation_queue_sdk_lifecycle(client):
    if client_is_sqlite(client):
        pytest.skip("Annotation queues not supported in SQLite")

    scorer_refs = ["weave:///entity/project/scorer/sdk_test:abc123"]

    queue_id = client.create_annotation_queue(
        name="SDK Test Queue",
        description="Created through WeaveClient",
        scorer_refs=scorer_refs,
    )

    queue = client.get_annotation_queue(queue_id)
    assert queue.id == queue_id
    assert queue.name == "SDK Test Queue"
    assert queue.description == "Created through WeaveClient"
    assert queue.scorer_refs == scorer_refs

    queues = client.get_annotation_queues(name="sdk test")
    assert any(q.id == queue_id for q in queues)

    updated_queue = client.update_annotation_queue(
        queue_id,
        name="Updated SDK Test Queue",
        description="Updated through WeaveClient",
    )
    assert updated_queue.id == queue_id
    assert updated_queue.name == "Updated SDK Test Queue"
    assert updated_queue.description == "Updated through WeaveClient"
    assert updated_queue.scorer_refs == scorer_refs

    calls = _create_finished_calls(client, 2)
    add_res = client.add_calls_to_annotation_queue(
        queue_id,
        call_ids=[call.id for call in calls],
        display_fields=["inputs.prompt", "output.text"],
    )
    assert add_res.added_count == 2
    assert add_res.duplicates == 0

    items = client.get_annotation_queue_items(
        queue_id,
        sort_by=[SortBy(field="created_at", direction="asc")],
        include_position=True,
    )
    assert [item.call_id for item in items] == [call.id for call in calls]
    assert [item.display_fields for item in items] == [
        ["inputs.prompt", "output.text"],
        ["inputs.prompt", "output.text"],
    ]
    assert [item.position_in_queue for item in items] == [1, 2]

    filtered_items = client.get_annotation_queue_items(
        queue_id,
        filter=AnnotationQueueItemsFilter(call_id=calls[0].id),
    )
    assert len(filtered_items) == 1
    assert filtered_items[0].call_id == calls[0].id

    stats = client.get_annotation_queue_stats([queue_id])
    assert len(stats) == 1
    assert stats[0].queue_id == queue_id
    assert stats[0].total_items == 2
    assert stats[0].completed_items == 0

    deleted_queue = client.delete_annotation_queue(queue_id)
    assert deleted_queue.id == queue_id
    assert deleted_queue.deleted_at is not None

    with pytest.raises(NotFoundError):
        client.get_annotation_queue(queue_id)
