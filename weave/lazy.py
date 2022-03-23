import collections
import inspect

from . import graph
from . import weave_types as types


def _ensure_node(v):
    if not isinstance(v, graph.Node):
        val_type = types.TypeRegistry.type_of(v)
        # TODO: should type-check v here.
        # TODO: make all Const nodes into Const Types!
        # TODO: need to do this in api as well
        if isinstance(val_type, types.String):
            v = graph.ConstNode(types.ConstString(v), v)
        else:
            v = graph.ConstNode(val_type, v)
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
