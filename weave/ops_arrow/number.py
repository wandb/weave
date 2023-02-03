import pyarrow.compute as pc
import pyarrow as pa

from ..decorator_arrow_op import arrow_op
from .. import weave_types as types
from ..api import op
from .list_ import ArrowWeaveList, ArrowWeaveListType

ARROW_WEAVE_LIST_NUMBER_TYPE = ArrowWeaveListType(types.Number())
ARROW_WEAVE_LIST_BOOLEAN_TYPE = ArrowWeaveListType(types.Boolean())
ARROW_WEAVE_LIST_STRING_TYPE = ArrowWeaveListType(types.String())

unary_input_type = {
    "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
}
binary_input_type = {
    "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
    "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
}


def self_type_output_type_fn(input_types):
    return input_types["self"]


# TODO: weirdly need to name this "<something>-add" since that's what the base
# Number op does. But we'd like to get rid of that requirement so we don't
# need name= for any ops!
@arrow_op(
    name="ArrowWeaveListNumber-add",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def __add__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.add(self._arrow_data, other), types.Number(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-mult",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def __mul__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.multiply(self._arrow_data, other), types.Number(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-div",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def __truediv__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.divide(self._arrow_data, other), types.Number(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-sub",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def __sub__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.subtract(self._arrow_data, other), types.Number(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-powBinary",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def __pow__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.power(self._arrow_data, other), types.Number(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-notEqual",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __ne__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.not_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-equal",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __eq__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-greater",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __gt__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.greater(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-greaterEqual",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __ge__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.greater_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-less",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __lt__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.less(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-lessEqual",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __le__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.less_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListNumber-negate",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def __neg__(self):
    return ArrowWeaveList(pc.negate(self._arrow_data), types.Number(), self._artifact)


# todo: fix op decorator to not require name here,
# these names are needed because the base class also has an op called floor.
# also true for ceil below
@arrow_op(
    name="ArrowWeaveListNumber-floor",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def floor(self):
    return ArrowWeaveList(pc.floor(self._arrow_data), types.Number(), self._artifact)


@arrow_op(
    name="ArrowWeaveListNumber-ceil",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def ceil(self):
    return ArrowWeaveList(pc.ceil(self._arrow_data), types.Number(), self._artifact)


@arrow_op(
    name="ArrowWeaveListNumber-abs",
    input_type={"self": ArrowWeaveListType(types.optional(types.Number()))},
    output_type=self_type_output_type_fn,
)
def abs(self):
    return ArrowWeaveList(pc.abs(self._arrow_data), types.Number(), self._artifact)


@arrow_op(
    name="ArrowWeaveListNumber-toFixed",
    input_type={
        "self": ArrowWeaveListType(types.optional(types.Number())),
        "digits": types.Number(),
    },
    output_type=self_type_output_type_fn,
)
def to_fixed(self, digits):
    return ArrowWeaveList(
        pc.round(self._arrow_data, int(digits)), types.Number(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-max",
    input_type={"self": ArrowWeaveListType(types.optional(types.Number()))},
    output_type=types.Number(),
)
def max(self):
    array = self._arrow_data_asarray_no_tags()
    return pc.max(array).as_py()


@op(
    name="ArrowWeaveListNumber-min",
    input_type={"self": ArrowWeaveListType(types.optional(types.Number()))},
    output_type=types.Number(),
)
def min(self):
    array = self._arrow_data_asarray_no_tags()
    return pc.min(array).as_py()


# TODO: Do we need to vectorize these in 1 more dimension?
@op(
    name="ArrowWeaveListNumbers-argmax",
    input_type={"self": ArrowWeaveListType(types.optional(types.Number()))},
    output_type=types.Number(),
)
def argmax(self):
    array = self._arrow_data_asarray_no_tags()
    return pc.index(array, pc.max(array)).as_py()


@op(
    name="ArrowWeaveListNumbers-argmin",
    input_type={"self": ArrowWeaveListType(types.optional(types.Number()))},
    output_type=types.Number(),
)
def argmin(self):
    array = self._arrow_data_asarray_no_tags()
    return pc.index(array, pc.min(array)).as_py()


@op(
    name="ArrowWeaveListNumbers-stddev",
    input_type={"self": ArrowWeaveListType(types.optional(types.Number()))},
    output_type=types.Number(),
)
def stddev(self):
    array = self._arrow_data_asarray_no_tags()
    return pc.stddev(array).as_py()


@arrow_op(
    name="ArrowWeaveListNumber-toTimestamp",
    input_type=unary_input_type,
    output_type=ArrowWeaveListType(types.optional(types.Timestamp())),
)
def to_timestamp(self):
    # TODO: We may need to handle more conversion points similar to Weave0
    timestamp_second_upper_bound = 60 * 60 * 24 * 365 * 1000
    # first 1000 years
    second_mask = pc.less(self._arrow_data, timestamp_second_upper_bound)
    data = pc.replace_with_mask(
        self._arrow_data, second_mask, pc.multiply(self._arrow_data, pa.scalar(1000.0))
    )
    return ArrowWeaveList(
        data.cast("int64").cast(pa.timestamp("ms", tz="+00:00")),
        types.Timestamp(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListNumber-toString",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_STRING_TYPE,
)
def to_string(self):
    return ArrowWeaveList(
        pc.cast(self._arrow_data, "string"), types.String(), self._artifact
    )
