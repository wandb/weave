import base64

import weave
from weave.trace.weave_client import ObjectVersionCollection, WeaveClient
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

    correct_id = base64.b64encode(
        bytes(client.server._next_trace_server._user_id, "utf-8")
    ).decode("utf-8")

    res = client._objects()
    assert len(res) == 3
    assert all(obj.wb_user_id == correct_id for obj in res)


def test_list_objects(client: WeaveClient):
    # Create test objects with multiple versions
    generate_objects(client, 5, 3)  # 5 objects with 3 versions each

    # Test basic functionality
    collections = client.list_objects()
    assert len(collections) == 5

    # Verify each collection has the correct number of versions
    for collection in collections:
        assert len(collection) == 3
        assert isinstance(collection, ObjectVersionCollection)
        assert collection.object_id.startswith("obj_")

        # Verify versions are sorted by version_index
        for i in range(len(collection) - 1):
            # Access the raw versions for version_index comparison
            assert (
                collection._raw_versions[i].version_index
                < collection._raw_versions[i + 1].version_index
            )

        # Verify latest property works
        assert collection._raw_versions[-1].is_latest == 1

        # Verify that we get WeaveObject instances when iterating
        for obj in collection:
            from weave.trace.vals import WeaveDict, WeaveObject

            # The objects we publish are dictionaries, so they'll be wrapped in WeaveDict
            assert isinstance(obj, (WeaveObject, WeaveDict))
            # Verify the object contains the expected data
            assert "i" in obj
            assert "j" in obj

    # Test with filter
    filtered_collections = client.list_objects(
        filter=tsi.ObjectVersionFilter(object_ids=["obj_0", "obj_1"])
    )
    assert len(filtered_collections) == 2
    assert {c.object_id for c in filtered_collections} == {"obj_0", "obj_1"}

    # Test with pagination
    paginated_collections = client.list_objects(limit=2, offset=1)
    assert len(paginated_collections) == 2

    # Verify the pagination skipped the first collection
    all_object_ids = {c.object_id for c in collections}
    paginated_object_ids = {c.object_id for c in paginated_collections}
    assert len(all_object_ids - paginated_object_ids) >= 1

    # Test with latest_only filter
    latest_collections = client.list_objects(
        filter=tsi.ObjectVersionFilter(latest_only=True)
    )
    assert len(latest_collections) == 5
    for collection in latest_collections:
        assert len(collection) == 1
        assert collection._raw_versions[0].is_latest == 1

    # Test the string representation
    for collection in collections:
        repr_str = repr(collection)
        assert collection.object_id in repr_str
        assert "base_class" in repr_str
        # The base_object_class might be None in test environment
        base_class = collection.base_object_class or "Unknown"
        assert base_class in repr_str
        assert f"versions={len(collection)}" in repr_str

    # Test accessing the latest version as a WeaveObject
    for collection in collections:
        latest = collection.latest
        from weave.trace.vals import WeaveDict, WeaveObject

        # The objects we publish are dictionaries, so they'll be wrapped in WeaveDict
        assert isinstance(latest, (WeaveObject, WeaveDict))
        # Verify the object contains the expected data
        assert "i" in latest
        assert "j" in latest


def test_list_objects_lazy_loading(client: WeaveClient):
    """Test that ObjectVersionCollection implements lazy loading correctly."""
    import time

    # Create test objects with multiple versions
    generate_objects(client, 5, 3)  # 5 objects with 3 versions each

    # Get collections
    collections = client.list_objects()
    assert len(collections) == 5

    # Time how long it takes to get the first item
    start_time = time.time()
    first_obj = collections[0][0]  # Get first object from first collection
    first_access_time = time.time() - start_time

    # Verify we got a valid object
    from weave.trace.vals import WeaveDict, WeaveObject

    assert isinstance(first_obj, (WeaveObject, WeaveDict))

    # Verify that only one object was loaded
    assert len(collections[0]._weave_objects) == 1

    # Time how long it takes to get the second item
    start_time = time.time()
    second_obj = collections[0][1]  # Get second object from first collection
    second_access_time = time.time() - start_time

    # Verify we got a valid object
    assert isinstance(second_obj, (WeaveObject, WeaveDict))

    # Verify that only two objects were loaded
    assert len(collections[0]._weave_objects) == 2

    # Print timing information for debugging
    print(f"First object access time: {first_access_time:.3f}s")
    print(f"Second object access time: {second_access_time:.3f}s")

    # Access should be reasonably fast (under 1 second)
    assert first_access_time < 1.0, (
        f"First access took {first_access_time:.3f}s, which is too slow"
    )
    assert second_access_time < 1.0, (
        f"Second access took {second_access_time:.3f}s, which is too slow"
    )


def test_list_objects_pagination_warning(client: WeaveClient):
    """Test that a warning is raised when using pagination with list_objects."""
    import warnings

    # Create test objects
    generate_objects(client, 3, 2)  # 3 objects with 2 versions each

    # Test with limit
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered
        warnings.simplefilter("always")

        # Call with limit
        client.list_objects(limit=2)

        # Verify a warning was raised
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "incomplete version groups" in str(w[0].message)

    # Test with offset
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered
        warnings.simplefilter("always")

        # Call with offset
        client.list_objects(offset=1)

        # Verify a warning was raised
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "incomplete version groups" in str(w[0].message)

    # Test with both limit and offset
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered
        warnings.simplefilter("always")

        # Call with both limit and offset
        client.list_objects(limit=1, offset=1)

        # Verify a warning was raised (only one warning even with both parameters)
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "incomplete version groups" in str(w[0].message)

    # Verify no warning when not using pagination
    with warnings.catch_warnings(record=True) as w:
        # Cause all warnings to always be triggered
        warnings.simplefilter("always")

        # Call without pagination
        client.list_objects()

        # Verify no warning was raised
        assert len(w) == 0
