from . import weave_internal
from . import weave_types as types
from . import weavejs_fixes


def test_remove_opcall_versions():
    n = weave_internal.make_const_node(types.Int(), 3) + 9
    assert ":" in n.from_op.name
    fixed_n = weavejs_fixes.remove_opcall_versions_node(n)
    assert fixed_n.from_op.name == "number-add"
