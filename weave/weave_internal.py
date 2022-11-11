import collections
import inspect
import typing
from . import graph
from . import weave_types as types
from . import context_state
from . import errors
from . import client_interface
from . import op_args
from .language_features.tagging import tagged_value_type
from . import language_autocall


def dereference_variables(node: graph.Node, var_values: graph.Frame) -> graph.Node:
    def map_fn(n: graph.Node) -> graph.Node:
        if isinstance(n, graph.VarNode):
            return var_values[n.name]
        return n

    return graph.map_nodes(node, map_fn)


def call_fn(weave_fn: graph.Node, inputs: graph.Frame) -> graph.Node:
    return dereference_variables(weave_fn, inputs)


def better_call_fn(weave_fn, *inputs):
    call_inputs = {}
    for input_name, input in zip(weave_fn.type.input_types.keys(), inputs):
        call_inputs[input_name] = input
    res = call_fn(weave_fn.val, call_inputs)
    return make_output_node(res.type, res.from_op.name, res.from_op.inputs)


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


class UniversalNodeMixin:
    pass


# TODO: remove from PR
def _get_common_union_type_class(type_):
    if isinstance(type_, types.UnionType):
        members = type_.members
        class0 = members[0].__class__
        if all(m.__class__ == class0 for m in members[1:]):
            return class0
    return None


def get_node_methods_classes(type_: types.Type) -> typing.Sequence[typing.Type]:
    classes = []

    # If we have a union of all the same type class, then use that
    # type class for our Node Methods.
    # TODO: This is not as general as WeaveJS!
    tc = _get_common_union_type_class(type_)
    if tc is None:
        tc = type_.__class__

    # When the type is a TaggedValueType, use the inner type to determine methods.
    if isinstance(type_, tagged_value_type.TaggedValueType):
        return get_node_methods_classes(type_.value)

    # Keeping this is still important for overriding dunder methods!
    for type_class in type_.__class__.mro():
        if (
            issubclass(type_class, types.Type)
            and type_class.NodeMethodsClass is not None
            and type_class.NodeMethodsClass not in classes
        ):
            classes.append(type_class.NodeMethodsClass)

    for mixin in UniversalNodeMixin.__subclasses__():
        # Add a fallback dispatcher which us invoked if nothing else matches.
        classes.append(mixin)
    return classes


def make_var_node(type_: types.Type, name: str) -> graph.VarNode:
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


def make_const_node(type_: types.Type, val: typing.Any) -> graph.ConstNode:
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


def make_output_node(
    type_: types.Type, op_name: str, op_params: dict[str, graph.Node]
) -> graph.OutputNode:
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
def define_fn(
    parameters: dict[str, types.Type], body: typing.Callable[..., graph.Node]
) -> graph.ConstNode:
    var_nodes = [make_var_node(t, k) for k, t in parameters.items()]
    try:
        fnNode = body(*var_nodes)
    except errors.WeaveExpectedConstError as e:
        raise errors.WeaveMakeFunctionError("function body expected const node.")
    if not isinstance(fnNode, graph.Node):
        raise errors.WeaveMakeFunctionError("output_type function must return a node.")
    return graph.ConstNode(types.Function(parameters, fnNode.type), fnNode)


ENVType = typing.Union[graph.Node, typing.Callable[..., graph.Node]]
ENInputTypeType = typing.Optional[
    typing.Union[types.Type, typing.Callable[..., types.Type]]
]
ENBoundParamsType = typing.Optional[dict[str, graph.Node]]


def _ensure_node(
    fq_op_name: str,
    v: ENVType,
    param_input_type: ENInputTypeType = None,
    input_type: op_args.OpArgs = None,
    already_bound_params: ENBoundParamsType = None,
) -> graph.Node:
    if callable(param_input_type):
        if already_bound_params is None:
            already_bound_params = {}
        already_bound_types = {k: n.type for k, n in already_bound_params.items()}
        already_bound_types = language_autocall.update_input_types(
            input_type, already_bound_types
        )
        try:
            param_input_type = param_input_type(already_bound_types)
        except AttributeError as e:
            raise errors.WeaveInternalError(
                f"callable input_type of {fq_op_name} failed to accept already_bound_types of {already_bound_types}"
            )
    if not isinstance(v, graph.Node):
        if callable(v):
            if not isinstance(param_input_type, types.Function):
                raise errors.WeaveInternalError(
                    "callable passed as argument, but type is not Function. Op: %s"
                    % fq_op_name
                )

            # Allow passing in functions with fewer arguments then the op
            # declares. E.g. for List.map I pass either of these:
            #    lambda row, index: ...
            #    lambda row: ...
            sig = inspect.signature(v)
            vars = {}
            for name in list(param_input_type.input_types.keys())[
                : len(sig.parameters)
            ]:
                vars[name] = param_input_type.input_types[name]

            return define_fn(vars, v)
        val_type = types.TypeRegistry.type_of(v)
        # TODO: should type-check v here.
        v = graph.ConstNode(val_type, v)
    return v


def bind_value_params_as_nodes(
    fq_op_name: str,
    sig: inspect.Signature,
    args: typing.Sequence[typing.Any],
    kwargs: typing.Mapping[str, typing.Any],
    input_type: op_args.OpArgs,
) -> collections.OrderedDict[str, graph.Node]:
    bound_params = sig.bind(*args, **kwargs)
    bound_params_with_constants = collections.OrderedDict()
    for k, v in bound_params.arguments.items():
        param = sig.parameters[k]
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            for sub_k, sub_v in v.items():
                bound_params_with_constants[sub_k] = _ensure_node(
                    fq_op_name, sub_v, None, None, None
                )
        else:
            if not isinstance(input_type, op_args.OpNamedArgs):
                raise errors.WeaveDefinitionError(
                    f"Error binding params to {fq_op_name} - found named params in signature, but op does not have named param args"
                )
            bound_params_with_constants[k] = _ensure_node(
                fq_op_name,
                v,
                input_type.arg_types[k],
                input_type,
                bound_params_with_constants,
            )
    return bound_params_with_constants
