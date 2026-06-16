import base64
import time

import pytest

import weave
from tests.trace.server_utils import TEST_ENTITY
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy


def generate_objects(weave_client: WeaveClient, obj_count: int, version_count: int):
    for i in range(obj_count):
        for j in range(version_count):
            weave.publish({"i": i, "j": j}, name=f"obj_{i}")


def test_objs_query_filters_over_shared_fixture(client: WeaveClient):
    """Against 10 objects x 10 versions: all/object_ids/is_op/latest_only/metadata_only filters."""
    generate_objects(client, 10, 10)
    project_id = client.project_id

    all_res = client.server.objs_query(tsi.ObjQueryReq(project_id=project_id))
    assert len(all_res.objs) == 100

    ids_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(object_ids=["obj_0", "obj_1"]),
        )
    )
    assert len(ids_res.objs) == 20
    assert all(obj.object_id in {"obj_0", "obj_1"} for obj in ids_res.objs)

    op_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id, filter=tsi.ObjectVersionFilter(is_op=True)
        )
    )
    assert len(op_res.objs) == 0
    non_op_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id, filter=tsi.ObjectVersionFilter(is_op=False)
        )
    )
    assert len(non_op_res.objs) == 100

    latest_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(latest_only=True),
        )
    )
    assert len(latest_res.objs) == 10
    assert all(obj.is_latest for obj in latest_res.objs)
    assert all(obj.val["j"] == 9 for obj in latest_res.objs)

    meta_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(latest_only=True),
            metadata_only=True,
        )
    )
    assert len(meta_res.objs) == 10
    assert all(obj.val == {} for obj in meta_res.objs)
    full_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=project_id,
            filter=tsi.ObjectVersionFilter(latest_only=True),
            metadata_only=False,
        )
    )
    assert len(full_res.objs) == 10
    assert all(obj.val for obj in full_res.objs)


@pytest.mark.parametrize("sort_field", ["created_at", "object_id"])
def test_objs_query_filter_limit_offset_sort(client: WeaveClient, sort_field: str):
    """limit/offset with desc and asc sort by created_at or object_id (same order here)."""
    generate_objects(client, 10, 10)

    desc_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=True),
            limit=3,
            offset=5,
            sort_by=[SortBy(field=sort_field, direction="desc")],
        )
    )
    assert len(desc_res.objs) == 3
    assert all(obj.is_latest for obj in desc_res.objs)
    assert [obj.val["i"] for obj in desc_res.objs] == [4, 3, 2]
    assert all(obj.val["j"] == 9 for obj in desc_res.objs)

    asc_res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=True),
            limit=3,
            offset=5,
            sort_by=[SortBy(field=sort_field, direction="asc")],
        )
    )
    assert len(asc_res.objs) == 3
    assert all(obj.is_latest for obj in asc_res.objs)
    assert [obj.val["i"] for obj in asc_res.objs] == [5, 6, 7]
    assert all(obj.val["j"] == 9 for obj in asc_res.objs)


def test_objs_query_wb_user_id(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    correct_id = base64.b64encode(TEST_ENTITY.encode()).decode()

    res = client._objects()
    assert len(res) == 3
    assert all(obj.wb_user_id == correct_id for obj in res)


@pytest.mark.flaky(reruns=3)
def test_objs_query_deleted_interaction(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3
    assert all(obj.val["i"] in {1, 2, 3} for obj in res.objs)

    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id="obj_1",
            digests=[res.objs[0].digest],
        )
    )

    assert res.num_deleted == 1

    # Allow ClickHouse ReplacingMergeTree to settle after soft delete
    time.sleep(0.2)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert all(obj.val["i"] in {2, 3} for obj in res.objs)

    # Delete the remaining objects
    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id="obj_1",
            digests=[res.objs[0].digest, res.objs[1].digest],
        )
    )
    assert res.num_deleted == 2

    # Allow ClickHouse ReplacingMergeTree to settle after soft delete
    time.sleep(0.2)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 0


@pytest.mark.flaky(reruns=3)
def test_objs_query_delete_and_recreate(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3

    original_created_at = res.objs[0].created_at

    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id="obj_1",
        )
    )
    assert res.num_deleted == 3

    weave.publish({"i": 1}, name="obj_1")

    # Allow ClickHouse ReplacingMergeTree to settle after delete+recreate
    time.sleep(0.2)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].val["i"] == 1
    assert res.objs[0].created_at > original_created_at

    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    # Allow ClickHouse ReplacingMergeTree to settle after recreating versions
    time.sleep(0.2)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3

    for i in range(3):
        assert res.objs[i].val["i"] == i + 1


@pytest.mark.flaky(reruns=3)
def test_objs_query_delete_and_add_new_versions(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3

    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
            object_id="obj_1",
        )
    )

    weave.publish({"i": 4}, name="obj_1")
    weave.publish({"i": 5}, name="obj_1")
    weave.publish({"i": 6}, name="obj_1")

    # Allow ClickHouse ReplacingMergeTree to settle after delete+recreate
    time.sleep(0.2)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3
    assert all(obj.val["i"] in {4, 5, 6} for obj in res.objs)


def test_publish_model_query_no_ref(client: WeaveClient):
    class MyModel(weave.Model):
        @weave.op
        def predict(self, x: int) -> int:
            return x

    model = MyModel()
    ref = weave.publish(model)
    res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"object_ids": [ref.name]},
            }
        )
    )
    assert len(res.objs) == 1
    assert "ref" not in res.objs[0].val
