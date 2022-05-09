import os

from . import weave_internal
from . import weave_types as types
from . import weavejs_fixes

from . import ops
from . import graph


def test_remove_opcall_versions():
    n = weave_internal.make_const_node(types.Int(), 3) + 9
    assert ":" in n.from_op.name
    fixed_n = weavejs_fixes.remove_opcall_versions_node(n)
    assert fixed_n.from_op.name == "number-add"


def test_convert_specific_op_to_generic_op_node():
    node = ops.local_path(os.path.join("testdata", "cereal.csv")).readcsv()[0]["type"]
    node = weavejs_fixes.fixup_node(node)
    assert node.from_op.name == "pick"
    assert "self" not in node.from_op.inputs
    assert "obj" in node.from_op.inputs
    dict_node = node.from_op.inputs["obj"]
    assert dict_node.from_op.name == "index"
    assert "self" not in dict_node.from_op.inputs
    assert "arr" in dict_node.from_op.inputs


def test_convert_specific_op_to_generic_op_data():
    node = ops.local_path(os.path.join("testdata", "cereal.csv")).readcsv()[0]["type"]
    node = weavejs_fixes.fixup_data(node.to_json())
    assert node["fromOp"]["name"] == "pick"
    assert "self" not in node["fromOp"]["inputs"]
    assert "obj" in node["fromOp"]["inputs"]
    dict_node = node["fromOp"]["inputs"]["obj"]
    assert dict_node["fromOp"]["name"] == "index"
    assert "self" not in dict_node["fromOp"]["inputs"]
    assert "arr" in dict_node["fromOp"]["inputs"]
