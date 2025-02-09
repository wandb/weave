"""
This test file ensures the base_object_classes behavior is as expected. Specifically:
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

from typing import Literal, Optional

import pytest
from pydantic import ValidationError

import weave
from weave.trace import base_objects
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.tsi import trace_server_interface as tsi
from weave.tsi.builtin_object_classes.test_only_example import (
    TestOnlyNestedBaseModel,
)


def with_base_object_class_annotations(
    val: dict,
    class_name: str,
    base_object_name: Optional[Literal["Object", "BaseObject"]] = None,
):
    """
    When serializing pydantic objects, add additional fields to indicate the class information. This is
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


def test_pythonic_creation(client: WeaveClient):
    # First, let's use the high-level pythonic creation API.
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2),
        nested_base_object=weave.publish(nested_obj).uri(),
    )
    ref = weave.publish(top_obj)

    top_obj_gotten = weave.ref(ref.uri()).get()

    assert isinstance(top_obj_gotten, base_objects.TestOnlyExample)
    assert top_obj_gotten.model_dump() == top_obj.model_dump()

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
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
                top_obj.model_dump(), "TestOnlyExample", "BaseObject"
            ),
            "nested_base_model": with_base_object_class_annotations(
                top_obj.nested_base_model.model_dump(), "TestOnlyNestedBaseModel"
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
                "_class_name": "TestOnlyNestedBaseModel",
                "_bases": ["BaseModel"],
            },
            "nested_base_object": "weave:///shawn/test-project/object/TestOnlyNestedBaseObject:JyFvHfyaJ79uCKpdZ3DD3if4NYam8QgTkzUlXQXAILI",
            "_class_name": "TestOnlyExample",
            "_bases": ["BaseObject", "BaseModel"],
        }
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            },
        )
    )
    objs = objs_res.objs

    assert len(objs) == 1
    assert (
        objs[0].val
        == with_base_object_class_annotations(
            nested_obj.model_dump(), "TestOnlyNestedBaseObject", "BaseObject"
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


def test_interface_creation(client):
    # Now we will do the equivant operation using low-level interface.
    nested_obj_id = "TestOnlyNestedBaseObject"
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": nested_obj_id,
                    "val": nested_obj.model_dump(),
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
        nested_base_model=TestOnlyNestedBaseModel(a=2),
        nested_base_object=nested_obj_ref.uri(),
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": top_level_obj_id,
                    "val": top_obj.model_dump(),
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

    top_obj_gotten = weave.ref(top_obj_ref.uri()).get()

    assert top_obj_gotten.model_dump() == top_obj.model_dump()

    nested_obj_gotten = weave.ref(nested_obj_ref.uri()).get()

    assert nested_obj_gotten.model_dump() == nested_obj.model_dump()

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
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
                top_obj.model_dump(), "TestOnlyExample", "BaseObject"
            ),
            "nested_base_model": with_base_object_class_annotations(
                top_obj.nested_base_model.model_dump(), "TestOnlyNestedBaseModel"
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
                "_class_name": "TestOnlyNestedBaseModel",
                "_bases": ["BaseModel"],
            },
            "nested_base_object": "weave:///shawn/test-project/object/TestOnlyNestedBaseObject:JyFvHfyaJ79uCKpdZ3DD3if4NYam8QgTkzUlXQXAILI",
            "_class_name": "TestOnlyExample",
            "_bases": ["BaseObject", "BaseModel"],
        }
    )

    objs_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            },
        )
    )
    objs = objs_res.objs
    assert len(objs) == 1
    assert (
        objs[0].val
        == with_base_object_class_annotations(
            nested_obj.model_dump(), "TestOnlyNestedBaseObject", "BaseObject"
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


def test_digest_equality(client):
    # Next, let's make sure that the digests are all equivalent
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_ref = weave.publish(nested_obj)
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=TestOnlyNestedBaseModel(a=2),
        nested_base_object=nested_ref.uri(),
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
                    "project_id": client._project_id(),
                    "object_id": nested_obj_id,
                    "val": nested_obj.model_dump(),
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
        nested_base_model=TestOnlyNestedBaseModel(a=2),
        nested_base_object=nested_obj_ref.uri(),
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": top_level_obj_id,
                    "val": top_obj.model_dump(),
                    "builtin_object_class": "TestOnlyExample",
                }
            }
        )
    )

    top_level_interface_style_digest = top_obj_res.digest

    assert top_level_pythonic_digest == top_level_interface_style_digest


def test_schema_validation(client):
    # Test that we can't create an object with the wrong schema
    with pytest.raises(ValidationError):
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client._project_id(),
                        "object_id": "nested_obj",
                        # Incorrect schema, should raise!
                        "val": {"a": 2},
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
                    "project_id": client._project_id(),
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

    with pytest.raises(ValueError):
        # Mismatching base object class, should raise
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client._project_id(),
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
