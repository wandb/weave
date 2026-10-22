"""Tests for WeaveClient annotation queue convenience methods."""

import datetime

import pytest

from weave.trace.call import Call
from weave.trace.weave_client import WeaveClient
from weave.trace_server.common_interface import AnnotationQueueItemsFilter, SortBy
from weave.trace_server.errors import NotFoundError
from weave.trace_server.trace_server_interface import (
    AnnotationQueueAddCallsRes,
    AnnotationQueueCreateRes,
    AnnotationQueueDeleteRes,
    AnnotationQueueItemSchema,
    AnnotationQueueItemsQueryRes,
    AnnotationQueueReadRes,
    AnnotationQueueSchema,
    AnnotationQueuesStatsRes,
    AnnotationQueueStatsSchema,
    AnnotationQueueUpdateRes,
)


class FakeAnnotationQueueServer:
    def __init__(self) -> None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self.queue = AnnotationQueueSchema(
            id="queue-id",
            project_id="entity/project",
            name="Test Queue",
            description="Queue description",
            scorer_refs=["weave:///entity/project/object/scorer:abc123"],
            created_at=now,
            created_by="test-user",
            updated_at=now,
            deleted_at=None,
        )
        self.item = AnnotationQueueItemSchema(
            id="item-id",
            project_id="entity/project",
            queue_id="queue-id",
            call_id="call-id",
            call_started_at=now,
            call_op_name="test_op",
            call_trace_id="trace-id",
            display_fields=["inputs.prompt", "output.text"],
            annotation_state="unstarted",
            created_at=now,
            created_by="test-user",
            updated_at=now,
        )
        self.stat = AnnotationQueueStatsSchema(
            queue_id="queue-id",
            total_items=1,
            completed_items=0,
        )
        self.requests = {}

    def annotation_queue_create(self, req):
        self.requests["create"] = req
        return AnnotationQueueCreateRes(id="queue-id")

    def annotation_queue_read(self, req):
        self.requests["read"] = req
        return AnnotationQueueReadRes(queue=self.queue)

    def annotation_queues_query_stream(self, req):
        self.requests["query"] = req
        return iter([self.queue])

    def annotation_queue_update(self, req):
        self.requests["update"] = req
        return AnnotationQueueUpdateRes(queue=self.queue)

    def annotation_queue_delete(self, req):
        self.requests["delete"] = req
        return AnnotationQueueDeleteRes(queue=self.queue)

    def annotation_queue_add_calls(self, req):
        self.requests["add_calls"] = req
        return AnnotationQueueAddCallsRes(added_count=1, duplicates=0)

    def annotation_queue_items_query(self, req):
        self.requests["items_query"] = req
        return AnnotationQueueItemsQueryRes(items=[self.item])

    def annotation_queues_stats(self, req):
        self.requests["stats"] = req
        return AnnotationQueuesStatsRes(stats=[self.stat])


def test_annotation_queue_sdk_methods_build_requests():
    server = FakeAnnotationQueueServer()
    client = WeaveClient(
        "entity",
        "project",
        server,  # type: ignore[arg-type]
        ensure_project_exists=False,
    )
    scorer_refs = ["weave:///entity/project/object/scorer:abc123"]

    queue_id = client.create_annotation_queue(
        name="Test Queue",
        description="Queue description",
        scorer_refs=scorer_refs,
    )
    assert queue_id == "queue-id"
    assert server.requests["create"] == {
        "project_id": "entity/project",
        "name": "Test Queue",
        "description": "Queue description",
        "scorer_refs": scorer_refs,
        "wb_user_id": None,
    }

    queue = client.get_annotation_queue("queue-id")
    assert queue is server.queue
    assert server.requests["read"] == {
        "project_id": "entity/project",
        "queue_id": "queue-id",
    }

    sort_by = [SortBy(field="updated_at", direction="desc")]
    queues = client.list_annotation_queues(
        name="Test",
        sort_by=sort_by,
        limit=10,
        offset=2,
    )
    assert queues == [server.queue]
    # A weave.shared SortBy goes out as its dump.
    assert server.requests["query"] == {
        "project_id": "entity/project",
        "name": "Test",
        "sort_by": [{"field": "updated_at", "direction": "desc"}],
        "limit": 10,
        "offset": 2,
    }

    updated_queue = client.update_annotation_queue(
        "queue-id",
        name="Updated Queue",
        description="Updated description",
        scorer_refs=scorer_refs,
    )
    assert updated_queue is server.queue
    assert server.requests["update"] == {
        "project_id": "entity/project",
        "queue_id": "queue-id",
        "name": "Updated Queue",
        "description": "Updated description",
        "scorer_refs": scorer_refs,
    }

    deleted_queue = client.delete_annotation_queue("queue-id")
    assert deleted_queue is server.queue
    assert server.requests["delete"] == {
        "project_id": "entity/project",
        "queue_id": "queue-id",
    }

    add_res = client.add_calls_to_annotation_queue(
        "queue-id",
        call_ids=["call-id"],
        display_fields=["inputs.prompt", "output.text"],
    )
    assert add_res.added_count == 1
    assert add_res.duplicates == 0
    assert server.requests["add_calls"] == {
        "project_id": "entity/project",
        "call_ids": ["call-id"],
        "display_fields": ["inputs.prompt", "output.text"],
        "queue_id": "queue-id",
    }

    item_filter = AnnotationQueueItemsFilter(call_id="call-id")
    items = client.list_annotation_queue_items(
        "queue-id",
        filter=item_filter,
        sort_by=sort_by,
        limit=5,
        offset=1,
        include_position=True,
    )
    assert items == [server.item]
    assert server.requests["items_query"] == {
        "project_id": "entity/project",
        "filter": item_filter.model_dump(),
        "sort_by": [{"field": "updated_at", "direction": "desc"}],
        "limit": 5,
        "offset": 1,
        "include_position": True,
        "queue_id": "queue-id",
    }

    stats = client.get_annotation_queue_stats(["queue-id"])
    assert stats == [server.stat]
    assert server.requests["stats"] == {
        "project_id": "entity/project",
        "queue_ids": ["queue-id"],
    }


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
    scorer_refs = [f"weave:///{client.project_id}/scorer/sdk_test:abc123"]

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

    queues = client.list_annotation_queues(name="sdk test")
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

    items = client.list_annotation_queue_items(
        queue_id,
        sort_by=[SortBy(field="created_at", direction="asc")],
        include_position=True,
    )
    assert {item.call_id for item in items} == {call.id for call in calls}
    assert [item.display_fields for item in items] == [
        ["inputs.prompt", "output.text"],
        ["inputs.prompt", "output.text"],
    ]
    assert [item.position_in_queue for item in items] == [1, 2]

    filtered_items = client.list_annotation_queue_items(
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
