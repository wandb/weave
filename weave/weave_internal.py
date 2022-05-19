import copy
import inspect
from . import graph

from . import weave_types as types
from . import client
from . import op_args
from . import server
from . import registry_mem
from . import op_def
from . import lazy


def map_nodes(node, map_fn):
    if isinstance(node, graph.OutputNode):
        new_inputs = {k: map_nodes(v, map_fn) for (k, v) in node.from_op.inputs.items()}
        node = graph.OutputNode(node.type, node.from_op.name, new_inputs)
    result = map_fn(node)
    if result is None:
        return node
    return result


def dereference_variables(node, var_values):
    def map_fn(n):
        if isinstance(n, graph.VarNode):
            return var_values[n.name]

    return map_nodes(node, map_fn)


def call_fn(weave_fn, inputs):
    return dereference_variables(weave_fn, inputs)


def use_internal(nodes):
    weave_client = client.Client(server.InProcessServer())
    single = True
    try:
        iter(nodes)
        single = False
    except TypeError:
        pass
    if single:
        nodes = (nodes,)
    result = weave_client.execute(nodes, no_cache=True)
    if single:
        return result[0]
    return result


def make_var_node(type_, name):
    if hasattr(type_, "NodeMethodsClass"):
        return_type = type(
            "VarNode%s" % type_.__class__.__name__,
            (graph.VarNode, type_.NodeMethodsClass),
            {},
        )
    else:
        return_type = graph.VarNode
    return return_type(type_, name)


def make_const_node(type_, val):
    if hasattr(type_, "NodeMethodsClass"):
        return_type = type(
            "ConstNode%s" % type_.__class__.__name__,
            (graph.ConstNode, type_.NodeMethodsClass),
            {},
        )
    else:
        return_type = graph.ConstNode
    return return_type(type_, val)


def make_output_node(type_, op_name, op_inputs):
    if hasattr(type_, "NodeMethodsClass"):
        return_type = type(
            "OutputNode%s" % type_.__class__.__name__,
            (graph.OutputNode, type_.NodeMethodsClass),
            {},
        )
    else:
        return_type = graph.OutputNode
    return return_type(type_, op_name, op_inputs)


# Given a registered op, make a mapped version of it.


def define_fn(parameters, body):
    varNodes = {k: make_var_node(t, k) for k, t in parameters.items()}
    fnNode = body(**varNodes)
    return graph.ConstNode(types.Function(parameters, fnNode.type), fnNode)


def make_mapped_op(op_name):
    mapped_op_name = "list-%s" % op_name  # TODO: doesn't handle fqn

    op = registry_mem.memory_registry.get_op(op_name)
    if op.input_type.kind != op_args.OpArgs.NAMED_ARGS:
        raise Exception("Can't make mapped op with non-NAMED_ARGS yet")
    arg_types = op.input_type.arg_types
    op_param_names = list(arg_types.keys())
    mapped_param_name = op_param_names[0]

    # first argument is mapped, everything else is the same
    input_types = copy.copy(arg_types)
    input_types[mapped_param_name] = types.List(arg_types[mapped_param_name])

    if not callable(op.output_type):
        output_type = types.List(op.output_type)
    else:

        def make_output_type(input_types):
            inner_input_types = copy.copy(input_types)
            inner_input_types[mapped_param_name] = input_types[
                mapped_param_name
            ].object_type
            return types.List(op.output_type(inner_input_types))

        output_type = make_output_type

    def resolve(**inputs):
        new_inputs = copy.copy(inputs)
        list_ = new_inputs.pop(mapped_param_name)
        return [op.resolve_fn(x, **new_inputs) for x in list_]

    # Use the function signature of the original op to compute the signature
    # of the lazy call
    resolve.sig = inspect.signature(op.resolve_fn)

    new_op = op_def.OpDef(
        mapped_op_name, op_args.OpNamedArgs(input_types), output_type, resolve
    )
    op_version = registry_mem.memory_registry.register_op(new_op)

    return op_version.call_fn
