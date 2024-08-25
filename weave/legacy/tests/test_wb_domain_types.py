from weave.legacy.weave import api as weave
from weave.legacy.weave import storage
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.ops_domain import wb_domain_types as wdt


def test_with_keys_assignability():
    org_type = wdt.OrgType
    org_with_keys = org_type.with_keys({"name": types.String()})
    assert not org_with_keys.assign_type(org_type)
    assert org_type.assign_type(org_with_keys)
    assert org_with_keys.assign_type(org_with_keys)

    org_with_keys_2 = org_type.with_keys(
        {
            "name": types.String(),
            "id": types.String(),
        }
    )

    assert org_with_keys.assign_type(org_with_keys_2)


def test_with_keys_not_assignability():
    org_type = wdt.OrgType
    org_with_keys = org_type.with_keys({"name": types.String()})
    project_type = wdt.ProjectType
    project_with_keys = project_type.with_keys({"name": types.String()})

    assert not org_with_keys.assign_type(project_with_keys)
    assert not project_with_keys.assign_type(org_with_keys)


def test_type_of_run_with_keys():
    run = wdt.Run.from_keys({"a": "1"})
    assert types.TypeRegistry.type_of(run) == wdt.RunType.with_keys(
        {"a": types.String()}
    )


def test_serialize_deserialize_run_type():
    run_type = wdt.RunType.with_keys({"a": types.String()})
    assert run_type.__class__.from_dict(run_type.to_dict()) == run_type


def test_storage_on_type_with_keys():
    run = wdt.Run.from_keys({"a": "1"})
    obj_id = storage.save(run, "my-test-run")
    loaded = storage.get(obj_id)
    assert loaded == run


def test_type_of_run_node_with_keys():
    run = wdt.Run.from_keys({"a": "1"})
    node = weave.save(run)
    assert node.type == wdt.RunType.with_keys({"a": types.String()})
