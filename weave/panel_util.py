import typing
from . import panel
from . import graph
from . import types as weave_types


def make_node(v: typing.Any) -> graph.Node:
    """Convert v to a node that is guaranteed to be json serializable"""
    if isinstance(v, graph.Node):
        return v

    node_type = weave_types.TypeRegistry.type_of(v)
    if weave_types.is_json_compatible(node_type):
        return graph.ConstNode(node_type, v)

    # Otherwise
    from . import storage

    ref = storage.save(v)
    from .ops_primitives.weave_api import get as op_get

    return op_get(str(ref))


def child_item(v):
    if isinstance(v, panel.Panel):
        return v
    else:
        return make_node(v)
