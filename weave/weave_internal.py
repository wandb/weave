import typing
from . import graph
from . import weave_types as types
from . import context_state
from . import errors
from . import client_interface


def dereference_variables(
    node: graph.Node, var_values: graph.Frame, missing_ok: bool = False
) -> graph.Node:
    def map_fn(n: graph.Node) -> graph.Node:
        if isinstance(n, graph.VarNode):
            try:
                return var_values[n.name]
            except KeyError:
                pass
                # if not missing_ok:
                #     raise errors.WeaveMissingVariableError(n.name)
        return n

    return graph.map_nodes_top_level([node], map_fn)[0]


def call_fn(
    weave_fn: graph.Node,
    inputs: graph.Frame,
) -> graph.Node:
    return dereference_variables(weave_fn, inputs)


def better_call_fn(weave_fn: graph.ConstNode, *inputs: graph.Node) -> graph.Node:
    call_inputs = {}
    if not isinstance(weave_fn.type, types.Function):
        raise errors.WeaveInternalError(
            "Expected function type, got %s" % weave_fn.type
        )
    for input_name, input in zip(weave_fn.type.input_types.keys(), inputs):
        call_inputs[input_name] = input
    res = call_fn(weave_fn.val, call_inputs)  # type: ignore
    # Convert to Runtime nodes so dispatch works.
    if isinstance(res, graph.OutputNode):
        return make_output_node(res.type, res.from_op.name, res.from_op.inputs)  # type: ignore
    elif isinstance(res, graph.VarNode):
        return make_var_node(res.type, res.name)
    elif isinstance(res, graph.ConstNode):
        return make_const_node(res.type, res.val)
    else:
        raise errors.WeaveInternalError("Invalid Node: %s" % res)


def use(
    nodes: typing.Union[graph.Node, typing.Sequence[graph.Node]],
    client: typing.Union[client_interface.ClientInterface, None] = None,
) -> typing.Union[typing.Any, typing.Sequence[typing.Any]]:
    if client is None:
        client = context_state.get_client()
        if client is None:
            raise errors.WeaveInternalError("no client set")
    single = True
    if not isinstance(nodes, graph.Node):
        single = False
    else:
        nodes = [nodes]

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


def make_var_node(type_: types.Type, name: str) -> graph.VarNode:
    # Circular import. TODO: fix
    from . import dispatch

    return dispatch.RuntimeVarNode(type_, name)


def make_const_node(type_: types.Type, val: typing.Any) -> graph.ConstNode:
    # Circular import. TODO: fix
    from . import dispatch

    return dispatch.RuntimeConstNode(type_, val)


def const(val: typing.Any, type: typing.Optional[types.Type] = None) -> graph.ConstNode:
    if type is None:
        type = types.TypeRegistry.type_of(val)
    return make_const_node(type, val)


def make_var_for_value(v: typing.Any, name: str) -> graph.VarNode:
    """Make a VarNode whose value is v."""
    if not isinstance(v, graph.Node):
        v = const(v)
    new_var = make_var_node(v.type, name)
    new_var._var_val = v
    return new_var


def make_output_node(
    type_: types.Type, op_name: str, op_params: dict[str, graph.Node]
) -> graph.OutputNode:
    # Circular import. TODO: fix
    from . import dispatch

    return dispatch.RuntimeOutputNode(type_, op_name, op_params)


# Given a registered op, make a mapped version of it.
def define_fn(
    parameters: dict[str, types.Type], body: typing.Callable[..., graph.Node]
) -> graph.ConstNode:
    var_nodes = [make_var_node(t, k) for k, t in parameters.items()]
    try:
        from . import op_def

        with op_def.no_refine():
            fnNode = body(*var_nodes)
    except errors.WeaveExpectedConstError as e:
        raise errors.WeaveMakeFunctionError("function body expected const node.")
    if not isinstance(fnNode, graph.Node):
        raise errors.WeaveMakeFunctionError("output_type function must return a node.")
    return const(fnNode, types.Function(parameters, fnNode.type))


ENVType = typing.Union[graph.Node, typing.Callable[..., graph.Node]]
ENInputTypeType = typing.Optional[
    typing.Union[types.Type, typing.Callable[..., types.Type]]
]
ENBoundParamsType = typing.Optional[dict[str, graph.Node]]


# this refines all the nodes in a graph. it's useful / needed if you do call_fn on some arguments
# that have a different type than exact type of the function inputs, e.g., the argument is tagged
# and the function doesn't explicitly operate on tagged values. this ensures that the input tags
# are propagated appropriately to the output type of the function.
def refine_graph(node: graph.Node) -> graph.Node:
    from .registry_mem import memory_registry

    if isinstance(node, (graph.ConstNode, graph.VoidNode, graph.VarNode)):
        return node
    elif isinstance(node, graph.OutputNode):
        op_name = node.from_op.name
        op = memory_registry.get_op(op_name)
        if op is None:
            raise ValueError("No op named %s" % op_name)
        refined_inputs: dict[str, typing.Any] = {}
        for input_name, input_node in node.from_op.inputs.items():
            refined_input = refine_graph(input_node)
            refined_inputs[input_name] = refined_input
        return op(**refined_inputs)

    else:
        raise NotImplementedError(
            "refine_graph cannot yet handle nodes of type %s" % type(node)
        )


def manual_call(
    op_name: str, inputs: dict[str, graph.Node], output_type: types.Type
) -> graph.Node:
    """Produce an output node manually.

    You can produce incorrect nodes this way. Use with caution.
    """
    from . import dispatch

    return dispatch.RuntimeOutputNode(output_type, op_name, inputs)
