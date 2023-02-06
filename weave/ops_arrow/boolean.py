import pyarrow.compute as pc
import pyarrow as pa

from ..decorator_arrow_op import arrow_op
from .. import weave_types as types

from .list_ import ArrowWeaveList, ArrowWeaveListType

unary_input_type = {
    "self": ArrowWeaveListType(types.Boolean()),
}
binary_input_type = {
    "self": ArrowWeaveListType(types.Boolean()),
    "other": types.UnionType(types.Boolean(), ArrowWeaveListType(types.Boolean())),
}

self_type_output_type_fn = lambda input_types: input_types["self"]


@arrow_op(
    name="ArrowWeaveListBoolean-equal",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def bool_equal(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListBoolean-notEqual",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def bool_not_equal(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.not_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListBoolean-and",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def bool_and(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.and_(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListBoolean-or",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def bool_or(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.or_(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListBoolean-not",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def bool_not(self):
    return ArrowWeaveList(pc.invert(self._arrow_data), types.Boolean(), self._artifact)
