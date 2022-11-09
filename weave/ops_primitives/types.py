from ..api import op
from .. import weave_types as types


@op(
    name="op-non_none",
    input_type={
        "obj_type": types.Type(),
    },
    output_type=types.Type(),
)
def op_non_none(obj_type):  # type: ignore
    if types.is_optional(obj_type):
        return types.non_none(obj_type)
    return obj_type
