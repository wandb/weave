import typing

from .language_features.util import currently_weavifying
from . import box
from . import weave_types as types
from . import op_args

if typing.TYPE_CHECKING:
    from . import op_def as OpDef


def should_force_none_result(
    op_def: "OpDef.OpDef", args: list[typing.Any], kwargs: dict[str, typing.Any]
) -> bool:
    # Hacking... this is nullability of ops
    # We should do this as a compile pass instead of hard-coding in engine.
    # That means we need an op called like "handle_null" that takes a function
    # as its second argument. Function is the op we want to execute if non-null.
    # TODO: fix
    # TODO: not implemented for async ops
    if not input_handles_nones(op_def._raw_input_type):
        params = op_def.input_type.create_param_dict(args, kwargs)
        first_param = params[list(params.keys())[0]]
        if first_param is None or isinstance(first_param, box.BoxedNone):
            return True
    return False


def input_handles_nones(inputs: op_args.OpArgs) -> bool:
    if isinstance(inputs, op_args.OpVarArgs):
        return True
    named_args = inputs.named_args()
    if len(named_args) == 0:
        return True
    return named_args[0].type.assign_type(types.NoneType())


def process_input_type(inputs: op_args.OpArgs) -> op_args.OpArgs:
    if input_handles_nones(inputs):
        return inputs
    inputs = typing.cast(op_args.OpNamedArgs, inputs)
    named_args = inputs.named_args()
    return op_args.OpNamedArgs(
        {**inputs.arg_types, named_args[0].name: types.optional(named_args[0].type)}
    )


def process_output_type(
    output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ],
    op_def: "OpDef.OpDef",
) -> typing.Union[
    types.Type,
    typing.Callable[[typing.Dict[str, types.Type]], types.Type],
]:
    if input_handles_nones(op_def._raw_input_type):
        return output_type

    if not callable(output_type):
        return types.optional(output_type)

    def wrapped_output_type(input_types: dict[str, types.Type]) -> types.Type:
        output_type = typing.cast(
            typing.Callable[[dict[str, types.Type]], types.Type], output_type
        )
        if currently_weavifying(input_types):
            return types.UnionType.make(  # type: ignore
                {"a": types.NoneType.make(), "b": output_type(input_types)}
            )
        else:
            first_arg_name = list(input_types.keys())[0]
            if input_types[first_arg_name].assign_type(types.NoneType()):
                _input_types = {
                    **input_types,
                    first_arg_name: types.non_none(input_types[first_arg_name]),
                }
                return types.optional(output_type(_input_types))
            return output_type(input_types)

    return wrapped_output_type
