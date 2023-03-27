from ..api import op
from .. import weave_types as types

from .arrow import ArrowWeaveListType

from . import convert


@op(
    input_type={
        "arr": types.List(),
    },
    output_type=lambda input_types: ArrowWeaveListType(input_types["arr"].object_type),
)
def list_to_arrow(arr):
    return convert.to_arrow(arr)


@op(
    input_type={
        "self": types.UnionType(ArrowWeaveListType(), types.List()),
    },
    output_type=lambda input_types: types.List(input_types["self"].object_type),
)
def to_py(self):
    if isinstance(self, types.List):
        return self
    return self.to_pylist_tagged()
