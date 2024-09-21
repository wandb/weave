import typing

from weave.legacy.weave import weave_types
from weave.legacy.weave import storage, graph, panel


def make_node(v: typing.Any) -> graph.Node:
    """Business logic for how values passed to panels are converted to json."""
    from weave.legacy.weave import ops

    if isinstance(v, graph.Node):
        return v

    node_type = weave_types.TypeRegistry.type_of(v)
    if weave_types.is_json_compatible(node_type):
        return graph.ConstNode(node_type, v)

    # Otherwise
    ref = storage.save(v)
    return ops.get(str(ref))  # type: ignore


def child_item(v):
    if isinstance(v, panel.Panel):
        return v
    else:
        return make_node(v)
