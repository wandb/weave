# This file should include tests for all the fixups we do to match
# the frontend js code.
# The related sites should be tagged with "# NOTE: js_compat" in the
#     Weave python code.
# TODO: Fix all the non-standard behaviors in the weave js code so we
#     can get rid of this file.
# Note: This file is not yet complete, there are existing fixups in the
#     weave Python code that I haven't documented here.

from .. import weave_types as types


def test_const_serialization():
    f_type = types.FileType(types.Const(types.String(), "png"))
    f_type_dict = f_type.to_dict()
    assert f_type_dict == {
        "extension": "png",
        "_property_types": {
            "extension": {"type": "const", "val": "png", "valType": "string"},
            "wb_object_type": {"type": "const", "val": "png", "valType": "string"},
        },
        "type": "file",
    }
    f_type2 = types.TypeRegistry.type_from_dict(f_type_dict)
    assert isinstance(f_type2, types.FileType)
    assert isinstance(f_type2.extension, types.Const)
    assert f_type2.extension.val == "png"
