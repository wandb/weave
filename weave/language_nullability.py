import typing
from . import box
from . import weave_types as types
from . import op_args
from .language_features.tagging import tagged_value_type

if typing.TYPE_CHECKING:
    from . import op_def as OpDef


def should_force_none_result(
    inputs: dict[str, typing.Any], op_def: "OpDef.OpDef"
) -> bool:
    # Hacking... this is nullability of ops
    # We should do this as a compile pass instead of hard-coding in engine.
    # That means we need an op called like "handle_null" that takes a function
    # as its second argument. Function is the op we want to execute if non-null.
    # TODO: fix
    # TODO: not implemented for async ops
    if inputs:
        input0 = list(inputs.values())[0]
        if input0 is None or isinstance(input0, box.BoxedNone):
            named_args = op_def.input_type.named_args()
            if len(named_args) == 0 or (
                not isinstance(
                    op_def.concrete_output_type, tagged_value_type.TaggedValueType
                )
                and not isinstance(
                    named_args[0].type, tagged_value_type.TaggedValueType
                )
                and not types.is_optional(named_args[0].type)
            ):
                return True
    return False


def adjust_assignable_param_dict_for_dispatch(
    op: "OpDef.OpDef", param_dict: dict[str, types.Type]
) -> dict[str, types.Type]:
    if isinstance(op.input_type, op_args.OpNamedArgs):
        named_args = op.input_type.named_args()
        if len(named_args) > 0:
            first_arg = named_args[0]
            first_param_type = param_dict[first_arg.name]
            if not first_arg.type.assign_type(types.NoneType()):
                if types.NoneType().assign_type(first_param_type):
                    return {**param_dict, first_arg.name: first_arg.type}
                non_none_type = types.non_none(first_param_type)
                return {**param_dict, first_arg.name: non_none_type}
    return param_dict


def adjust_input_type_for_mixin_dispatch(input_type: types.Type) -> types.Type:
    return types.union(types.NoneType(), input_type)
