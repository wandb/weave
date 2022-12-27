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


def adjust_assignable_param_dict_for_dispatch(
    op: OpDef.OpDef, param_dict: dict[str, types.Type], query: str
) -> dict[str, types.Type]:
    if isinstance(op.input_type, op_args.OpNamedArgs):
        named_args = op.input_type.named_args()
        if len(named_args) > 0:
            first_arg = named_args[0]
            if not first_arg.type.assign_type(types.NoneType()):
                non_none_type = types.non_none(param_dict[first_arg.name])
                return {**param_dict, first_arg.name: non_none_type}
    return param_dict


def adjust_input_type_for_mixin_dispatch(input_type: types.Type) -> types.Type:
    return types.union(types.NoneType(), input_type)
