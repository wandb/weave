from .. import weave_internal
from .. import weave_types as types
from .. import graph_editable
from .. import api as weave


def test_build_and_replace():
    #    2      3
    #     \      \
    # 1 -> (a) -> (b)
    #        \      \
    #   4 -> (c) -> (d)
    a = weave_internal.make_const_node(types.Int(), 1) + 2
    b = a + 3
    c = a * 4
    d = b + c

    assert weave.use(d) == 18

    edit_g = graph_editable.EditGraph((d,))

    assert len(edit_g.nodes) == 4
    assert len(edit_g.edges) == 4
    assert len(edit_g.output_edges) == 3
    assert len(edit_g.input_edges) == 4

    edit_g.replace(c, a / 4)

    x = edit_g.get_node(d)
    assert weave.use(x) == 6.75
