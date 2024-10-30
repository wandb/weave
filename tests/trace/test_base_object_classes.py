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

import pytest

import weave
from weave.trace import base_objects
from weave.trace.refs import ObjectRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def test_pythonic_creation(client: WeaveClient):
    # First, let's use the high-level pythonic creation API.
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=base_objects.TestOnlyNestedBaseModel(a=2),
        nested_obj=weave.publish(nested_obj).uri(),
    )
    ref = weave.publish(top_obj)

    top_obj_gotten = weave.ref(ref.uri()).get()

    assert isinstance(top_obj_gotten, base_objects.TestOnlyExample)
    assert top_obj_gotten.model_dump() == top_obj.model_dump()

    objs = client.server.obj_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["TestOnlyExample"]},
            },
        )
    )

    assert len(objs) == 1
    assert objs[0].val == top_obj.model_dump()

    objs = client.server.obj_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            },
        )
    )

    assert len(objs) == 1
    assert objs[0].val == nested_obj.model_dump()


def test_interface_creation(client):
    # Now we will do the equivant operation using low-level interface.
    nested_obj_id = "nested_obj"
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": nested_obj_id,
                    "val": nested_obj.model_dump(),
                }
            }
        )
    )
    nested_obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=nested_obj_id,
        digest=nested_obj_res.digest,
    )

    top_level_obj_id = "top_obj"
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=base_objects.TestOnlyNestedBaseModel(a=2),
        nested_obj=nested_obj_ref.uri(),
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": top_level_obj_id,
                    "val": top_obj.model_dump(),
                }
            }
        )
    )
    top_obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=top_level_obj_id,
        digest=top_obj_res.digest,
    )

    top_obj_gotten = weave.ref(top_obj_ref.uri()).get()

    assert top_obj_gotten.model_dump() == top_obj.model_dump()

    nested_obj_gotten = weave.ref(nested_obj_ref.uri()).get()

    assert nested_obj_gotten.model_dump() == nested_obj.model_dump()

    objs = client.server.obj_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["TestOnlyExample"]},
            },
        )
    )

    assert len(objs) == 1
    assert objs[0].val == top_obj.model_dump()

    objs = client.server.obj_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client._project_id(),
                "filter": {"base_object_classes": ["TestOnlyNestedBaseObject"]},
            },
        )
    )

    assert len(objs) == 1
    assert objs[0].val == nested_obj.model_dump()


def test_digest_equality(client):
    # Next, let's make sure that the digests are all equivalent

    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=base_objects.TestOnlyNestedBaseModel(a=2),
        nested_obj=weave.publish(nested_obj).uri(),
    )
    ref = weave.publish(top_obj)
    pythonic_digest = ref.digest

    # Now we will do the equivant operation using low-level interface.
    nested_obj_id = "nested_obj"
    nested_obj = base_objects.TestOnlyNestedBaseObject(b=3)
    nested_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": nested_obj_id,
                    "val": nested_obj.model_dump(),
                }
            }
        )
    )
    nested_obj_ref = ObjectRef(
        entity=client.entity,
        project=client.project,
        name=nested_obj_id,
        digest=nested_obj_res.digest,
    )

    top_level_obj_id = "top_obj"
    top_obj = base_objects.TestOnlyExample(
        primitive=1,
        nested_base_model=base_objects.TestOnlyNestedBaseModel(a=2),
        nested_obj=nested_obj_ref.uri(),
    )
    top_obj_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client._project_id(),
                    "object_id": top_level_obj_id,
                    "val": top_obj.model_dump(),
                }
            }
        )
    )

    interface_style_digest = top_obj_res.digest

    assert pythonic_digest == interface_style_digest


def test_schema_validation(client):
    # Test that we can't create an object with the wrong schema
    with pytest.raises():
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client._project_id(),
                        "object_id": "nested_obj",
                        "val": {"a": 2},
                    }
                }
            )
        )
