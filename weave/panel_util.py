from . import panel
from . import graph

make_node = graph.make_node


def child_item(v):
    if isinstance(v, panel.Panel):
        return v
    else:
        return graph.make_node(v)
