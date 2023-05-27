import typing
from ..api import op
from .. import errors
from .. import weave_types as types


@op(
    name="type-name",
)
def type_name(self: types.Type) -> str:
    return self.name


def _cast_output_type(input_type):
    if not isinstance(input_type["to_type"], types.Const):
        raise errors.WeaveTypeError(f"Expected Const, got {input_type}")
    return input_type["to_type"].val


# This is not yet supported in js. The right argument needs to be Const,
# but we don't have a way to construct const objects in js yet.
@op(
    input_type={"to_type": types.Const(types.Type(), None)},
    output_type=_cast_output_type,
)
def cast(obj: typing.Any, to_type):
    obj_type = types.TypeRegistry.type_of(obj)
    if not to_type.assign_type(obj_type):
        raise errors.WeaveTypeError(f"Cannot cast {obj_type} to {to_type}")
    return obj
