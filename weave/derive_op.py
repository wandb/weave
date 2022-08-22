import copy
import inspect

from . import weave_types as types
from . import op_args
from . import registry_mem
from . import op_def


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
