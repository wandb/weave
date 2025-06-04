import base64

import weave
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


class SimpleModel(weave.Object):
    model_name: str
    version: str


class LLMStructuredCompletionModel(weave.Object):
    llm_model_id: str
    temperature: float = 0.7


class AdvancedLLMModel(LLMStructuredCompletionModel):
    max_tokens: int = 1000
    special_features: list[str] = []


class Provider(weave.Object):
    name: str
    api_key: str


def generate_objects(weave_client: WeaveClient, obj_count: int, version_count: int):
    for i in range(obj_count):
        for j in range(version_count):
            weave.publish({"i": i, "j": j}, name=f"obj_{i}")


def generate_typed_objects(weave_client: WeaveClient):
    """Generate objects with different leaf_object_classes for testing."""
    # Create SimpleModel objects
    simple_model_1 = SimpleModel(model_name="simple_model_1", version="1.0")
    simple_model_2 = SimpleModel(model_name="simple_model_2", version="2.0")
    weave.publish(simple_model_1, name="simple_model_1")
    weave.publish(simple_model_2, name="simple_model_2")

    # Create LLMStructuredCompletionModel objects
    llm_model_1 = LLMStructuredCompletionModel(llm_model_id="gpt-4", temperature=0.5)
    llm_model_2 = LLMStructuredCompletionModel(llm_model_id="claude-3", temperature=0.8)
    weave.publish(llm_model_1, name="llm_model_1")
    weave.publish(llm_model_2, name="llm_model_2")

    # Create AdvancedLLMModel objects (inherits from LLMStructuredCompletionModel)
    advanced_model = AdvancedLLMModel(
        llm_model_id="gpt-4-turbo",
        temperature=0.3,
        max_tokens=2000,
        special_features=["function_calling", "json_mode"],
    )
    weave.publish(advanced_model, name="advanced_model")

    # Create Provider objects
    provider = Provider(name="openai", api_key="sk-***")
    weave.publish(provider, name="provider_1")

    # Create some basic dict objects (no specific class)
    weave.publish({"type": "basic_dict", "value": 1}, name="basic_dict_1")
    weave.publish({"type": "basic_dict", "value": 2}, name="basic_dict_2")


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


def test_objs_query_deleted_interaction(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3
    assert all(obj.val["i"] in [1, 2, 3] for obj in res.objs)

    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id="obj_1",
            digests=[res.objs[0].digest],
        )
    )

    assert res.num_deleted == 1

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert all(obj.val["i"] in [2, 3] for obj in res.objs)

    # Delete the remaining objects
    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id="obj_1",
            digests=[res.objs[0].digest, res.objs[1].digest],
        )
    )
    assert res.num_deleted == 2

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 0


def test_objs_query_delete_and_recreate(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3

    original_created_at = res.objs[0].created_at

    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id="obj_1",
        )
    )
    assert res.num_deleted == 3

    weave.publish({"i": 1}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].val["i"] == 1
    assert res.objs[0].created_at > original_created_at

    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3

    for i in range(3):
        print("res.objs[i].val", res.objs[i].val)
        assert res.objs[i].val["i"] == i + 1


def test_objs_query_delete_and_add_new_versions(client: WeaveClient):
    weave.publish({"i": 1}, name="obj_1")
    weave.publish({"i": 2}, name="obj_1")
    weave.publish({"i": 3}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3

    res = client.server.obj_delete(
        tsi.ObjDeleteReq(
            project_id=client._project_id(),
            object_id="obj_1",
        )
    )

    weave.publish({"i": 4}, name="obj_1")
    weave.publish({"i": 5}, name="obj_1")
    weave.publish({"i": 6}, name="obj_1")

    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(latest_only=False),
        )
    )
    assert len(res.objs) == 3
    assert all(obj.val["i"] in [4, 5, 6] for obj in res.objs)


def test_objs_query_filter_leaf_object_class_basic(client: WeaveClient):
    """Test basic leaf_object_class filtering."""
    generate_typed_objects(client)

    # Test filtering by SimpleModel
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["SimpleModel"]),
        )
    )
    assert len(res.objs) == 2
    assert all(obj.leaf_object_class == "SimpleModel" for obj in res.objs)
    assert all("model_name" in obj.val for obj in res.objs)

    # Test filtering by LLMStructuredCompletionModel
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["LLMStructuredCompletionModel"]
            ),
        )
    )
    assert len(res.objs) == 2
    assert all(
        obj.leaf_object_class == "LLMStructuredCompletionModel" for obj in res.objs
    )
    assert all("llm_model_id" in obj.val for obj in res.objs)

    # Test filtering by AdvancedLLMModel (inherited class)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["AdvancedLLMModel"]),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].leaf_object_class == "AdvancedLLMModel"
    assert "max_tokens" in res.objs[0].val
    assert "special_features" in res.objs[0].val

    # Test filtering by Provider
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["Provider"]),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].leaf_object_class == "Provider"
    assert "api_key" in res.objs[0].val


