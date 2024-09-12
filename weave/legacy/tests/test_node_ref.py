from weave.legacy.weave import api as weave
from weave.legacy.weave import graph

from ...legacy.weave import node_ref


def test_node_to_ref():
    l = [{"a": 5, "b": 6}, {"a": 7, "b": 9}]
    l_node = weave.save(l, "my-l")
    node = l_node[0]["a"]
    ref = node_ref.node_to_ref(node)
    assert ref.name == "my-l"
    assert ref.extra == ["0", "a"]

    node2 = node_ref.ref_to_node(ref)
    assert (
        str(node2) == 'get("local-artifact:///my-l:fc48d97f6600ff9162ca/obj")[0]["a"]'
    )
