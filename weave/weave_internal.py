from . import graph
from . import weave_types as types
from . import context_state
from . import errors


def dereference_variables(node, var_values):
    def map_fn(n):
        if isinstance(n, graph.VarNode):
            return var_values[n.name]

    return graph.map_nodes(node, map_fn)


def call_fn(weave_fn, inputs):
    return dereference_variables(weave_fn, inputs)


def better_call_fn(weave_fn, *inputs):
    call_inputs = {}
    for input_name, input in zip(weave_fn.type.input_types.keys(), inputs):
        call_inputs[input_name] = input
    res = call_fn(weave_fn.val, call_inputs)
    return make_output_node(res.type, res.from_op.name, res.from_op.inputs)


def use(nodes, client=None):
    if client is None:
        client = context_state.get_client()
    single = True
    if not isinstance(nodes, graph.Node) and (
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
        if not isinstance(node, graph.Node):
            if context_state.eager_mode():
                raise errors.WeaveApiError("use not allowed in eager mode.")
            else:
                raise errors.WeaveApiError("non-Node passed to use(): %s" % type(node))
        actual_nodes.append(node)

    result = client.execute(actual_nodes)

    if single:
        result = result[0]
    return result


# TODO: remove from PR
def _get_common_union_type_class(type_):
    if isinstance(type_, types.UnionType):
        members = type_.members
        class0 = members[0].__class__
        if all(m.__class__ == class0 for m in members[1:]):
            return class0
    return None


def get_node_methods_classes(type_):
    classes = []

    # If we have a union of all the same type class, then use that
    # type class for our Node Methods.
    # TODO: This is not as general as WeaveJS!
    tc = _get_common_union_type_class(type_)
    if tc is None:
        tc = type_.__class__

    for type_class in tc.mro():
        if (
            hasattr(type_class, "NodeMethodsClass")
            and type_class.NodeMethodsClass not in classes
        ):
            classes.append(type_class.NodeMethodsClass)
    return classes


def make_var_node(type_, name):
    node_methods_classes = get_node_methods_classes(type_)
    if node_methods_classes:
        return_type = type(
            "VarNode%s" % type_.__class__.__name__,
            (graph.VarNode, *node_methods_classes),
            {},
        )
    else:
        return_type = graph.VarNode
    return return_type(type_, name)


def make_const_node(type_, val):
    node_methods_classes = get_node_methods_classes(type_)
    if node_methods_classes:
        return_type = type(
            "ConstNode%s" % type_.__class__.__name__,
            (graph.ConstNode, *node_methods_classes),
            {},
        )
    else:
        return_type = graph.ConstNode
    return return_type(type_, val)


def const(val, type=None):
    if type is None:
        type = types.TypeRegistry.type_of(type)
    return make_const_node(type, val)


def make_output_node(type_, op_name, op_params):
    node_methods_classes = get_node_methods_classes(type_)
    if node_methods_classes:
        return_type = type(
            "OutputNode%s" % type_.__class__.__name__,
            (graph.OutputNode, *node_methods_classes),
            {},
        )
    else:
        return_type = graph.OutputNode
    return return_type(type_, op_name, op_params)


# Given a registered op, make a mapped version of it.


def define_fn(parameters, body):
    var_nodes = [make_var_node(t, k) for k, t in parameters.items()]
    fnNode = body(*var_nodes)
    return graph.ConstNode(types.Function(parameters, fnNode.type), fnNode)
