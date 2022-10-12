from ..api import op
from .. import weave_types as types


@op(
    name="tagged-unwrapTaggedValue",
    input_type={
        "tagged_value": types.TaggedType(types.TypedDict({}), types.Any()),
    },
    output_type=lambda input_types: input_types["tagged_value"]._value,
)
def unwrap_tagged_value(tagged_value):
    return tagged_value._value
