from ..decorator_op import op
from .. import weave_types as types


@op(
    name="isNone",
    input_type={"val": types.optional(types.Any())},
    output_type=types.Boolean(),
)
def is_none(val):
    return val == None
