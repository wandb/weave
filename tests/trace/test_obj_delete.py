import pytest

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy


def _objs_query(client: WeaveClient, object_id: str) -> list[tsi.ObjSchema]:
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id]),
            sort_by=[SortBy(field="created_at", direction="asc")],
        )
    )
    return objs.objs


def _obj_delete(client: WeaveClient, object_id: str, digests: list[str]) -> int:
    return client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client.project_id,
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


def test_delete_error_and_edge_cases(client: WeaveClient):
    """Over-limit, nonexistent id, mixed valid/invalid digests, and duplicate digests."""
    # Over the MAX_OBJECTS_TO_DELETE limit raises before touching storage.
    max_objs = 100
    too_many = [f"test_{i}" for i in range(max_objs + 1)]
    with pytest.raises(
        ValueError, match=f"Please delete {max_objs} or fewer objects at a time"
    ):
        _obj_delete(client, "obj_limit", too_many)

    # Deleting a nonexistent object id.
    with pytest.raises(weave.trace_server.errors.NotFoundError):
        _obj_delete(client, "nonexistent_obj", None)

    # Mixed valid/invalid digests rejects the whole request.
    v0 = weave.publish({"i": 1}, name="obj_mixed")
    v1 = weave.publish({"i": 2}, name="obj_mixed")
    with pytest.raises(
        weave.trace_server.errors.NotFoundError,
        match="Delete request contains 3 digests, but found 2 objects to delete. Diff digests: {'invalid-digest'}",
    ):
        _obj_delete(client, "obj_mixed", [v0.digest, "invalid-digest", v1.digest])

    # Duplicate digests collapse to a single delete.
    dv0 = weave.publish({"i": 1}, name="obj_dup")
    assert _obj_delete(client, "obj_dup", [dv0.digest, dv0.digest]) == 1


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


def _latest_objs_query(client: WeaveClient, object_id: str) -> list[tsi.ObjSchema]:
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(object_ids=[object_id], latest_only=True),
        )
    )
    return objs.objs


@pytest.mark.parametrize("republish_val", [{"i": 1}, {"i": 99}])
def test_republish_after_deleting_all_versions(
    client: WeaveClient, republish_val: dict[str, int]
):
    # Repro for #6298: publish, delete every version, re-publish, then the
    # re-published object must be visible (including via latest_only, which
    # backs the Datasets tab). republish_val == {"i": 1} re-publishes the
    # identical digest that was just tombstoned (the original report).
    v0 = weave.publish({"i": 1}, name="obj_1")
    v1 = weave.publish({"i": 2}, name="obj_1")
    assert _obj_delete(client, "obj_1", None) == 2
    assert _objs_query(client, "obj_1") == []

    v2 = weave.publish(republish_val, name="obj_1")

    objs = _objs_query(client, "obj_1")
    assert len(objs) == 1
    assert objs[0].digest == v2.digest
    assert objs[0].val == republish_val
    assert objs[0].is_latest == 1

    latest = _latest_objs_query(client, "obj_1")
    assert len(latest) == 1
    assert latest[0].digest == v2.digest
    assert latest[0].val == republish_val


def test_read_deleted_object_and_op(client: WeaveClient):
    """Reading a deleted object or op raises ObjectDeletedError and refs resolve to None."""
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    obj1_v2 = weave.publish({"i": 3}, name="obj_1")
    _obj_delete(client, "obj_1", [obj1_v2.digest])

    @weave.op
    def my_op(x: int) -> int:
        return x + 1

    op_ref = weave.publish(my_op, name="my_op")
    _obj_delete(client, "my_op", [op_ref.digest])

    for object_id, published in (("obj_1", obj1_v2), ("my_op", op_ref)):
        with pytest.raises(weave.trace_server.errors.ObjectDeletedError) as e:
            client.server.obj_read(
                tsi.ObjReadReq(
                    project_id=client.project_id,
                    object_id=object_id,
                    digest=published.digest,
                )
            )
        assert e.value.deleted_at is not None

        ref_res = client.server.refs_read_batch(
            tsi.RefsReadBatchReq(refs=[published.uri])
        )
        assert len(ref_res.vals) == 1
        assert ref_res.vals[0] is None


def test_op_versions(client: WeaveClient):
    @weave.op
    def my_op(x: int) -> int:
        return x + 1

    my_op(1)
    my_op(2)

    @weave.op
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


