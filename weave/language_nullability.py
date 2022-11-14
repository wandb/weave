import typing

from . import box
from . import errors
from . import weave_types as types

if typing.TYPE_CHECKING:
    from . import op_def as OpDef
    from . import op_args


def process_op_def_input_type(
    raw_input_type: "op_args.OpArgs", op_def: "OpDef.OpDef"
) -> "op_args.OpArgs":
    if _needs_none_wrap(raw_input_type):
        return _make_none_wrapped_input_type(raw_input_type)
    else:
        return raw_input_type


def process_op_def_resolve_fn(
    op_def: "OpDef.OpDef",
    args: list[typing.Any],
    kwargs: dict[str, typing.Any],
) -> typing.Any:
    if _needs_none_wrap(op_def.raw_input_type):
        named_args = op_def.raw_input_type.named_args()
        params = op_def.input_type.create_param_dict(args, kwargs)
        first_param = params[named_args[0].name]
        if first_param == None or isinstance(first_param, box.BoxedNone):
            return None
    return op_def.raw_resolve_fn(*args, **kwargs)


def process_opdef_output_type(
    output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ],
    op_def: "OpDef.OpDef",
) -> typing.Union[
    types.Type,
    typing.Callable[[typing.Dict[str, types.Type]], types.Type],
]:
    if _needs_none_wrap(op_def.raw_input_type):
        first_arg_name = op_def.input_type.named_args()[0].name
        if isinstance(output_type, types.Type):
            return _make_type_nullable(output_type)
        elif callable(output_type):
            callable_output_type = output_type

            def ot(input_types: typing.Dict[str, types.Type]) -> types.Type:
                return _make_type_nullable(callable_output_type(input_types))

            return ot
        else:
            raise Exception("Invalid output_type")
    else:
        return output_type


def _needs_none_wrap(input_type: "op_args.OpArgs") -> bool:
    named_args = input_type.named_args()
    return len(named_args) >= 0 and not types.is_optional(named_args[0].type)


def _make_none_wrapped_input_type(input_type: "op_args.OpArgs") -> "op_args.OpArgs":
    from . import op_args

    if not isinstance(input_type, op_args.OpNamedArgs):
        raise errors.WeaveTypeError("Can only wrap named args")
    named_args = input_type.named_args()
    first_arg = named_args[0]
    return op_args.OpNamedArgs(
        {**input_type.arg_types, first_arg.name: _make_type_nullable(first_arg.type)}
    )


def _make_type_nullable(type: types.Type) -> types.Type:
    return types.union(type, types.NoneType())
