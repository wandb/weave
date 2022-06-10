from . import panel
from . import graph


def child_item(v):
    if isinstance(v, panel.Panel):
        return v
    else:
        return graph.make_node(v)
