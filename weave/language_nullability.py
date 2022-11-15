import typing
from . import box
from . import weave_types as types
from . import op_def as OpDef
from . import op_args


def should_force_none_result(
    inputs: dict[str, typing.Any], op_def: OpDef.OpDef
) -> bool:
    # Hacking... this is nullability of ops
    # We should do this as a compile pass instead of hard-coding in engine.
    # That means we need an op called like "handle_null" that takes a function
    # as its second argument. Function is the op we want to execute if non-null.
    # TODO: fix
    # TODO: not implemented for async ops
    if inputs:
        input_name0 = list(inputs.keys())[0]
        input0 = list(inputs.values())[0]
        if input0 is None or isinstance(input0, box.BoxedNone):
            named_args = op_def.input_type.named_args()
            if len(named_args) == 0 or not types.is_optional(named_args[0].type):
                return True
            op_input_types = op_def.input_type
            if isinstance(op_input_types, op_args.OpNamedArgs):
                input0_type = op_input_types.arg_types[input_name0]
                if not types.is_optional(input0_type):
                    return True
    return False
