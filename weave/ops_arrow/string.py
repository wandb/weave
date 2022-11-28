import typing

import pyarrow as pa
import pyarrow.compute as pc

from ..api import op
from .. import weave_types as types

from .list_ import ArrowWeaveList


def _concatenate_strings(
    left: ArrowWeaveList[str], right: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[str]:
    if isinstance(right, ArrowWeaveList):
        right = right._arrow_data
    return ArrowWeaveList(
        pc.binary_join_element_wise(left._arrow_data, right, ""), types.String()
    )


@op(name="ArrowWeaveListString-equal")
def __eq__(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(pc.equal(self._arrow_data, other), types.Boolean())


@op(name="ArrowWeaveListString-notEqual")
def __ne__(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(pc.not_equal(self._arrow_data, other), types.Boolean())


@op(name="ArrowWeaveListString-contains")
def __contains__(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        return ArrowWeaveList(
            pa.array(
                other_item.as_py() in my_item.as_py()
                for my_item, other_item in zip(self._arrow_data, other._arrow_data)
            )
        )
    return ArrowWeaveList(pc.match_substring(self._arrow_data, other), types.Boolean())


# TODO: fix
@op(name="ArrowWeaveListString-in")
def in_(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[bool]:
    if isinstance(other, ArrowWeaveList):
        return ArrowWeaveList(
            pa.array(
                my_item.as_py() in other_item.as_py()
                for my_item, other_item in zip(self._arrow_data, other._arrow_data)
            )
        )
    return ArrowWeaveList(
        # this has to be a python loop because the second argument to match_substring has to be a scalar string
        pa.array(item.as_py() in other for item in self._arrow_data),
        types.Boolean(),
    )


@op(name="ArrowWeaveListString-len")
def arrowweavelist_len(self: ArrowWeaveList[str]) -> ArrowWeaveList[int]:
    return ArrowWeaveList(pc.binary_length(self._arrow_data), types.Int())


@op(name="ArrowWeaveListString-add")
def __add__(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[str]:
    return _concatenate_strings(self, other)


# todo: remove this explicit name, it shouldn't be needed
@op(name="ArrowWeaveListString-append")
def append(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[str]:
    return _concatenate_strings(self, other)


@op(name="ArrowWeaveListString-prepend")
def prepend(
    self: ArrowWeaveList[str], other: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[str]:
    if isinstance(other, str):
        other = ArrowWeaveList(
            pa.array([other] * len(self._arrow_data)), types.String()
        )
    return _concatenate_strings(other, self)


@op(name="ArrowWeaveListString-split")
def split(
    self: ArrowWeaveList[str], pattern: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[list[str]]:
    if isinstance(pattern, str):
        return ArrowWeaveList(
            pc.split_pattern(self._arrow_data, pattern), types.List(types.String())
        )
    return ArrowWeaveList(
        pa.array(
            self._arrow_data[i].as_py().split(pattern._arrow_data[i].as_py())
            for i in range(len(self._arrow_data))
        ),
        types.List(types.String()),
    )


@op(name="ArrowWeaveListString-partition")
def partition(
    self: ArrowWeaveList[str], sep: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[list[str]]:
    return ArrowWeaveList(
        pa.array(
            self._arrow_data[i]
            .as_py()
            .partition(sep if isinstance(sep, str) else sep._arrow_data[i].as_py())
            for i in range(len(self._arrow_data))
        ),
        types.List(types.String()),
    )


@op(name="ArrowWeaveListString-startsWith")
def startswith(
    self: ArrowWeaveList[str], prefix: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[bool]:
    if isinstance(prefix, str):
        return ArrowWeaveList(
            pc.starts_with(self._arrow_data, prefix),
            types.Boolean(),
        )
    return ArrowWeaveList(
        pa.array(
            s.as_py().startswith(p.as_py())
            for s, p in zip(self._arrow_data, prefix._arrow_data)
        ),
        types.Boolean(),
    )


@op(name="ArrowWeaveListString-endsWith")
def endswith(
    self: ArrowWeaveList[str], suffix: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[bool]:
    if isinstance(suffix, str):
        return ArrowWeaveList(
            pc.ends_with(self._arrow_data, suffix),
            types.Boolean(),
        )
    return ArrowWeaveList(
        pa.array(
            s.as_py().endswith(p.as_py())
            for s, p in zip(self._arrow_data, suffix._arrow_data)
        ),
        types.Boolean(),
    )


@op(name="ArrowWeaveListString-isAlpha")
def isalpha(self: ArrowWeaveList[str]) -> ArrowWeaveList[bool]:
    return ArrowWeaveList(pc.ascii_is_alpha(self._arrow_data), types.Boolean())


@op(name="ArrowWeaveListString-isNumeric")
def isnumeric(self: ArrowWeaveList[str]) -> ArrowWeaveList[bool]:
    return ArrowWeaveList(pc.ascii_is_decimal(self._arrow_data), types.Boolean())


@op(name="ArrowWeaveListString-isAlnum")
def isalnum(self: ArrowWeaveList[str]) -> ArrowWeaveList[bool]:
    return ArrowWeaveList(pc.ascii_is_alnum(self._arrow_data), types.Boolean())


@op(name="ArrowWeaveListString-lower")
def lower(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(pc.ascii_lower(self._arrow_data), types.String())


@op(name="ArrowWeaveListString-upper")
def upper(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(pc.ascii_upper(self._arrow_data), types.String())


@op(name="ArrowWeaveListString-slice")
def slice(self: ArrowWeaveList[str], begin: int, end: int) -> ArrowWeaveList[str]:
    return ArrowWeaveList(
        pc.utf8_slice_codeunits(self._arrow_data, begin, end), types.String()
    )


@op(name="ArrowWeaveListString-replace")
def replace(
    self: ArrowWeaveList[str], pattern: str, replacement: str
) -> ArrowWeaveList[str]:
    return ArrowWeaveList(
        pc.replace_substring(self._arrow_data, pattern, replacement),
        types.String(),
    )


@op(name="ArrowWeaveListString-strip")
def strip(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(pc.utf8_trim_whitespace(self._arrow_data), types.String())


@op(name="ArrowWeaveListString-lStrip")
def lstrip(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(pc.utf8_ltrim_whitespace(self._arrow_data), types.String())


@op(name="ArrowWeaveListString-rStrip")
def rstrip(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(pc.utf8_rtrim_whitespace(self._arrow_data), types.String())
