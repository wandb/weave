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
from .decorators import weave_class, op, mutation
from .op_args import OpVarArgs
from . import usage_analytics
from .context import (
    use_fixed_server_port,
    use_frontend_devmode,
    capture_weave_server_logs,
)


def save(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.Node):
        from .ops_primitives.storage import save as op_save

        return op_save(node_or_obj, name=name)
    else:
        ref = _storage.save(node_or_obj, name=name)
        return _weave_internal.make_const_node(ref.type, ref.obj)


def get(ref_str):
    obj = _storage.get(ref_str)
    return _weave_internal.make_const_node(types.TypeRegistry.type_of(obj), obj)


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
                raise errors.WeaveApiError("non-Node passed to use().")
        actual_nodes.append(_graph.Node.node_from_json(node.to_json()))

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


# TODO: this shouldn't be here, you should be able to call
#    .filter() etc on whatever table and pass in a lambda
#    (like we can do now for adding columns to panel_table)
def define_fn(parameters, body):
    varNodes = {k: _weave_internal.make_var_node(t, k) for k, t in parameters.items()}
    fnNode = body(**varNodes)
    return _graph.ConstNode(types.Function(parameters, fnNode.type), fnNode)


def type_of(obj: typing.Any) -> types.Type:
    return types.TypeRegistry.type_of(obj)
