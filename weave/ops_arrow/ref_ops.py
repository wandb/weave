import pyarrow.compute as pc
import pyarrow as pa

from ..decorator_op import op
from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from . import util
from .list_ import ArrowWeaveList, ArrowWeaveListType


nullable_binary_input_type = {
    "self": ArrowWeaveListType(types.optional(types.RefType())),
    "other": types.UnionType(
        types.optional(types.RefType()),
        ArrowWeaveListType(types.optional(types.RefType())),
    ),
}


@arrow_op(
    name="ArrowWeaveListRef-equal",
    input_type=nullable_binary_input_type,
    output_type=ArrowWeaveListType(types.Boolean()),
)
def ref_equal(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    else:
        from .. import storage

        other_ref = storage._get_ref(other)
        other = str(other_ref)
    self_ = self.map_column(
        lambda col, path: ArrowWeaveList(col._arrow_data, types.String())
    )
    # self_arrow_data = pc.cast(self._arrow_data, pa.string())
    result = util.equal(self_._arrow_data, other)
    return ArrowWeaveList(result, types.Boolean(), self._artifact)
