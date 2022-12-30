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


def process_opdef_output_type(
    op_concrete_output_type: types.Type,
    op_output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ],
    op_input_type: op_args.OpArgs,
) -> typing.Union[
    types.Type,
    typing.Callable[[typing.Dict[str, types.Type]], types.Type],
]:
    named_args = op_input_type.named_args()
    if named_args and not types.is_optional(named_args[0].type):

        def nullable_output_type(
            input_type: typing.Dict[str, types.Type]
        ) -> types.Type:
            arg0_type = input_type[named_args[0].name]
            if not isinstance(
                op_concrete_output_type, tagged_value_type.TaggedValueType
            ) and types.NoneType().assign_type(arg0_type):
                # if we're not a tag outputer and we have None as our first
                # input, then just return the type of the first input (which
                # could be tagged).
                return arg0_type
            if callable(op_output_type):
                non_null_output_type = op_output_type(input_type)
            else:
                non_null_output_type = op_output_type
            if types.is_optional(arg0_type):
                return types.optional(non_null_output_type)
            return non_null_output_type

        return nullable_output_type
    return op_output_type


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
