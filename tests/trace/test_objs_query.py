import base64

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def generate_objects(weave_client: WeaveClient, obj_count: int, version_count: int):
    for i in range(obj_count):
        for j in range(version_count):
            weave.publish({"i": i, "j": j}, name=f"obj_{i}")


def test_objs_query_all(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
        )
    )
    assert len(res.objs) == 100


def test_objs_query_filter_object_ids(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=["obj_0", "obj_1"]),
        )
    )
    assert len(res.objs) == 20
    assert all(obj.object_id in ["obj_0", "obj_1"] for obj in res.objs)


def test_objs_query_filter_is_op(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(), filter=tsi.ObjectVersionFilter(is_op=True)
        )
    )
    assert len(res.objs) == 0
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(), filter=tsi.ObjectVersionFilter(is_op=False)
        )
    )
    assert len(res.objs) == 100


def test_objs_query_filter_latest_only(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
        )
    )
    assert len(res.objs) == 10
    assert all(obj.is_latest for obj in res.objs)
    assert all(obj.val["j"] == 9 for obj in res.objs)


def test_objs_query_filter_limit_offset_sort_by_created_at(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
            limit=3,
            offset=5,
            sort_by=[tsi.SortBy(field="created_at", direction="desc")],
        )
    )
    assert len(res.objs) == 3
    assert all(obj.is_latest for obj in res.objs)
    assert res.objs[0].val["j"] == 9
    assert res.objs[0].val["i"] == 4
    assert res.objs[1].val["j"] == 9
    assert res.objs[1].val["i"] == 3
    assert res.objs[2].val["j"] == 9
    assert res.objs[2].val["i"] == 2

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
            limit=3,
            offset=5,
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
        )
    )
    assert len(res.objs) == 3
    assert all(obj.is_latest for obj in res.objs)
    assert res.objs[0].val["j"] == 9
    assert res.objs[0].val["i"] == 5
    assert res.objs[1].val["j"] == 9
    assert res.objs[1].val["i"] == 6
    assert res.objs[2].val["j"] == 9
    assert res.objs[2].val["i"] == 7


def test_objs_query_filter_limit_offset_sort_by_object_id(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
            limit=3,
            offset=5,
            sort_by=[tsi.SortBy(field="object_id", direction="desc")],
        )
    )
    assert len(res.objs) == 3
    assert all(obj.is_latest for obj in res.objs)
    assert res.objs[0].val["j"] == 9
    assert res.objs[0].val["i"] == 4
    assert res.objs[1].val["j"] == 9
    assert res.objs[1].val["i"] == 3
    assert res.objs[2].val["j"] == 9
    assert res.objs[2].val["i"] == 2

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
            limit=3,
            offset=5,
            sort_by=[tsi.SortBy(field="object_id", direction="asc")],
        )
    )
    assert len(res.objs) == 3
    assert all(obj.is_latest for obj in res.objs)
    assert res.objs[0].val["j"] == 9
    assert res.objs[0].val["i"] == 5
    assert res.objs[1].val["j"] == 9
    assert res.objs[1].val["i"] == 6
    assert res.objs[2].val["j"] == 9
    assert res.objs[2].val["i"] == 7


def test_objs_query_filter_metadata_only(client: WeaveClient):
    generate_objects(client, 10, 10)

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
            metadata_only=True,
        )
    )
    assert len(res.objs) == 10
    for obj in res.objs:
        assert obj.val == {}

    # sanity check that we get the full object when we don't ask for metadata only
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=True),
            metadata_only=False,
        )
    )
    assert len(res.objs) == 10
    for obj in res.objs:
        assert obj.val


def test_objs_query_wb_user_id(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    correct_id = base64.b64encode(bytes(client.server._user_id, "utf-8")).decode(
        "utf-8"
    )

    res = client._objects()
    assert len(res) == 3
    assert all(obj.wb_user_id == correct_id for obj in res)
