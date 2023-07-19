from ..ops_domain import wb_domain_types as wdt
from .. import weave_types as types


def test_with_keys_assignability():
    org_type = wdt.OrgType
    org_with_keys = org_type.with_keys({"orgName": types.String()})
    assert not org_with_keys().assign_type(org_type)
    assert org_type.assign_type(org_with_keys())
