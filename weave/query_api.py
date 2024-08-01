import typing

from weave.legacy import graph as _graph
from weave.legacy.graph import Node

# If this is not imported, serialization of Weave Nodes is incorrect!
from weave.legacy import graph_mapper as _graph_mapper

from . import storage as _storage
from . import ref_base as _ref_base
from weave.legacy import wandb_api as _wandb_api

from . import weave_internal as _weave_internal

from weave.legacy import context as _context
from . import weave_init as _weave_init
from . import weave_client as _weave_client

from . import usage_analytics

def save(node_or_obj, name=None):
    from weave.legacy.ops_primitives.weave_api import get, save

    if isinstance(node_or_obj, _graph.Node):
        return save(node_or_obj, name=name)
    else:
        # If the user does not provide a branch, then we explicitly set it to
        # the default branch, "latest".
        branch = None
        name_contains_branch = name is not None and ":" in name
        if not name_contains_branch:
            branch = "latest"
        ref = _storage.save(node_or_obj, name=name, branch=branch)
        if name is None:
            # if the user didn't provide a name, the returned reference
            # will be to the specific version
            uri = ref.uri
        else:
            # otherwise the reference will be to whatever branch was provided
            # or the "latest" branch if only a name was provided.
            uri = ref.branch_uri
        return get(str(uri))


def get(ref_str):
    obj = _storage.get(ref_str)
    ref = typing.cast(_ref_base.Ref, _storage._get_ref(obj))
    return _weave_internal.make_const_node(ref.type, obj)


def use(nodes, client=None):
    usage_analytics.use_called()
    if client is None:
        client = _context.get_client()
    return _weave_internal.use(nodes, client)