def test_objs_query_filter_leaf_object_class_multiple(client: WeaveClient):
    """Test filtering by multiple leaf_object_classes."""
    generate_typed_objects(client)

    # Test filtering by multiple classes
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["SimpleModel", "Provider"]
            ),
        )
    )
    assert len(res.objs) == 3  # 2 SimpleModel + 1 Provider
    leaf_classes = {obj.leaf_object_class for obj in res.objs}
    assert leaf_classes == {"SimpleModel", "Provider"}

    # Test filtering by LLM-related classes
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["LLMStructuredCompletionModel", "AdvancedLLMModel"]
            ),
        )
    )
    assert len(res.objs) == 3  # 2 LLMStructuredCompletionModel + 1 AdvancedLLMModel
    leaf_classes = {obj.leaf_object_class for obj in res.objs}
    assert leaf_classes == {"LLMStructuredCompletionModel", "AdvancedLLMModel"}


def test_objs_query_filter_leaf_object_class_with_other_filters(client: WeaveClient):
    """Test leaf_object_class filtering combined with other filters."""
    generate_typed_objects(client)

    # Test with latest_only
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["SimpleModel"],
                latest_only=True,
            ),
        )
    )
    assert len(res.objs) == 2
    assert all(obj.is_latest for obj in res.objs)
    assert all(obj.leaf_object_class == "SimpleModel" for obj in res.objs)

    # Test with specific object_ids
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["LLMStructuredCompletionModel"],
                object_ids=["llm_model_1"],
            ),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].object_id == "llm_model_1"
    assert res.objs[0].leaf_object_class == "LLMStructuredCompletionModel"

    # Test with is_op filter (should return empty since we're creating objects, not ops)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["SimpleModel"],
                is_op=True,
            ),
        )
    )
    assert len(res.objs) == 0

    # Test with is_op=False (should return objects)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["SimpleModel"],
                is_op=False,
            ),
        )
    )
    assert len(res.objs) == 2
    assert all(
        not obj.is_latest or obj.is_latest for obj in res.objs
    )  # Objects can be latest or not


def test_objs_query_filter_leaf_object_class_nonexistent(client: WeaveClient):
    """Test filtering by non-existent leaf_object_class."""
    generate_typed_objects(client)

    # Test filtering by a class that doesn't exist
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["NonExistentClass"]),
        )
    )
    assert len(res.objs) == 0

    # Test case sensitivity
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["simplemodel"]
            ),  # lowercase
        )
    )
    assert len(res.objs) == 0


def test_objs_query_filter_leaf_object_class_inheritance_hierarchy(client: WeaveClient):
    """Test that leaf_object_class filtering respects inheritance hierarchy."""
    generate_typed_objects(client)

    # Get all objects to understand the hierarchy
    res = client.server.objs_query(tsi.ObjQueryReq(project_id=client._project_id()))

    # Find objects with different inheritance levels
    advanced_llm_objs = [
        obj for obj in res.objs if obj.leaf_object_class == "AdvancedLLMModel"
    ]
    llm_objs = [
        obj
        for obj in res.objs
        if obj.leaf_object_class == "LLMStructuredCompletionModel"
    ]

    assert len(advanced_llm_objs) == 1
    assert len(llm_objs) == 2

    # AdvancedLLMModel should have a different base_object_class than regular LLMStructuredCompletionModel
    # Both should be weave Objects, but AdvancedLLMModel inherits from LLMStructuredCompletionModel
    advanced_obj = advanced_llm_objs[0]
    regular_llm_obj = llm_objs[0]

    # Verify the inheritance hierarchy is preserved in the stored objects
    assert advanced_obj.leaf_object_class == "AdvancedLLMModel"
    assert regular_llm_obj.leaf_object_class == "LLMStructuredCompletionModel"

    # Advanced model should have additional fields from inheritance
    assert "max_tokens" in advanced_obj.val
    assert "special_features" in advanced_obj.val
    assert "llm_model_id" in advanced_obj.val  # Inherited field
    assert "temperature" in advanced_obj.val  # Inherited field

    # Regular LLM model should not have the advanced fields
    assert "max_tokens" not in regular_llm_obj.val
    assert "special_features" not in regular_llm_obj.val


