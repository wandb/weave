from . import node_ref
from . import api as weave
from . import refs
from . import graph


def test_node_to_ref():
    l = [{"a": 5, "b": 6}, {"a": 7, "b": 9}]
    l_node = weave.save(l, "my-l")
    node = l_node[0]["a"]
    ref = node_ref.node_to_ref(node)
    assert ref.name == "my-l"
    assert ref.extra == ["0", "a"]

    node2 = node_ref.ref_to_node(ref)
    assert graph.nodes_equal(node2, node)
