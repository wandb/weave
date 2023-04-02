import typing
from . import panel
from . import graph
from . import weave_types
from . import storage
from . import ops


def make_node(v: typing.Any) -> graph.Node:
    """Convert v to a node that is guaranteed to be json serializable"""
    if isinstance(v, graph.Node):
        return v

    node_type = weave_types.TypeRegistry.type_of(v)
    if weave_types.is_json_compatible(node_type):
        return graph.ConstNode(node_type, v)

    # Otherwise
    print("TO PYTHON", v)
    ref = storage.to_python(v)
    return ops.get(str(ref))


def child_item(v):
    if isinstance(v, panel.Panel):
        return v
    else:
        return make_node(v)
