from .. import api as weave
from .. import storage
from ..ops_domain import wb_domain_types as wdt
from .. import weave_types as types


def test_with_keys_assignability():
    org_type = wdt.OrgType
    org_with_keys = org_type.with_keys({"orgName": types.String()})
    assert not org_with_keys().assign_type(org_type)
    assert org_type.assign_type(org_with_keys())


def test_type_of_run_with_keys():
    run = wdt.Run.from_gql({"a": "1"})
    assert types.TypeRegistry.type_of(run) == wdt.RunType.with_keys(
        {"a": types.String()}
    )


def test_serialize_deserialize_run_type():
    run_type_class: types.Type = wdt.RunType.with_keys({"a": types.String()})
    run_type = run_type_class()
    assert run_type_class.from_dict(run_type.to_dict()) == run_type


def test_storage_on_type_with_keys():
    run = wdt.Run.from_gql({"a": "1"})
    obj_id = storage.save(run, "my-test-run")
    loaded = storage.get(obj_id)
    assert loaded == run


def test_type_of_run_node_with_keys():
    run = wdt.Run.from_gql({"a": "1"})
    node = weave.save(run)
    assert node.type == wdt.RunType.with_keys({"a": types.String()})()
