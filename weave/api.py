import typing
from . import graph as _graph
from . import graph_mapper as _graph_mapper
from . import storage as _storage
from . import trace as _trace
from . import weave_internal as _weave_internal
from . import errors as _errors
from . import ops as _ops
from . import context as _context

# exposed as part of api
from . import weave_types as types
from . import types_numpy as _types_numpy
from . import errors
from .decorators import weave_class, op, mutation, type
from .op_args import OpVarArgs
from .op_def import OpDef
from . import usage_analytics
from .context import (
    use_fixed_server_port,
    use_frontend_devmode,
    # eager_execution,
    # lazy_execution,
)
from .server import capture_weave_server_logs
from .val_const import const
from .file_base import File, Dir
from .dispatch import RuntimeConstNode

from .weave_internal import define_fn

Node = _graph.Node


def save(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.Node):
        return _ops.save(node_or_obj, name=name)
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
        return _ops.get(str(uri))


def publish(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.Node):
        node_or_obj = use(node_or_obj)

    ref = _storage.publish(node_or_obj, name)
    return _weave_internal.make_const_node(ref.type, ref.obj)


def get(ref_str):
    obj = _storage.get(ref_str)
    ref = _storage._get_ref(obj)
    return _weave_internal.make_const_node(ref.type, obj)


def use(nodes, client=None):
    usage_analytics.use_called()
    if client is None:
        client = _context.get_client()
    return _weave_internal.use(nodes, client)


def _get_ref(obj):
    if isinstance(obj, _storage.Ref):
        return obj
    ref = _storage.get_ref(obj)
    if ref is None:
        raise _errors.WeaveApiError("obj is not a weave object: %s" % obj)
    return ref


def versions(obj):
    if isinstance(obj, _graph.ConstNode):
        obj = obj.val
    elif isinstance(obj, _graph.OutputNode):
        obj = use(obj)
    ref = _get_ref(obj)
    return ref.versions()


def expr(obj):
    ref = _get_ref(obj)
    return _trace.get_obj_expr(ref)


def type_of(obj: typing.Any) -> types.Type:
    return types.TypeRegistry.type_of(obj)


def weave(obj: typing.Any) -> RuntimeConstNode:
    return _weave_internal.make_const_node(type_of(obj), obj)  # type: ignore


def from_pandas(df):
    return _ops.pandas_to_awl(df)
