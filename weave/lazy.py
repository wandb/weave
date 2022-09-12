# TODO: rename this file to op_call.py
import collections
import inspect

from . import graph
from . import weave_types as types
from . import context_state
from . import weave_internal
from . import errors
from . import api
from . import language_autocall


def _ensure_node(fq_op_name, v, input_type, param_input_type, already_bound_params):
    if callable(param_input_type):
        already_bound_types = {k: n.type for k, n in already_bound_params.items()}
        already_bound_types = language_autocall.update_input_types(
            input_type,
            already_bound_types,
        )

        param_input_type = param_input_type(already_bound_types)
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

            return weave_internal.define_fn(vars, v)
        val_type = types.TypeRegistry.type_of(v)
        # TODO: should type-check v here.
        v = graph.ConstNode(val_type, v)
    return v


def _bind_params(fq_op_name, sig, args, kwargs, input_type):
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
            bound_params_with_constants[k] = _ensure_node(
                fq_op_name,
                v,
                input_type,
                input_type.arg_types[k],
                bound_params_with_constants,
            )
    return bound_params_with_constants


def _make_output_node(
    fq_op_name, bound_params, input_type, output_type_, refine_output_type
):
    output_type = output_type_
    # Don't try to refine if there are variable nodes, we are building a
    # function in that case!
    if refine_output_type and not any(
        graph.expr_vars(arg_node) for arg_node in bound_params.values()
    ):
        # If the weave.op in question is defined on a class, then the
        # incoming bound_params will have a `self` key. Interestingly,
        # the `refine_output_type` is an instance of `weave.op_def.OpDef`
        # which means that it already is bound to an object. This results
        # in two (both valid) `self` values:
        #   1. `self` in the `bound_params` which is the logical `self` in the weave graph
        #   2. `self` bound to `refine_output_type` as a byproduct of python language.
        #
        # Normally, we would do `refine_output_type(**bound_params). However.
        # Now, we _want_ to use the self in #1 as the self paramter passed to the
        # underlying implementation. So, we drop down a level and manually call
        # the underlying implementation.
        called_refine_output_type = refine_output_type.call_fn(**bound_params)
        output_type = api.use(called_refine_output_type)
    elif callable(output_type):
        new_input_type = {}
        for k, n in bound_params.items():
            if isinstance(n, graph.ConstNode):
                new_input_type[k] = types.Const(n.type, n.val)
            else:
                new_input_type[k] = n.type

        new_input_type = language_autocall.update_input_types(
            input_type, new_input_type
        )

        output_type = output_type(new_input_type)

    name = "OutputNode"
    bases = [graph.OutputNode]

    # Mixin Node methods
    bases += weave_internal.get_node_methods_classes(output_type)

    # If the output type is a run, mixin the Run's output type
    # as well. execute.py automatic inserts await_output operations
    # as needed.
    if isinstance(output_type, types.RunType) and hasattr(
        output_type.output, "NodeMethodsClass"
    ):
        name += output_type.output.__class__.__name__
        bases.append(output_type.output.NodeMethodsClass)

    node_methods_class, node_name = language_autocall.node_methods_class(output_type)
    if node_methods_class is not None:
        name += node_name
        bases.append(node_methods_class)

    return_type = type(name, tuple(bases), {})
    return return_type(output_type, fq_op_name, bound_params)


def make_lazy_call(f, fq_op_name, input_type, output_type, refine_output_type):
    """Given the parameters of an op definition, make a function that returns `graph.Node`

    Args:
        f: Op function body
        fq_op_name: Op name
        input_type: Op input_type
        output_type: Op output_type

    Returns:
        A lazy function with the same signature structure as f. The returned function accepts
        `graph.Node` arguments and will return a `graph.Node`
    """
    if hasattr(f, "sig"):
        sig = f.sig
    else:
        sig = inspect.signature(f)

    def lazy_call(*args, **kwargs):
        bound_params = _bind_params(fq_op_name, sig, args, kwargs, input_type)
        return _make_output_node(
            fq_op_name, bound_params, input_type, output_type, refine_output_type
        )

    return lazy_call


def make_eager_call(lazy_call, op_def):
    if op_def.is_async:

        def eager_call_async(*args, **kwargs):
            output_node = lazy_call(*args, **kwargs)
            return weave_internal.use(output_node)

        return eager_call_async
    else:

        def eager_call_sync(*args, **kwargs):
            return op_def.resolve_fn(*args, **kwargs)

        return eager_call_sync


def make_call(eager_call, lazy_call):
    def call(*args, **kwargs):
        if context_state.eager_mode():
            return eager_call(*args, **kwargs)
        else:
            return lazy_call(*args, **kwargs)

    return call
