import os

import pytest

from weave.legacy.weave import (
    api,
    context_state,
    mappers_python,
    ops,
    weave_internal,
    weavejs_fixes,
)
from weave.legacy.weave import weave_types as types


@pytest.mark.skip(
    "calling custom ops with graph engine is broken right now. Not needed for weaveflow"
)
def test_clean_opcall_str():
    _loading_builtins_token = context_state.set_loading_built_ins(False)

    try:

        @api.op(input_type={"x": types.Number()}, output_type=types.Number())
        def test_inc(x):
            return x + 1

    finally:
        context_state.clear_loading_built_ins(_loading_builtins_token)

    n = test_inc(5)
    assert "local-artifact://" in n.from_op.name
    fixed_n = weavejs_fixes.remove_opcall_versions_node(n)
    assert fixed_n.from_op.name == "op-test_inc"


def test_convert_specific_op_to_generic_op_node():
    node = ops.local_path(os.path.join("testdata", "cereal.csv")).readcsv()[0]["type"]
    node = weavejs_fixes.fixup_node(node)
    assert node.from_op.name == "pick"
    assert "self" not in node.from_op.inputs
    # Convert inputs to list to ensure we didn't screw up order
    assert list(node.from_op.inputs.keys())[0] == "obj"
    assert "obj" in node.from_op.inputs
    dict_node = node.from_op.inputs["obj"]
    assert dict_node.from_op.name == "index"
    assert "self" not in dict_node.from_op.inputs
    assert list(dict_node.from_op.inputs.keys())[0] == "arr"


def test_convert_specific_op_to_generic_op_data():
    node = ops.local_path(os.path.join("testdata", "cereal.csv")).readcsv()[0]["type"]
    node = weavejs_fixes.fixup_data(node.to_json())
    assert node["fromOp"]["name"] == "pick"
    assert "self" not in node["fromOp"]["inputs"]
    assert list(node["fromOp"]["inputs"].keys())[0] == "obj"
    dict_node = node["fromOp"]["inputs"]["obj"]
    assert dict_node["fromOp"]["name"] == "index"
    assert "self" not in dict_node["fromOp"]["inputs"]
    assert list(dict_node["fromOp"]["inputs"].keys())[0] == "arr"


def test_strip_union_encoding_from_weavejs_response(weave_test_client):
    obj = [1, "a"]
    obj_type = types.TypeRegistry.type_of(obj)
    m = mappers_python.map_to_python(obj_type, None)
    serialized = m.apply(obj)

    assert serialized != obj
    assert all("_union_id" in item for item in serialized)

    node = weave_internal.make_const_node(obj_type, obj)
    serialized2 = weave_test_client.execute([node])[0]

    assert serialized2 == obj
