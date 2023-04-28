import typing

from weave import artifact_local, ref_base
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
from .decorators import weave_class, op, type
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
    if isinstance(node_or_obj, _graph.ConstNode):
        node_or_obj = node_or_obj.val
    ref = _storage.save(node_or_obj, name=name)
    return _ops.get(str(ref))


def publish(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.ConstNode):
        node_or_obj = node_or_obj.val
    node_or_obj = _recursively_publish_local_references(node_or_obj)
    ref = _storage.publish(node_or_obj, name=name)
    return _ops.get(str(ref))


def _recursively_publish_local_references(obj: typing.Any):
    if not isinstance(obj, _graph.Node):
        return obj

    res = _graph.map_nodes_full([obj], _recursively_publish_local_references_in_nodes)
    return res[0]


def _recursively_publish_local_references_in_nodes(node: _graph.Node) -> _graph.Node:
    if not (isinstance(node, _graph.OutputNode) and node.from_op.name == "get"):
        return node

    uri_node = node.from_op.inputs["uri"]
    if not isinstance(uri_node, _graph.ConstNode):
        return node

    uri = uri_node.val
    if not isinstance(uri, str):
        return node

    new_ref = ref_base.Ref.from_str(uri)
    if not isinstance(new_ref, artifact_local.LocalArtifactRef):
        return node

    # This use/publish pattern could be more efficient once we get Danny's new artifact API.
    value = use(node)
    new_node = publish(value)

    return new_node


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
