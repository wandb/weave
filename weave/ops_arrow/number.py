import pyarrow.compute as pc

from ..api import op
from .. import weave_types as types

from .list_ import ArrowWeaveList, ArrowWeaveListType


ARROW_WEAVE_LIST_NUMBER_TYPE = ArrowWeaveListType(types.Number())

# TODO: weirdly need to name this "<something>-add" since that's what the base
# Number op does. But we'd like to get rid of that requirement so we don't
# need name= for any ops!
@op(
    name="ArrowWeaveListNumber-add",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def __add__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.add(self._arrow_data, other), types.Number(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-mult",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def __mul__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.multiply(self._arrow_data, other), types.Number(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-div",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def __truediv__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.divide(self._arrow_data, other), types.Number(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-sub",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def __sub__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.subtract(self._arrow_data, other), types.Number(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-powBinary",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def __pow__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.power(self._arrow_data, other), types.Number(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-notEqual",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
)
def __ne__(self, other) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.not_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-equal",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
)
def __eq__(self, other) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-greater",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
)
def __gt__(self, other) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.greater(self._arrow_data, other), types.Boolean(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-greaterEqual",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
)
def __ge__(self, other) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.greater_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-less",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
)
def __lt__(self, other) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.less(self._arrow_data, other), types.Boolean(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-lessEqual",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
        "other": types.UnionType(types.Number(), ARROW_WEAVE_LIST_NUMBER_TYPE),
    },
)
def __le__(self, other) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.less_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@op(
    name="ArrowWeaveListNumber-negate",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def __neg__(self):
    return ArrowWeaveList(pc.negate(self._arrow_data), types.Number(), self._artifact)


# todo: fix op decorator to not require name here,
# these names are needed because the base class also has an op called floor.
# also true for ceil below
@op(
    name="ArrowWeaveListNumber-floor",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def floor(self):
    return ArrowWeaveList(pc.floor(self._arrow_data), types.Number(), self._artifact)


@op(
    name="ArrowWeaveListNumber-ceil",
    input_type={
        "self": ARROW_WEAVE_LIST_NUMBER_TYPE,
    },
    output_type=ARROW_WEAVE_LIST_NUMBER_TYPE,
)
def ceil(self):
    return ArrowWeaveList(pc.ceil(self._arrow_data), types.Number(), self._artifact)
