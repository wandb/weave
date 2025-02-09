import pytest

import weave
from weave.trace.weave_client import WeaveClient
from weave.tsi import trace_server_interface as tsi


def _objs_query(client: WeaveClient, object_id: str) -> list[tsi.ObjSchema]:
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
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
    with pytest.raises(weave.trace_server.errors.NotFoundError):
        _obj_delete(client, "obj_1", [v0.digest])

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

    with pytest.raises(weave.trace_server.errors.NotFoundError):
        _obj_delete(client, "obj_1", None)


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
    objs = _objs_query(client, "obj_1")
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


def test_delete_object_max_limit(client: WeaveClient):
    # Create more than MAX_OBJECTS_TO_DELETE objects
    max_objs = 100
    digests = []
    for i in range(max_objs + 1):
        digests.append(f"test_{i}")

    with pytest.raises(
        ValueError, match=f"Please delete {max_objs} or fewer objects at a time"
    ):
        _obj_delete(client, "obj_1", digests)


def test_delete_nonexistent_object_id(client: WeaveClient):
    with pytest.raises(weave.trace_server.errors.NotFoundError):
        _obj_delete(client, "nonexistent_obj", None)


def test_delete_mixed_valid_invalid_digests(client: WeaveClient):
    v0 = weave.publish({"i": 1}, name="obj_1")
    v1 = weave.publish({"i": 2}, name="obj_1")

    invalid_digests = [v0.digest, "invalid-digest", v1.digest]
    with pytest.raises(
        weave.trace_server.errors.NotFoundError,
        match="Delete request contains 3 digests, but found 2 objects to delete. Diff digests: {'invalid-digest'}",
    ):
        _obj_delete(client, "obj_1", invalid_digests)


def test_delete_duplicate_digests(client: WeaveClient):
    v0 = weave.publish({"i": 1}, name="obj_1")

    num_deleted = _obj_delete(client, "obj_1", [v0.digest, v0.digest])
    assert num_deleted == 1


def test_delete_with_digest_aliases(client: WeaveClient):
    v0 = weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")

    num_deleted = _obj_delete(client, "obj_1", ["latest"])
    assert num_deleted == 1

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 1
    assert objs[0].digest == v0.digest
    assert objs[0].val == {"i": 1}

    num_deleted = _obj_delete(client, "obj_1", ["v0"])
    assert num_deleted == 1

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 0


def test_delete_and_recreate_object(client: WeaveClient):
    # Create and delete initial object
    v0 = weave.publish({"i": 1}, name="obj_1")
    _obj_delete(client, "obj_1", [v0.digest])

    # Create new object with same ID
    v1 = weave.publish({"i": 2}, name="obj_1")

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 1
    assert objs[0].digest == v1.digest
    assert objs[0].val == {"i": 2}


def test_read_deleted_object(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    obj1_v2 = weave.publish({"i": 3}, name="obj_1")

    _obj_delete(client, "obj_1", [obj1_v2.digest])

    with pytest.raises(weave.trace_server.errors.ObjectDeletedError) as e:
        client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id="obj_1",
                digest=obj1_v2.digest,
            )
        )
    assert e.value.deleted_at is not None

    ref_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            project_id=client._project_id(),
            object_ids=["obj_1"],
            refs=[obj1_v2.uri()],
        )
    )
    assert len(ref_res.vals) == 1
    assert ref_res.vals[0] is None


def test_op_versions(client: WeaveClient):
    @weave.op
    def my_op(x: int) -> int:
        return x + 1

    my_op(1)
    my_op(2)

    @weave.op()
    def my_op(x: int, y: int) -> int:
        return x + y

    my_op(1, 2)

    objs = _objs_query(client, "my_op")
    assert len(objs) == 2

    _obj_delete(client, "my_op", [objs[0].digest])

    objs2 = _objs_query(client, "my_op")
    assert len(objs2) == 1
    assert objs2[0].version_index == 1

    _obj_delete(client, "my_op", ["latest"])

    objs3 = _objs_query(client, "my_op")
    assert len(objs3) == 0


def test_read_deleted_op(client: WeaveClient):
    @weave.op
    def my_op(x: int) -> int:
        return x + 1

    op_ref = weave.publish(my_op, name="my_op")

    _obj_delete(client, "my_op", [op_ref.digest])

    with pytest.raises(weave.trace_server.errors.ObjectDeletedError) as e:
        client.server.obj_read(
            tsi.ObjReadReq(
                project_id=client._project_id(),
                object_id="my_op",
                digest=op_ref.digest,
            )
        )
    assert e.value.deleted_at is not None

    ref_res = client.server.refs_read_batch(
        tsi.RefsReadBatchReq(
            project_id=client._project_id(),
            object_ids=["my_op"],
            refs=[op_ref.uri()],
        )
    )
    assert len(ref_res.vals) == 1
    assert ref_res.vals[0] is None
