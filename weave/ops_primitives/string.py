from ..api import op, mutation, weave_class
from .. import weave_types as types


@op(
    name="root-string",
    input_type={
        "v": types.String(),
    },
)
def string(v) -> str:
    return v


@op(
    name="string-lastLetter",
    input_type={"v": types.String()},
)
def lastLetter(v) -> str:
    return v[-1]


@weave_class(weave_type=types.String)
class String:
    @op(
        name="string-set",
        input_type={"self": types.String(), "val": types.String()},
        output_type=types.String(),
    )
    @mutation
    def set(self, val):
        return val


types.String.instance_class = String
