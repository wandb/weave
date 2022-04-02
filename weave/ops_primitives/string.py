from ..api import op, mutation, weave_class
from .. import weave_types as types


@op(
    name="root-string",
)
def string(v: str) -> str:
    return v


@op(
    name="string-lastLetter",
)
def lastLetter(v: str) -> str:
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
