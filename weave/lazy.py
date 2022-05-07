# TODO: rename this file to op_call.py
import collections
import inspect

from . import graph
from . import weave_types as types
from . import context
from . import api


def _ensure_node(v):
    if not isinstance(v, graph.Node):
        val_type = types.TypeRegistry.type_of(v)
        # TODO: should type-check v here.
        v = graph.ConstNode(types.Const(val_type, v), v)
    return v


def _bind_params(sig, args, kwargs, input_type):
    bound_params = sig.bind(*args, **kwargs)
    bound_params_with_constants = collections.OrderedDict()
    for k, v in bound_params.arguments.items():
        param = sig.parameters[k]
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            for sub_k, sub_v in v.items():
                bound_params_with_constants[sub_k] = _ensure_node(sub_v)
        else:
            bound_params_with_constants[k] = _ensure_node(v)
    return bound_params_with_constants


def _make_output_node(fq_op_name, bound_params, output_type_):
    output_type = output_type_
    if callable(output_type):
        new_input_type = {k: n.type for k, n in bound_params.items()}
        output_type = output_type(new_input_type)

    if hasattr(output_type, "NodeMethodsClass"):
        name = "OutputNode%s" % output_type.__class__.__name__
        bases = [graph.OutputNode, output_type.NodeMethodsClass]

        # If the output type is a run, mixin the Run's output type
        # as well. execute.py automatic inserts await_output operations
        # as needed.
        if isinstance(output_type, types.RunType) and hasattr(
            output_type._output, "NodeMethodsClass"
        ):
            name += output_type._output.__class__.__name__
            bases.append(output_type._output.NodeMethodsClass)

        return_type = type(name, tuple(bases), {})
    else:
        return_type = graph.OutputNode
    return return_type(output_type, fq_op_name, bound_params)


def make_lazy_call(f, fq_op_name, input_type, output_type):
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
        bound_params = _bind_params(sig, args, kwargs, input_type)
        return _make_output_node(fq_op_name, bound_params, output_type)

    return lazy_call


def make_eager_call(lazy_call):
    def eager_call(*args, **kwargs):
        output_node = lazy_call(*args, **kwargs)
        return api.use(output_node)

    return eager_call


def make_call(eager_call, lazy_call):
    def call(*args, **kwargs):
        if context.eager_mode():
            return eager_call(*args, **kwargs)
        else:
            return lazy_call(*args, **kwargs)

    return call
