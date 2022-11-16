import dataclasses
import pyarrow.compute as pc

from ..api import op, weave_class, type, use, OpVarArgs, type_of
from .. import weave_types as types

from .list_ import ArrowWeaveList, ArrowWeaveListType


@dataclasses.dataclass(frozen=True)
class ArrowWeaveListNumberType(ArrowWeaveListType):
    # TODO: This should not be assignable via constructor. It should be
    #    a static property type at this point.
    name = "ArrowWeaveListNumber"
    object_type: types.Type = types.Number()


@weave_class(weave_type=ArrowWeaveListNumberType)
class ArrowWeaveListNumber(ArrowWeaveList):
    object_type = types.Number()

    # TODO: weirdly need to name this "<something>-add" since that's what the base
    # Number op does. But we'd like to get rid of that requirement so we don't
    # need name= for any ops!
    @op(
        name="ArrowWeaveListNumber-add",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
        output_type=ArrowWeaveListNumberType(),
    )
    def __add__(self, other):
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.add(self._arrow_data, other), types.Number())

    @op(
        name="ArrowWeaveListNumber-mult",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
        output_type=ArrowWeaveListNumberType(),
    )
    def __mul__(self, other):
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.multiply(self._arrow_data, other), types.Number())

    @op(
        name="ArrowWeaveListNumber-div",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
        output_type=ArrowWeaveListNumberType(),
    )
    def __truediv__(self, other):
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.divide(self._arrow_data, other), types.Number())

    @op(
        name="ArrowWeaveListNumber-sub",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
        output_type=ArrowWeaveListNumberType(),
    )
    def __sub__(self, other):
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.subtract(self._arrow_data, other), types.Number())

    @op(
        name="ArrowWeaveListNumber-powBinary",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
        output_type=ArrowWeaveListNumberType(),
    )
    def __pow__(self, other):
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.power(self._arrow_data, other), types.Number())

    @op(
        name="ArrowWeaveListNumber-notEqual",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
    )
    def __ne__(self, other) -> ArrowWeaveList[bool]:
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.not_equal(self._arrow_data, other), types.Boolean())

    @op(
        name="ArrowWeaveListNumber-equal",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
    )
    def __eq__(self, other) -> ArrowWeaveList[bool]:
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.equal(self._arrow_data, other), types.Boolean())

    @op(
        name="ArrowWeaveListNumber-greater",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
    )
    def __gt__(self, other) -> ArrowWeaveList[bool]:
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.greater(self._arrow_data, other), types.Boolean())

    @op(
        name="ArrowWeaveListNumber-greaterEqual",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
    )
    def __ge__(self, other) -> ArrowWeaveList[bool]:
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(
            pc.greater_equal(self._arrow_data, other), types.Boolean()
        )

    @op(
        name="ArrowWeaveListNumber-less",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
    )
    def __lt__(self, other) -> ArrowWeaveList[bool]:
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.less(self._arrow_data, other), types.Boolean())

    @op(
        name="ArrowWeaveListNumber-lessEqual",
        input_type={
            "self": ArrowWeaveListNumberType(),
            "other": types.UnionType(types.Number(), ArrowWeaveListNumberType()),
        },
    )
    def __le__(self, other) -> ArrowWeaveList[bool]:
        if isinstance(other, ArrowWeaveList):
            other = other._arrow_data
        return ArrowWeaveList(pc.less_equal(self._arrow_data, other), types.Boolean())

    @op(
        name="ArrowWeaveListNumber-negate",
        output_type=ArrowWeaveListNumberType(),
    )
    def __neg__(self):
        return ArrowWeaveList(pc.negate(self._arrow_data), types.Number())

    # todo: fix op decorator to not require name here,
    # these names are needed because the base class also has an op called floor.
    # also true for ceil below
    @op(name="ArrowWeaveListNumber-floor", output_type=ArrowWeaveListNumberType())
    def floor(self):
        return ArrowWeaveList(pc.floor(self._arrow_data), types.Number())

    @op(name="ArrowWeaveListNumber-ceil", output_type=ArrowWeaveListNumberType())
    def ceil(self):
        return ArrowWeaveList(pc.ceil(self._arrow_data), types.Number())