def test_objs_query_filter_leaf_object_class_with_sorting_and_pagination(
    client: WeaveClient,
):
    """Test leaf_object_class filtering with sorting and pagination."""
    generate_typed_objects(client)

    # Test with sorting by created_at and pagination
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["SimpleModel"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
            limit=1,
            offset=0,
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].leaf_object_class == "SimpleModel"
    first_obj_id = res.objs[0].object_id

    # Get the second object
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["SimpleModel"]),
            sort_by=[tsi.SortBy(field="created_at", direction="asc")],
            limit=1,
            offset=1,
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].leaf_object_class == "SimpleModel"
    second_obj_id = res.objs[0].object_id

    # Objects should be different
    assert first_obj_id != second_obj_id

    # Test sorting by object_id
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=["LLMStructuredCompletionModel"]
            ),
            sort_by=[tsi.SortBy(field="object_id", direction="desc")],
        )
    )
    assert len(res.objs) == 2
    # Should be sorted in descending order
    assert res.objs[0].object_id > res.objs[1].object_id


def test_objs_query_filter_leaf_object_class_metadata_only(client: WeaveClient):
    """Test leaf_object_class filtering with metadata_only flag."""
    generate_typed_objects(client)

    # Test metadata_only=True
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["SimpleModel"]),
            metadata_only=True,
        )
    )
    assert len(res.objs) == 2
    assert all(obj.leaf_object_class == "SimpleModel" for obj in res.objs)
    # With metadata_only=True, val should be empty
    assert all(obj.val == {} for obj in res.objs)

    # Test metadata_only=False
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(leaf_object_classes=["SimpleModel"]),
            metadata_only=False,
        )
    )
    assert len(res.objs) == 2
    assert all(obj.leaf_object_class == "SimpleModel" for obj in res.objs)
    # With metadata_only=False, val should contain the actual data
    assert all(obj.val != {} for obj in res.objs)
    assert all("model_name" in obj.val for obj in res.objs)


def test_objs_query_filter_leaf_object_class_versioning(client: WeaveClient):
    """Test leaf_object_class filtering with object versioning."""
    # Create an object, then republish it with a different class (simulating evolution)
    simple_model = SimpleModel(model_name="evolving_model", version="1.0")
    weave.publish(simple_model, name="evolving_model")

    # Republish the same object name with a different class type
    llm_model = LLMStructuredCompletionModel(
        llm_model_id="evolving_model_v2", temperature=0.5
    )
    weave.publish(llm_model, name="evolving_model")

    # Get all versions of the object
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=["evolving_model"],
                latest_only=False,
            ),
        )
    )
    assert len(res.objs) == 2

    # Check that we have both leaf classes represented
    leaf_classes = {obj.leaf_object_class for obj in res.objs}
    assert leaf_classes == {"SimpleModel", "LLMStructuredCompletionModel"}

    # Test filtering by the old leaf class (should get the first version)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=["evolving_model"],
                leaf_object_classes=["SimpleModel"],
            ),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].leaf_object_class == "SimpleModel"
    assert not res.objs[0].is_latest

    # Test filtering by the new leaf class (should get the latest version)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                object_ids=["evolving_model"],
                leaf_object_classes=["LLMStructuredCompletionModel"],
            ),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].leaf_object_class == "LLMStructuredCompletionModel"
    assert res.objs[0].is_latest


def test_objs_query_filter_leaf_object_class_with_basic_objects(client: WeaveClient):
    """Test that basic dict objects (without specific weave.Object classes) are handled correctly."""
    # Generate our typed objects plus some basic objects
    generate_typed_objects(client)

    # Get all objects to see what we have
    all_res = client.server.objs_query(tsi.ObjQueryReq(project_id=client._project_id()))

    # Find objects that are basic dicts (should have no specific leaf_object_class or None)
    basic_dict_objs = [
        obj for obj in all_res.objs if obj.object_id.startswith("basic_dict_")
    ]
    assert len(basic_dict_objs) == 2

    # These should either have None or a generic class name
    for obj in basic_dict_objs:
        # The exact behavior may vary, but they shouldn't match our specific classes
        assert obj.leaf_object_class not in [
            "SimpleModel",
            "LLMStructuredCompletionModel",
            "AdvancedLLMModel",
            "Provider",
        ]

    # Filtering by specific leaf classes shouldn't return basic dict objects
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                leaf_object_classes=[
                    "SimpleModel",
                    "LLMStructuredCompletionModel",
                    "AdvancedLLMModel",
                    "Provider",
                ]
            ),
        )
    )

    # Should get 6 typed objects but not the 2 basic dict objects
    assert len(res.objs) == 6
    typed_object_ids = {obj.object_id for obj in res.objs}
    assert not any(obj_id.startswith("basic_dict_") for obj_id in typed_object_ids)


