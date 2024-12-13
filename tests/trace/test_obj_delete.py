import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def _objs_query(client: WeaveClient, object_id: str) -> list[tsi.ObjSchema]:
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
        )
    )
    return objs.objs


def _obj_delete(client: WeaveClient, object_id: str, digests: list[str]) -> int:
    return client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id=object_id,
            digests=digests,
        )
    ).num_deleted


def test_delete_object_versions(client: WeaveClient):
    v0 = weave.publish({"i": 1}, name="obj_1")
    v1 = weave.publish({"i": 2}, name="obj_1")
    v2 = weave.publish({"i": 3}, name="obj_1")

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 3

    num_deleted = _obj_delete(client, "obj_1", [v0.digest])
    assert num_deleted == 1

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 2

    # test deleting an already deleted digest
    num_deleted = _obj_delete(client, "obj_1", [v0.digest])
    assert num_deleted == 0

    # test deleting a non-existent digest
    num_deleted = _obj_delete(client, "obj_1", ["non-existent-digest"])
    assert num_deleted == 0

    # test deleting multiple digests
    digests = [v1.digest, v2.digest]
    num_deleted = _obj_delete(client, "obj_1", digests)
    assert num_deleted == 2

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 0


def test_delete_all_object_versions(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    num_deleted = _obj_delete(client, "obj_1", None)
    assert num_deleted == 3

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 0

    num_deleted = _obj_delete(client, "obj_1", None)
    assert num_deleted == 0


def test_delete_version_correctness(client: WeaveClient):
    v0 = weave.publish({"i": 1}, name="obj_1")
    v1 = weave.publish({"i": 2}, name="obj_1")
    v2 = weave.publish({"i": 3}, name="obj_1")

    _obj_delete(client, "obj_1", [v1.digest])
    objs = _objs_query(client, "obj_1")
    assert len(objs) == 2
    assert objs[0].digest == v0.digest
    assert objs[0].val == {"i": 1}
    assert objs[0].version_index == 0
    assert objs[1].digest == v2.digest
    assert objs[1].val == {"i": 3}
    assert objs[1].version_index == 2

    v3 = weave.publish({"i": 4}, name="obj_1")
    assert len(objs) == 3
    assert objs[0].digest == v0.digest
    assert objs[0].val == {"i": 1}
    assert objs[0].version_index == 0
    assert objs[1].digest == v2.digest
    assert objs[1].val == {"i": 3}
    assert objs[1].version_index == 2
    assert objs[2].digest == v3.digest
    assert objs[2].val == {"i": 4}
    assert objs[2].version_index == 3

    _obj_delete(client, "obj_1", [v3.digest])
    objs = _objs_query(client, "obj_1")
    assert len(objs) == 2
    assert objs[0].digest == v0.digest
    assert objs[0].val == {"i": 1}
    assert objs[0].version_index == 0
    assert objs[1].digest == v2.digest
    assert objs[1].val == {"i": 3}
    assert objs[1].version_index == 2
