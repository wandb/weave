import typing
from . import box
from . import errors
from . import weave_types as types
from . import op_def as OpDef
from . import op_args
from . import registry_mem


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
    op: OpDef.OpDef,
    param_dict: dict[str, types.Type],
    is_exact_match: bool,
) -> dict[str, types.Type]:
    if isinstance(op.input_type, op_args.OpNamedArgs):
        named_args = op.input_type.named_args()
        if len(named_args) > 0:
            first_arg = named_args[0]
            p_type = param_dict[first_arg.name]

            # the op's first arg does not explicitly consume a null, but
            # it still must accept null due to nullability rules.
            if not first_arg.type.assign_type(types.NoneType()):

                # here we make it look as though the first arg is the concrete
                # component of an optional type if p_type is optional.
                non_none_type = types.non_none(p_type)

                # p_type is explicitly a none type (with no concrete type),
                # we should still let it pass through as a none type.
                # in that case, non_none_type will be types.Invalid().

                # pick this off for testing mutual assignability
                if isinstance(p_type, types.Const):
                    p_type = p_type.val_type

                if types.Invalid().assign_type(non_none_type):
                    # see if there is an exact match for the original op query

                    if is_exact_match and types.types_are_mutually_assignable(
                        p_type, types.NoneType()
                    ):
                        return {**param_dict, first_arg.name: first_arg.type}

                return {**param_dict, first_arg.name: non_none_type}
    return param_dict


def adjust_input_type_for_mixin_dispatch(input_type: types.Type) -> types.Type:
    return types.union(types.NoneType(), input_type)