def test_objs_query_filter_base_object_class_basic(client: WeaveClient):
    """Test basic base_object_class filtering and verify base vs leaf class relationships."""
    generate_typed_objects(client)

    # Get all objects first to understand the hierarchy
    all_res = client.server.objs_query(tsi.ObjQueryReq(project_id=client._project_id()))

    # Print object info for debugging
    for obj in all_res.objs:
        if not obj.object_id.startswith("basic_dict_"):
            print(
                f"Object {obj.object_id}: base={obj.base_object_class}, leaf={obj.leaf_object_class}"
            )

    # Test filtering by base class that should include inherited objects
    # AdvancedLLMModel inherits from LLMStructuredCompletionModel, so filtering by
    # base_object_class="LLMStructuredCompletionModel" should return:
    # - 2 LLMStructuredCompletionModel objects (base=leaf="LLMStructuredCompletionModel")
    # - 1 AdvancedLLMModel object (base="LLMStructuredCompletionModel", leaf="AdvancedLLMModel")
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["LLMStructuredCompletionModel"]
            ),
        )
    )

    # Should get 3 objects total
    assert len(res.objs) == 3

    # All should have the same base_object_class
    assert all(
        obj.base_object_class == "LLMStructuredCompletionModel" for obj in res.objs
    )

    # But we should have two different leaf_object_classes
    leaf_classes = {obj.leaf_object_class for obj in res.objs}
    assert leaf_classes == {"LLMStructuredCompletionModel", "AdvancedLLMModel"}

    # Count each type
    llm_objs = [
        obj
        for obj in res.objs
        if obj.leaf_object_class == "LLMStructuredCompletionModel"
    ]
    advanced_objs = [
        obj for obj in res.objs if obj.leaf_object_class == "AdvancedLLMModel"
    ]

    assert len(llm_objs) == 2  # 2 base LLMStructuredCompletionModel objects
    assert len(advanced_objs) == 1  # 1 AdvancedLLMModel object

    # Verify the AdvancedLLMModel has additional fields from inheritance
    advanced_obj = advanced_objs[0]
    assert "max_tokens" in advanced_obj.val
    assert "special_features" in advanced_obj.val
    assert "llm_model_id" in advanced_obj.val  # Inherited from base class
    assert "temperature" in advanced_obj.val  # Inherited from base class

    # Test filtering by a base class where base == leaf
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(base_object_classes=["SimpleModel"]),
        )
    )

    assert len(res.objs) == 2
    assert all(obj.base_object_class == "SimpleModel" for obj in res.objs)
    assert all(
        obj.leaf_object_class == "SimpleModel" for obj in res.objs
    )  # base == leaf


def test_objs_query_filter_base_object_class_combined_with_leaf(client: WeaveClient):
    """Test combining base_object_class and leaf_object_class filters."""
    generate_typed_objects(client)

    # Test filtering by both base and leaf class - should be intersection
    # This should return only the base LLMStructuredCompletionModel objects,
    # not the AdvancedLLMModel objects (which have different leaf class)
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["LLMStructuredCompletionModel"],
                leaf_object_classes=["LLMStructuredCompletionModel"],
            ),
        )
    )

    assert len(res.objs) == 2
    assert all(
        obj.base_object_class == "LLMStructuredCompletionModel" for obj in res.objs
    )
    assert all(
        obj.leaf_object_class == "LLMStructuredCompletionModel" for obj in res.objs
    )

    # None should be AdvancedLLMModel
    assert all("max_tokens" not in obj.val for obj in res.objs)
    assert all("special_features" not in obj.val for obj in res.objs)

    # Test filtering by base class but different leaf class
    # This should return only the AdvancedLLMModel object
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["LLMStructuredCompletionModel"],
                leaf_object_classes=["AdvancedLLMModel"],
            ),
        )
    )

    assert len(res.objs) == 1
    assert res.objs[0].base_object_class == "LLMStructuredCompletionModel"
    assert res.objs[0].leaf_object_class == "AdvancedLLMModel"
    assert "max_tokens" in res.objs[0].val
    assert "special_features" in res.objs[0].val

    # Test filtering by multiple base classes
    res = client.server.objs_query(
        tsi.ObjQueryReq(
            project_id=client._project_id(),
            filter=tsi.ObjectVersionFilter(
                base_object_classes=["SimpleModel", "Provider"],
            ),
        )
    )

    assert len(res.objs) == 3  # 2 SimpleModel + 1 Provider
    base_classes = {obj.base_object_class for obj in res.objs}
    assert base_classes == {"SimpleModel", "Provider"}

    # For these objects, base should equal leaf (no inheritance)
    for obj in res.objs:
        assert obj.base_object_class == obj.leaf_object_class
