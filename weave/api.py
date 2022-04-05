from . import graph as _graph
from . import storage as _storage
from . import weave_internal as _weave_internal
from . import errors as _errors

# exposed as part of api
from . import weave_types as types
from . import errors
from .decorators import weave_class, op, mutation
from .op_args import OpVarArgs
from . import context as _context
from . import usage_analytics
from .context import use_fixed_server_port, use_frontend_devmode


def save(node_or_obj, name=None):
    if isinstance(node_or_obj, _graph.Node):
        from .ops_primitives import file as file_ops

        return file_ops.save(node_or_obj, name=name)
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
    if (
        not isinstance(nodes, _graph.OutputNode)
        and isinstance(nodes, list)
        or isinstance(nodes, tuple)
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
