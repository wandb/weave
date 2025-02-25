import time

import weave
from weave.trace.vals import WeaveDict, WeaveObject
from weave.trace.weave_client import ObjectVersionCollection, WeaveClient
from weave.trace_server import trace_server_interface as tsi


def generate_objects(weave_client: WeaveClient, obj_count: int, version_count: int):
    for i in range(obj_count):
        for j in range(version_count):
            weave.publish({"i": i, "j": j}, name=f"obj_{i}")


def test_list_objects_basic(client: WeaveClient):
    generate_objects(client, obj_count=5, version_count=3)

    collections = client.list_objects()
    assert len(collections) == 5

    for collection in collections:
        assert len(collection) == 3
        assert isinstance(collection, ObjectVersionCollection)
        assert collection.object_id.startswith("obj_")


def test_list_objects_iteration(client: WeaveClient):
    generate_objects(client, obj_count=2, version_count=2)

    collections = client.list_objects()

    for collection in collections:
        for obj in collection:
            assert isinstance(obj, (WeaveDict))
            assert "i" in obj
            assert "j" in obj


def test_list_objects_with_filter(client: WeaveClient):
    generate_objects(client, obj_count=5, version_count=2)

    filtered_collections = client.list_objects(
        filter=tsi.ObjectVersionFilter(object_ids=["obj_0", "obj_1"])
    )

    assert len(filtered_collections) == 2
    assert {c.object_id for c in filtered_collections} == {"obj_0", "obj_1"}


def test_list_objects_lazy_loading(client: WeaveClient):
    generate_objects(client, obj_count=3, version_count=3)

    collections = client.list_objects()

    # No objects should be loaded initially
    assert len(collections[0]._weave_objects) == 0

    # Objects should be loaded only when accessed
    first_obj = collections[0][0]
    assert isinstance(first_obj, (WeaveObject, WeaveDict))
    assert len(collections[0]._weave_objects) == 1

    second_obj = collections[0][1]
    assert isinstance(second_obj, (WeaveObject, WeaveDict))
    assert len(collections[0]._weave_objects) == 2


def test_list_objects_access_performance(client: WeaveClient):
    generate_objects(client, obj_count=2, version_count=2)

    collections = client.list_objects()

    start_time = time.time()
    _ = collections[0][0]
    first_access_time = time.time() - start_time

    start_time = time.time()
    _ = collections[0][1]
    second_access_time = time.time() - start_time

    assert first_access_time < 1.0
    assert second_access_time < 1.0
