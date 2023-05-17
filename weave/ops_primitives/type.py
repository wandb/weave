from ..api import op
from .. import weave_types as types


@op(
    name="type-name",
)
def type_name(self: types.Type) -> str:
    return self.name
