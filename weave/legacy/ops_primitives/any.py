from weave import weave_types as types
from weave.legacy.decorator_op import op


@op(
    name="isNone",
    input_type={"val": types.optional(types.Any())},
    output_type=types.Boolean(),
)
def is_none(val):
    return val == None
