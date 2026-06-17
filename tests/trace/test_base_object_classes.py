"""This test file ensures the base_object_classes behavior is as expected. Specifically:
1. We ensure that pythonic publishing and getting of objects:
    a. Results in the correct base_object_class filter in the query.
    b. Produces identical results.
2. We ensure that using the low-level interface:
    a. Results in the correct base_object_class filter in the query.
    b. Produces identical results.
3. We ensure that digests are equivalent between pythonic and interface style creation.
   This is important to ensure that UI-based generation of objects is consistent with
   programmatic generation.
4. We ensure that invalid schemas are properly rejected from the server.
"""

import time
from typing import Literal

import pytest
from pydantic import ValidationError

import weave
from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.trace import base_objects
from weave.trace.refs import ObjectRef
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import WeaveClient, map_to_refs
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    _invalid_field_message,
)
from weave.trace_server.errors import (
    InvalidFieldError,
    InvalidRequest,
    ObjectNameTypeCollision,
)
from weave.trace_server.interface.builtin_object_classes.test_only_example import (
    TestOnlyNestedBaseModel,
)


def with_base_object_class_annotations(
    val: dict,
    class_name: str,
    base_object_name: Literal["Object", "BaseObject"] | None = None,
):
    """When serializing pydantic objects, add additional fields to indicate the class information. This is
    a utlity to perform that mapping for the purposes of testing. We want to ensure that both the client
    and server agree on this structure, therefore I am adding this utility here.
    """
    bases = ["BaseModel"]
    if base_object_name is not None:
        bases.insert(0, base_object_name)
    return {
        **val,
        "_type": class_name,
        "_class_name": class_name,
        "_bases": bases,
    }


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_pythonic_creation(client: WeaveClient):
    # First, let's use the high-level pythonic creation API.
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2, aliased_property_alias=3),
        nested_base_object=weave.publish(nested_obj).uri,
    )
    ref = weave.publish(top_obj)

    top_obj_gotten = weave.ref(ref.uri).get()

    assert isinstance(top_obj_gotten, base_objects.TestOnlyExample)
    assert top_obj_gotten.model_dump(by_alias=True) == top_obj.model_dump(by_alias=True)

    # Test inherited object (leaf class) with pythonic creation
    inherited_obj = base_objects.TestOnlyInheritedBaseObject(
        b=10, c=20, additional_field="pythonic_test"
    )
    inherited_ref = weave.publish(inherited_obj)

    inherited_obj_gotten = weave.ref(inherited_ref.uri).get()

    assert isinstance(inherited_obj_gotten, base_objects.TestOnlyInheritedBaseObject)
    assert inherited_obj_gotten.model_dump(by_alias=True) == inherited_obj.model_dump(
        by_alias=True
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["TestOnlyExample"]},
            },
        )
    )
    objs = objs_res.objs

    assert len(objs) == 1
    assert (
        objs[0].val
        == {
            **with_base_object_class_annotations(
                top_obj.model_dump(by_alias=True), "TestOnlyExample", "BaseObject"
            ),
            "nested_base_model": with_base_object_class_annotations(
                top_obj.nested_base_model.model_dump(by_alias=True),
                "TestOnlyNestedBaseModel",
            ),
        }
        == {
            "_type": "TestOnlyExample",
            "name": None,
            "description": None,
            "primitive": 1,
            "nested_base_model": {
                "_type": "TestOnlyNestedBaseModel",
                "a": 2,
                "aliased_property_alias": 3,
                "_class_name": "TestOnlyNestedBaseModel",
                "_bases": ["BaseModel"],
            },
            "nested_base_object": "weave:///shawn/test-project/object/TestOnlyNestedBaseObject:zg8WgbAC5GBqld3Ka5XMY8YpAQkEVoJDXePQqXgrA4E",
            "_class_name": "TestOnlyExample",
            "_bases": ["BaseObject", "BaseModel"],
        }
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            },
        )
    )
    objs = objs_res.objs

    # Should get 2 objects: 1 base TestOnlyNestedBaseObject + 1 inherited TestOnlyInheritedBaseObject
    assert len(objs) == 2

    # Find the base and inherited objects
    base_obj = next(
        obj for obj in objs if obj.leaf_object_class == "TestOnlyNestedBaseObject"
    )
    inherited_obj_result = next(
        obj for obj in objs if obj.leaf_object_class == "TestOnlyInheritedBaseObject"
    )

    # Verify base object
    assert (
        base_obj.val
        == with_base_object_class_annotations(
            nested_obj.model_dump(by_alias=True),
            "TestOnlyNestedBaseObject",
            "BaseObject",
        )
        == {
            "_type": "TestOnlyNestedBaseObject",
            "name": None,
            "description": None,
            "b": 3,
            "_class_name": "TestOnlyNestedBaseObject",
            "_bases": ["BaseObject", "BaseModel"],
        }
    )

    # Verify inherited object - demonstrates leaf class extraction from payload
    assert inherited_obj_result.base_object_class == "TestOnlyNestedBaseObject"
    assert inherited_obj_result.leaf_object_class == "TestOnlyInheritedBaseObject"

    # For inherited objects, the _bases includes the full inheritance chain
    expected_inherited_val = {
        "_type": "TestOnlyInheritedBaseObject",
        "name": None,
        "description": None,
        "b": 10,
        "c": 20,
        "additional_field": "pythonic_test",
        "_class_name": "TestOnlyInheritedBaseObject",
        "_bases": [
            "TestOnlyNestedBaseObject",
            "BaseObject",
            "BaseModel",
        ],  # Full inheritance chain
    }
    assert inherited_obj_result.val == expected_inherited_val


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
@pytest.mark.flaky(reruns=3)
def test_interface_creation(client):
    # Now we will do the equivant operation using low-level interface.
    nested_obj_id = "TestOnlyNestedBaseObject"
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": nested_obj_id,
                    "val": nested_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )
    nested_obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=nested_obj_id,
        _digest=nested_obj_res.digest,
    )

    top_level_obj_id = "TestOnlyExample"
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2, aliased_property_alias=3),
        nested_base_object=nested_obj_ref.uri,
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": top_level_obj_id,
                    "val": top_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyExample",
                }
            }
        )
    )
    top_obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=top_level_obj_id,
        _digest=top_obj_res.digest,
    )

    # Allow ClickHouse eventual consistency to settle before reading
    time.sleep(0.2)
    top_obj_gotten = weave.ref(top_obj_ref.uri).get()

    assert top_obj_gotten.model_dump(by_alias=True) == top_obj.model_dump(by_alias=True)

    nested_obj_gotten = weave.ref(nested_obj_ref.uri).get()

    assert nested_obj_gotten.model_dump(by_alias=True) == nested_obj.model_dump(
        by_alias=True
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["TestOnlyExample"]},
            },
        )
    )

    objs = objs_res.objs
    assert len(objs) == 1
    assert (
        objs[0].val
        == {
            **with_base_object_class_annotations(
                top_obj.model_dump(by_alias=True), "TestOnlyExample", "BaseObject"
            ),
            "nested_base_model": with_base_object_class_annotations(
                top_obj.nested_base_model.model_dump(by_alias=True),
                "TestOnlyNestedBaseModel",
            ),
        }
        == {
            "_type": "TestOnlyExample",
            "name": None,
            "description": None,
            "primitive": 1,
            "nested_base_model": {
                "_type": "TestOnlyNestedBaseModel",
                "a": 2,
                "aliased_property_alias": 3,
                "_class_name": "TestOnlyNestedBaseModel",
                "_bases": ["BaseModel"],
            },
            "nested_base_object": "weave:///shawn/test-project/object/TestOnlyNestedBaseObject:zg8WgbAC5GBqld3Ka5XMY8YpAQkEVoJDXePQqXgrA4E",
            "_class_name": "TestOnlyExample",
            "_bases": ["BaseObject", "BaseModel"],
        }
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            },
        )
    )
    objs = objs_res.objs
    assert len(objs) == 1
    assert (
        objs[0].val
        == with_base_object_class_annotations(
            nested_obj.model_dump(by_alias=True),
            "TestOnlyNestedBaseObject",
            "BaseObject",
        )
        == {
            "_type": "TestOnlyNestedBaseObject",
            "name": None,
            "description": None,
            "b": 3,
            "_class_name": "TestOnlyNestedBaseObject",
            "_bases": ["BaseObject", "BaseModel"],
        }
    )


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_digest_equality(client):
    # Next, let's make sure that the digests are all equivalent
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_ref = weave.publish(nested_obj)
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2, aliased_property_alias=3),
        nested_base_object=nested_ref.uri,
    )
    ref = weave.publish(top_obj)
    nested_pythonic_digest = nested_ref.digest
    top_level_pythonic_digest = ref.digest

    # Now we will do the equivant operation using low-level interface.
    nested_obj_id = "TestOnlyNestedBaseObject"
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": nested_obj_id,
                    "val": nested_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )
    nested_obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=nested_obj_id,
        _digest=nested_obj_res.digest,
    )

    nested_interface_style_digest = nested_obj_ref.digest

    assert nested_pythonic_digest == nested_interface_style_digest

    top_level_obj_id = "TestOnlyExample"
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2, aliased_property_alias=3),
        nested_base_object=nested_obj_ref.uri,
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": top_level_obj_id,
                    "val": top_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyExample",
                }
            }
        )
    )

    top_level_interface_style_digest = top_obj_res.digest

    assert top_level_pythonic_digest == top_level_interface_style_digest


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_schema_validation(client):
    # Test that we can't create an object with the wrong schema
    with pytest.raises(ValidationError):
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "nested_obj",
                        # Incorrect schema, should raise!
                        "val": {"a": 2, "aliased_property_alias": 3},
                        "builtin_object_class": "TestOnlyNestedBaseObject",
                    }
                }
            )
        )

    # Correct schema, should work
    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "nested_obj",
                    "val": {
                        "b": 2,
                        "_class_name": "TestOnlyNestedBaseObject",
                        "_bases": ["BaseObject", "BaseModel"],
                    },
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    with pytest.raises(ValueError, match="object_class must match"):
        # Mismatching base object class, should raise
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "nested_obj",
                        "val": {
                            "b": 2,
                            "_class_name": "TestOnlyNestedBaseObject",
                            "_bases": ["BaseObject", "BaseModel"],
                        },
                        "builtin_object_class": "TestOnlyExample",
                    }
                }
            )
        )

    # Test hierarchy object with wrong builtin_object_class - should fail
    with pytest.raises(ValueError, match="object_class must match"):
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "inherited_obj_wrong_class",
                        "val": {
                            "b": 100,
                            "c": 200,
                            "additional_field": "test_value",
                            "_class_name": "TestOnlyInheritedBaseObject",
                            "_bases": ["BaseObject", "BaseModel"],
                        },
                        # Wrong builtin_object_class - using base class instead of inherited class
                        "builtin_object_class": "TestOnlyNestedBaseObject",
                    }
                }
            )
        )


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_leaf_object_class_from_builtin_object_class(client: WeaveClient):
    """Test that when builtin_object_class is set, leaf_object_class is correctly set on stored object."""
    # Create an object using builtin_object_class parameter
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=42)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "test_nested_obj",
                    "val": nested_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    # Read the object back and verify leaf_object_class is set correctly
    read_obj_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="test_nested_obj",
            digest=nested_obj_res.digest,
        )
    )

    assert read_obj_res.obj.base_object_class == "TestOnlyNestedBaseObject"
    assert read_obj_res.obj.leaf_object_class == "TestOnlyNestedBaseObject"

    # Create a more complex object
    top_obj = base_objects.TestOnlyExample(
        primitive=123,
        nested_base_model=TestOnlyNestedBaseModel(a=456, aliased_property_alias=789),
        nested_base_object=f"weave:///{client.entity}/{client.project}/object/test_nested_obj:{nested_obj_res.digest}",
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "test_top_obj",
                    "val": top_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyExample",
                }
            }
        )
    )

    # Read the object back and verify leaf_object_class is set correctly
    read_top_obj_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="test_top_obj",
            digest=top_obj_res.digest,
        )
    )

    assert read_top_obj_res.obj.base_object_class == "TestOnlyExample"
    assert read_top_obj_res.obj.leaf_object_class == "TestOnlyExample"


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_leaf_object_class_filtering_with_builtin_objects(client: WeaveClient):
    """Test that leaf_object_class filtering works correctly with builtin objects created via builtin_object_class."""
    # Create several objects with different builtin_object_classes
    nested_obj1 = base_objects.TestOnlyNestedBaseObject(b=100)
    nested_obj1_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "nested_obj_1",
                    "val": nested_obj1.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    nested_obj2 = base_objects.TestOnlyNestedBaseObject(b=200)
    nested_obj2_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "nested_obj_2",
                    "val": nested_obj2.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    # Create inherited object to test hierarchy
    inherited_obj = base_objects.TestOnlyInheritedBaseObject(
        b=300, c=400, additional_field="test_inherited"
    )
    inherited_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "inherited_obj",
                    "val": inherited_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyInheritedBaseObject",
                }
            }
        )
    )

    top_obj = base_objects.TestOnlyExample(
        primitive=300,
        nested_base_model=TestOnlyNestedBaseModel(a=400, aliased_property_alias=500),
        nested_base_object=f"weave:///{client.entity}/{client.project}/object/nested_obj_1:{nested_obj1_res.digest}",
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "top_obj",
                    "val": top_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyExample",
                }
            }
        )
    )

    # Test filtering by leaf_object_class for TestOnlyNestedBaseObject (base class only)
    nested_objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["TestOnlyNestedBaseObject"]},
            }
        )
    )

    assert len(nested_objs_res.objs) == 2  # Only the 2 base objects, not inherited
    assert all(
        obj.leaf_object_class == "TestOnlyNestedBaseObject"
        for obj in nested_objs_res.objs
    )
    assert all(
        obj.base_object_class == "TestOnlyNestedBaseObject"
        for obj in nested_objs_res.objs
    )

    nested_obj_ids = {obj.object_id for obj in nested_objs_res.objs}
    assert nested_obj_ids == {"nested_obj_1", "nested_obj_2"}

    # Test filtering by leaf_object_class for TestOnlyInheritedBaseObject (inherited class)
    inherited_objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["TestOnlyInheritedBaseObject"]},
            }
        )
    )

    assert len(inherited_objs_res.objs) == 1
    assert inherited_objs_res.objs[0].leaf_object_class == "TestOnlyInheritedBaseObject"
    assert (
        inherited_objs_res.objs[0].base_object_class == "TestOnlyNestedBaseObject"
    )  # Different from leaf!
    assert inherited_objs_res.objs[0].object_id == "inherited_obj"

    # Test filtering by base_object_class - should return both base and inherited objects
    base_class_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            }
        )
    )

    assert len(base_class_res.objs) == 3  # 2 base + 1 inherited
    leaf_classes = {obj.leaf_object_class for obj in base_class_res.objs}
    assert leaf_classes == {"TestOnlyNestedBaseObject", "TestOnlyInheritedBaseObject"}

    # Test filtering by leaf_object_class for TestOnlyExample
    top_objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["TestOnlyExample"]},
            }
        )
    )

    assert len(top_objs_res.objs) == 1
    assert top_objs_res.objs[0].leaf_object_class == "TestOnlyExample"
    assert top_objs_res.objs[0].base_object_class == "TestOnlyExample"
    assert top_objs_res.objs[0].object_id == "top_obj"

    # Test filtering by multiple leaf_object_classes including hierarchy
    all_test_objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "leaf_object_classes": [
                        "TestOnlyNestedBaseObject",
                        "TestOnlyInheritedBaseObject",
                        "TestOnlyExample",
                    ]
                },
            }
        )
    )

    assert len(all_test_objs_res.objs) == 4  # 2 base + 1 inherited + 1 example
    leaf_classes = {obj.leaf_object_class for obj in all_test_objs_res.objs}
    assert leaf_classes == {
        "TestOnlyNestedBaseObject",
        "TestOnlyInheritedBaseObject",
        "TestOnlyExample",
    }

    # Test filtering by non-existent leaf_object_class
    empty_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["NonExistentClass"]},
            }
        )
    )

    assert len(empty_res.objs) == 0


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_base_and_leaf_object_class_combined_filtering_builtin_objects(
    client: WeaveClient,
):
    """Test that base_object_class and leaf_object_class filtering work together for builtin objects."""
    # Create objects with builtin_object_class
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=123)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "combined_test_nested",
                    "val": nested_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    top_obj = base_objects.TestOnlyExample(
        primitive=456,
        nested_base_model=TestOnlyNestedBaseModel(a=789, aliased_property_alias=101112),
        nested_base_object=f"weave:///{client.entity}/{client.project}/object/combined_test_nested:{nested_obj_res.digest}",
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "combined_test_top",
                    "val": top_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyExample",
                }
            }
        )
    )

    # Test combined filtering: both base_object_class and leaf_object_class must match
    # For builtin objects, base_object_class == leaf_object_class
    combined_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "base_object_classes": ["TestOnlyExample"],
                    "leaf_object_classes": ["TestOnlyExample"],
                },
            }
        )
    )

    assert len(combined_res.objs) == 1
    assert combined_res.objs[0].base_object_class == "TestOnlyExample"
    assert combined_res.objs[0].leaf_object_class == "TestOnlyExample"
    assert combined_res.objs[0].object_id == "combined_test_top"

    # Test mismatched filtering: should return empty since base != leaf for these objects
    mismatched_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "base_object_classes": ["TestOnlyExample"],
                    "leaf_object_classes": ["TestOnlyNestedBaseObject"],
                },
            }
        )
    )

    assert len(mismatched_res.objs) == 0


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_inherited_builtin_object_class_hierarchy(client: WeaveClient):
    """Test that inheritance between builtin objects works correctly with base_object_class and leaf_object_class."""
    # Create base object
    base_obj = base_objects.TestOnlyNestedBaseObject(b=100)
    base_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "base_obj",
                    "val": base_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    # Create inherited object
    inherited_obj = base_objects.TestOnlyInheritedBaseObject(
        b=200, c=300, additional_field="test_value"
    )
    inherited_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "inherited_obj",
                    "val": inherited_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyInheritedBaseObject",
                }
            }
        )
    )

    # Read both objects back and verify class hierarchy
    base_read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="base_obj",
            digest=base_obj_res.digest,
        )
    )

    inherited_read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="inherited_obj",
            digest=inherited_obj_res.digest,
        )
    )

    # Verify base object: base_object_class == leaf_object_class
    assert base_read_res.obj.base_object_class == "TestOnlyNestedBaseObject"
    assert base_read_res.obj.leaf_object_class == "TestOnlyNestedBaseObject"

    # Verify inherited object: base_object_class != leaf_object_class
    assert inherited_read_res.obj.base_object_class == "TestOnlyNestedBaseObject"
    assert inherited_read_res.obj.leaf_object_class == "TestOnlyInheritedBaseObject"

    # Verify inherited object has additional fields
    assert "c" in inherited_read_res.obj.val
    assert "additional_field" in inherited_read_res.obj.val
    assert inherited_read_res.obj.val["c"] == 300
    assert inherited_read_res.obj.val["additional_field"] == "test_value"
    # And inherited field from base
    assert "b" in inherited_read_res.obj.val
    assert inherited_read_res.obj.val["b"] == 200

    # Test filtering by base_object_class - should return both objects
    base_class_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            }
        )
    )

    assert len(base_class_filter_res.objs) == 2
    base_obj_classes = {obj.base_object_class for obj in base_class_filter_res.objs}
    assert base_obj_classes == {"TestOnlyNestedBaseObject"}

    leaf_obj_classes = {obj.leaf_object_class for obj in base_class_filter_res.objs}
    assert leaf_obj_classes == {
        "TestOnlyNestedBaseObject",
        "TestOnlyInheritedBaseObject",
    }

    # Test filtering by leaf_object_class for base class - should return only base object
    base_leaf_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["TestOnlyNestedBaseObject"]},
            }
        )
    )

    assert len(base_leaf_filter_res.objs) == 1
    assert base_leaf_filter_res.objs[0].leaf_object_class == "TestOnlyNestedBaseObject"
    assert base_leaf_filter_res.objs[0].base_object_class == "TestOnlyNestedBaseObject"
    assert base_leaf_filter_res.objs[0].object_id == "base_obj"

    # Test filtering by leaf_object_class for inherited class - should return only inherited object
    inherited_leaf_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["TestOnlyInheritedBaseObject"]},
            }
        )
    )

    assert len(inherited_leaf_filter_res.objs) == 1
    assert (
        inherited_leaf_filter_res.objs[0].leaf_object_class
        == "TestOnlyInheritedBaseObject"
    )
    assert (
        inherited_leaf_filter_res.objs[0].base_object_class
        == "TestOnlyNestedBaseObject"
    )
    assert inherited_leaf_filter_res.objs[0].object_id == "inherited_obj"

    # Test combined filtering: base_object_class and leaf_object_class
    # Should return only the inherited object since it has the specific leaf class but shares the base class
    combined_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "base_object_classes": ["TestOnlyNestedBaseObject"],
                    "leaf_object_classes": ["TestOnlyInheritedBaseObject"],
                },
            }
        )
    )

    assert len(combined_filter_res.objs) == 1
    assert (
        combined_filter_res.objs[0].leaf_object_class == "TestOnlyInheritedBaseObject"
    )
    assert combined_filter_res.objs[0].base_object_class == "TestOnlyNestedBaseObject"
    assert combined_filter_res.objs[0].object_id == "inherited_obj"

    # Test filtering by multiple leaf classes
    multi_leaf_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "leaf_object_classes": [
                        "TestOnlyNestedBaseObject",
                        "TestOnlyInheritedBaseObject",
                    ]
                },
            }
        )
    )

    assert len(multi_leaf_filter_res.objs) == 2
    leaf_classes = {obj.leaf_object_class for obj in multi_leaf_filter_res.objs}
    assert leaf_classes == {
        "TestOnlyNestedBaseObject",
        "TestOnlyInheritedBaseObject",
    }


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_exclude_base_object_classes(client: WeaveClient):
    """Test that exclude_base_object_classes filter correctly excludes objects by their base classes."""
    # Create several objects with different base classes
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=100)
    nested_ref = weave.publish(nested_obj)

    top_obj = base_objects.TestOnlyExample(
        primitive=200,
        nested_base_model=TestOnlyNestedBaseModel(a=300, aliased_property_alias=400),
        nested_base_object=nested_ref.uri,
    )
    top_ref = weave.publish(top_obj)

    inherited_obj = base_objects.TestOnlyInheritedBaseObject(
        b=500, c=600, additional_field="test_exclude"
    )
    inherited_ref = weave.publish(inherited_obj)

    # Test excluding TestOnlyExample - should get nested and inherited objects
    exclude_example_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"exclude_base_object_classes": ["TestOnlyExample"]},
            }
        )
    )

    # Should exclude only TestOnlyExample, include TestOnlyNestedBaseObject and inherited
    base_classes = {obj.base_object_class for obj in exclude_example_res.objs}
    assert "TestOnlyExample" not in base_classes
    assert "TestOnlyNestedBaseObject" in base_classes

    # Test excluding TestOnlyNestedBaseObject - should get only TestOnlyExample
    exclude_nested_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"exclude_base_object_classes": ["TestOnlyNestedBaseObject"]},
            }
        )
    )

    base_classes_excluded = {obj.base_object_class for obj in exclude_nested_res.objs}
    assert "TestOnlyNestedBaseObject" not in base_classes_excluded
    assert "TestOnlyExample" in base_classes_excluded

    # Test excluding multiple base classes
    exclude_multiple_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "exclude_base_object_classes": [
                        "TestOnlyExample",
                        "TestOnlyNestedBaseObject",
                    ]
                },
            }
        )
    )

    # Should exclude both, so result should be empty or only non-test objects
    base_classes_multi = {obj.base_object_class for obj in exclude_multiple_res.objs}
    assert "TestOnlyExample" not in base_classes_multi
    assert "TestOnlyNestedBaseObject" not in base_classes_multi

    # Test excluding non-existent class - should return all objects
    exclude_nonexistent_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"exclude_base_object_classes": ["NonExistentClass"]},
            }
        )
    )

    # Should return all objects since we're not excluding anything that exists
    assert len(exclude_nonexistent_res.objs) >= 3


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_exclude_base_object_classes_with_include_filter(client: WeaveClient):
    """Test that exclude_base_object_classes works correctly when combined with base_object_classes."""
    # Create objects with different base classes
    nested_obj1 = base_objects.TestOnlyNestedBaseObject(b=111)
    nested_ref1 = weave.publish(nested_obj1)

    nested_obj2 = base_objects.TestOnlyNestedBaseObject(b=222)
    nested_ref2 = weave.publish(nested_obj2)

    top_obj = base_objects.TestOnlyExample(
        primitive=333,
        nested_base_model=TestOnlyNestedBaseModel(a=444, aliased_property_alias=555),
        nested_base_object=nested_ref1.uri,
    )
    top_ref = weave.publish(top_obj)

    inherited_obj = base_objects.TestOnlyInheritedBaseObject(
        b=666, c=777, additional_field="test_combined"
    )
    inherited_ref = weave.publish(inherited_obj)

    # Test combining include and exclude (should be treated as AND logic)
    # Include TestOnlyNestedBaseObject but exclude nothing -> should get TestOnlyNestedBaseObject objects
    combined_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "base_object_classes": ["TestOnlyNestedBaseObject"],
                    "exclude_base_object_classes": ["TestOnlyExample"],
                },
            }
        )
    )

    # Should get TestOnlyNestedBaseObject objects (base and inherited), not TestOnlyExample
    base_classes = {obj.base_object_class for obj in combined_res.objs}
    assert base_classes == {"TestOnlyNestedBaseObject"}
    assert len(combined_res.objs) >= 3  # nested_obj1, nested_obj2, inherited_obj


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_exclude_base_object_classes_with_inherited_objects(client: WeaveClient):
    """Test that exclude_base_object_classes correctly handles inherited objects."""
    # Create base and inherited objects
    base_obj = base_objects.TestOnlyNestedBaseObject(b=1000)
    base_ref = weave.publish(base_obj)

    inherited_obj = base_objects.TestOnlyInheritedBaseObject(
        b=2000, c=3000, additional_field="test_inheritance_exclude"
    )
    inherited_ref = weave.publish(inherited_obj)

    # Exclude the base class - should exclude both base and inherited objects
    exclude_base_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"exclude_base_object_classes": ["TestOnlyNestedBaseObject"]},
            }
        )
    )

    # Should not include objects with base_object_class == TestOnlyNestedBaseObject
    base_classes = {obj.base_object_class for obj in exclude_base_res.objs}
    assert "TestOnlyNestedBaseObject" not in base_classes

    # Verify the inherited object is also excluded (since its base class is TestOnlyNestedBaseObject)
    object_ids = {obj.object_id for obj in exclude_base_res.objs}
    # The inherited object should be excluded since it has base_object_class = TestOnlyNestedBaseObject
    assert all(
        obj.base_object_class != "TestOnlyNestedBaseObject"
        for obj in exclude_base_res.objs
    )


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_obj_create_rejects_name_type_collision(client: WeaveClient):
    """WB-30574: object_id is bound to one base_object_class per project.

    Creating a new object with an existing object_id but a different
    base_object_class must be rejected. Otherwise the apparent type of the
    object changes and prior versions become invisible on the type-filtered
    assets page.
    """
    shared_object_id = "shared_name"

    # First create succeeds with base_object_class=TestOnlyNestedBaseObject.
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=1)
    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": shared_object_id,
                    "val": nested_obj.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )

    # Second create with the same object_id but a different base_object_class
    # must fail loudly. The error message must reference the existing type so
    # the user understands why the create was rejected.
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2, aliased_property_alias=3),
        nested_base_object="weave:///fake/fake/object/fake:fake",
    )
    with pytest.raises(ObjectNameTypeCollision) as excinfo:
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": shared_object_id,
                        "val": top_obj.model_dump(by_alias=True),
                        "builtin_object_class": "TestOnlyExample",
                    }
                }
            )
        )
    assert excinfo.value.object_id == shared_object_id
    assert excinfo.value.kind == "object"
    assert excinfo.value.new_base_object_class == "TestOnlyExample"
    assert excinfo.value.existing_base_object_classes == ["TestOnlyNestedBaseObject"]
    assert "TestOnlyNestedBaseObject" in str(excinfo.value)

    # And the original type must still be the only one present for that name.
    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"object_ids": [shared_object_id]},
            }
        )
    )
    assert len(objs_res.objs) == 1
    assert objs_res.objs[0].base_object_class == "TestOnlyNestedBaseObject"

    # A new version with the SAME base_object_class is still allowed.
    nested_obj_v2 = base_objects.TestOnlyNestedBaseObject(b=2)
    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": shared_object_id,
                    "val": nested_obj_v2.model_dump(by_alias=True),
                    "builtin_object_class": "TestOnlyNestedBaseObject",
                }
            }
        )
    )


