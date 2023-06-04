import typing
import pyarrow.compute as pc
import pyarrow as pa

from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from ..api import op
from .list_ import ArrowWeaveList, ArrowWeaveListType
from .. import timestamp as weave_timestamp
from . import util

ARROW_WEAVE_LIST_TIMESTAMP_TYPE = ArrowWeaveListType(types.Timestamp())
ARROW_WEAVE_LIST_BOOLEAN_TYPE = ArrowWeaveListType(types.Boolean())

binary_input_type = {
    "self": ARROW_WEAVE_LIST_TIMESTAMP_TYPE,
    "other": types.UnionType(types.Timestamp(), ARROW_WEAVE_LIST_TIMESTAMP_TYPE),
}


@arrow_op(
    name="ArrowWeaveListDate-toNumber",
    input_type={"self": ArrowWeaveListType(types.optional(types.Timestamp()))},
    output_type=ArrowWeaveListType(types.optional(types.Int())),
)
def to_number(self):
    return ArrowWeaveList(
        pc.milliseconds_between(pa.timestamp("ms", 0), self._arrow_data),
        types.optional(types.Timestamp()),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListDate-floor",
    input_type={"self": ArrowWeaveListType(types.optional(types.Timestamp()))},
    output_type=ArrowWeaveListType(types.optional(types.Timestamp())),
)
def floor(self, multiple_s: int):
    return ArrowWeaveList(
        pc.floor_temporal(self._arrow_data, multiple=multiple_s, unit="second"),
        types.optional(types.Timestamp()),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListDate-ceil",
    input_type={"self": ArrowWeaveListType(types.optional(types.Timestamp()))},
    output_type=ArrowWeaveListType(types.optional(types.Timestamp())),
)
def ceil(self, multiple_s: int):
    return ArrowWeaveList(
        pc.ceil_temporal(
            self._arrow_data,
            multiple=multiple_s,
            unit="second",
            ceil_is_strictly_greater=True,
        ),
        types.optional(types.Timestamp()),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListDate-__lt__",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def le(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.less(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListDate-__le__",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def lt(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.less_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListDate-__gt__",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def gt(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.greater(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListDate-__ge__",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def ge(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.greater_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )
