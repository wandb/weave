import typing
from . import graph as _graph
from . import storage as _storage
from . import weave_internal as _weave_internal
from . import errors as _errors
from . import ops as _ops
from . import context as _context

# exposed as part of api
from . import weave_types as types
from . import errors
from .decorators import weave_class, op, mutation, type
from .op_args import OpVarArgs
from .op_def import OpDef
from . import usage_analytics
from .context import (
    use_fixed_server_port,
    use_frontend_devmode,
    capture_weave_server_logs,
    eager_execution,
    lazy_execution,
)

from .weave_internal import define_fn

Node = _graph.Node


def save(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.Node):
        from .ops_primitives.weave_api import save as op_save

        return op_save(node_or_obj, name=name)
    else:
        ref = _storage.save(node_or_obj, name=name)

        # TODO: This doesn't return op_get
        # But somehow we eventually get an op_get... how?
        from .ops_primitives.weave_api import get as op_get

        return op_get(str(ref))

        return _weave_internal.make_const_node(ref.type, ref.obj)


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
    # weave_client = client.Client(server.SubprocessServer())
    # weave_client = client.Client(server.HttpServer('http://127.0.0.1:9994'))
    single = True
    if not isinstance(nodes, _graph.Node) and (
        isinstance(nodes, list) or isinstance(nodes, tuple)
    ):
        single = False
    if single:
        nodes = (nodes,)

    # Do this to convert all Refs to get(str(ref))
    # But this is incorrect! If there are shared parent nodes among nodes, we will
    # disconnect them.
    # TODO: Fix
    actual_nodes = []
    for node in nodes:
        if not isinstance(node, _graph.Node):
            if _context.eager_mode():
                raise errors.WeaveApiError("use not allowed in eager mode.")
            else:
                raise errors.WeaveApiError("non-Node passed to use(): %s" % type(node))
        actual_nodes.append(node)

    result = client.execute(actual_nodes)

    if single:
        result = result[0]
    return result


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
    return _storage.get_obj_expr(ref)


def type_of(obj: typing.Any) -> types.Type:
    return types.TypeRegistry.type_of(obj)