def _create_monitor(client: WeaveClient, name: str, query: dict | None):
    """Create a Monitor via the client's serialization so the stored `query` carries weave bookkeeping keys, exercising the server-side strip + validation."""
    monitor = weave.Monitor(name=name, scorers=[], query=query)
    val = to_json(map_to_refs(monitor), client.project_id, client)
    return client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": name,
                    "val": val,
                }
            }
        )
    )


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_monitor_create_rejects_unknown_query_field(client: WeaveClient):
    """A Monitor query on an unknown field is rejected with the complete allowed-field list."""
    bad_query = {
        "$expr": {"$eq": [{"$getField": "operation_name"}, {"$literal": "predict"}]}
    }
    with pytest.raises(InvalidFieldError) as exc_info:
        _create_monitor(client, "bad-monitor", bad_query)

    assert str(exc_info.value) == _invalid_field_message("operation_name")
    assert "_dump" not in str(exc_info.value)

    # A structurally invalid query (empty $and) is a bad request, not a field error.
    with pytest.raises(InvalidRequest):
        _create_monitor(client, "empty-and-monitor", {"$expr": {"$and": []}})

    # Neither rejected monitor was stored.
    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"object_ids": ["bad-monitor", "empty-and-monitor"]},
            }
        )
    )
    assert objs_res.objs == []


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_monitor_create_accepts_valid_query_fields(client: WeaveClient):
    """Static, dynamic, and absent monitor queries all create successfully."""
    valid_query = {
        "$expr": {
            "$and": [
                {"$eq": [{"$getField": "parent_id"}, {"$literal": None}]},
                {
                    "$eq": [
                        {"$getField": "summary.weave.status"},
                        {"$literal": "success"},
                    ]
                },
            ]
        }
    }
    dynamic_query = {
        "$expr": {"$eq": [{"$getField": "inputs.foo"}, {"$literal": "bar"}]}
    }

    _create_monitor(client, "valid-monitor", valid_query)
    _create_monitor(client, "dynamic-monitor", dynamic_query)
    _create_monitor(client, "no-query-monitor", None)

    # A Monitor-classed object whose `query` is not a recognizable query shape is
    # left untouched (we only validate queries we understand), never 500'd.
    monitor = weave.Monitor(name="opaque-monitor", scorers=[], query=None)
    opaque_val = to_json(map_to_refs(monitor), client.project_id, client)
    opaque_val["query"] = "not-a-query"
    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "opaque-monitor",
                    "val": opaque_val,
                }
            }
        )
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "object_ids": [
                        "valid-monitor",
                        "dynamic-monitor",
                        "no-query-monitor",
                        "opaque-monitor",
                    ]
                },
            }
        )
    )
    assert {obj.object_id for obj in objs_res.objs} == {
        "valid-monitor",
        "dynamic-monitor",
        "no-query-monitor",
        "opaque-monitor",
    }
