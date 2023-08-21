# This file should include tests for all the fixups we do to match
# the frontend js code.
# The related sites should be tagged with "# NOTE: js_compat" in the
#     Weave python code.
# TODO: Fix all the non-standard behaviors in the weave js code so we
#     can get rid of this file.
# Note: This file is not yet complete, there are existing fixups in the
#     weave Python code that I haven't documented here.

from .. import weave_types as types
from .. import weavejs_fixes
from ..ops_domain import wb_domain_types
from .. import gql_with_keys


def test_const_serialization():
    f_type = types.FileType(types.Const(types.String(), "png"))
    f_type_dict = f_type.to_dict()
    assert f_type_dict == {"extension": "png", "type": "FileBase"}
    f_type2 = types.TypeRegistry.type_from_dict(f_type_dict)
    assert isinstance(f_type2, types.FileType)
    assert isinstance(f_type2.extension, types.Const)
    assert f_type2.extension.val == "png"


def test_gql_haskeys_stripping():
    instance = wb_domain_types.Run({"a": types.String()})
    type = types.TypeRegistry.type_of(instance)
    assert isinstance(type, gql_with_keys.PartialObjectType)
    serialized = type.to_dict()
    assert weavejs_fixes.remove_gql_haskeys_from_types(serialized) == "run"