def test_delete_all_object_versions_api(client: WeaveClient):
    """Test the public API for deleting all versions of an object."""
    v0 = weave.publish({"i": 1}, name="obj_test_all")
    v1 = weave.publish({"i": 2}, name="obj_test_all")
    v2 = weave.publish({"i": 3}, name="obj_test_all")

    objs = _objs_query(client, "obj_test_all")
    assert len(objs) == 3

    # Delete all versions using the new public API
    num_deleted = client.delete_all_object_versions("obj_test_all")
    assert num_deleted == 3

    objs = _objs_query(client, "obj_test_all")
    assert len(objs) == 0

    # Try to delete again when no versions exist
    with pytest.raises(weave.trace_server.errors.NotFoundError):
        client.delete_all_object_versions("obj_test_all")


def test_delete_all_op_versions_api(client: WeaveClient):
    """Test the public API for deleting all versions of an op."""

    @weave.op
    def test_op(x: int) -> int:
        return x + 1

    test_op(1)
    test_op(2)

    @weave.op
    def test_op(x: int, y: int) -> int:
        return x + y

    test_op(1, 2)

    objs = _objs_query(client, "test_op")
    assert len(objs) == 2

    # Delete all versions using the new public API
    num_deleted = client.delete_all_op_versions("test_op")
    assert num_deleted == 2

    objs = _objs_query(client, "test_op")
    assert len(objs) == 0

    # Try to delete again when no versions exist
    with pytest.raises(weave.trace_server.errors.NotFoundError):
        client.delete_all_op_versions("test_op")


def test_delete_object_versions_api(client: WeaveClient):
    """Test the public API for deleting multiple specific versions of an object."""
    v0 = weave.publish({"i": 1}, name="obj_multi_delete")
    v1 = weave.publish({"i": 2}, name="obj_multi_delete")
    v2 = weave.publish({"i": 3}, name="obj_multi_delete")
    v3 = weave.publish({"i": 4}, name="obj_multi_delete")

    objs = _objs_query(client, "obj_multi_delete")
    assert len(objs) == 4

    # Delete multiple specific versions
    num_deleted = client.delete_object_versions(
        "obj_multi_delete", [v0.digest, v2.digest]
    )
    assert num_deleted == 2

    objs = _objs_query(client, "obj_multi_delete")
    assert len(objs) == 2
    assert objs[0].digest == v1.digest
    assert objs[1].digest == v3.digest

    # Delete using aliases
    num_deleted = client.delete_object_versions("obj_multi_delete", ["latest"])
    assert num_deleted == 1

    objs = _objs_query(client, "obj_multi_delete")
    assert len(objs) == 1
    assert objs[0].digest == v1.digest

    # Delete the last remaining version
    num_deleted = client.delete_object_versions("obj_multi_delete", [v1.digest])
    assert num_deleted == 1

    objs = _objs_query(client, "obj_multi_delete")
    assert len(objs) == 0


def _datasets_query(client: WeaveClient, latest_only: bool) -> list[tsi.ObjSchema]:
    objs = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client.project_id,
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["Dataset"], latest_only=latest_only
            ),
        )
    )
    return objs.objs


def test_republish_dataset_after_deleting_all_versions(client: WeaveClient):
    # Repro for #6298: the Datasets tab queries by base_object_class +
    # latest_only. After deleting every version and re-publishing the
    # identical first version (same digest as the tombstoned row), the
    # dataset must reappear in both the full and latest_only listings.
    r0 = weave.publish(weave.Dataset(name="my_ds", rows=[{"a": 1}, {"a": 2}]))
    weave.publish(weave.Dataset(name="my_ds", rows=[{"a": 3}]))
    assert len(_datasets_query(client, latest_only=False)) == 2

    _obj_delete(client, "my_ds", None)
    assert _datasets_query(client, latest_only=False) == []

    r2 = weave.publish(weave.Dataset(name="my_ds", rows=[{"a": 1}, {"a": 2}]))
    assert r2.digest == r0.digest

    latest = _datasets_query(client, latest_only=True)
    assert len(latest) == 1
    assert latest[0].object_id == "my_ds"
    assert latest[0].digest == r2.digest
    assert latest[0].is_latest == 1

    all_versions = _datasets_query(client, latest_only=False)
    assert len(all_versions) == 1
    assert all_versions[0].digest == r2.digest
