import typing

import pyarrow as pa
import pyarrow.compute as pc

from ..api import op
from ..decorator_op import arrow_op
from .. import weave_types as types

from .list_ import ArrowWeaveList, ArrowWeaveListType


ARROW_WEAVE_LIST_STRING_TYPE = ArrowWeaveListType(types.String())


def _concatenate_strings(
    left: ArrowWeaveList[str], right: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[str]:
    if isinstance(right, ArrowWeaveList):
        right = right._arrow_data
    return ArrowWeaveList(
        pc.binary_join_element_wise(left._arrow_data, right, ""),
        types.String(),
        left._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-equal",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.Boolean()),
)
def __eq__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-notEqual",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.Boolean()),
)
def __ne__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    return ArrowWeaveList(
        pc.not_equal(self._arrow_data, other), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-contains",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.Boolean()),
)
def __contains__(self, other):
    if isinstance(other, ArrowWeaveList):
        return ArrowWeaveList(
            pa.array(
                other_item.as_py() in my_item.as_py()
                for my_item, other_item in zip(self._arrow_data, other._arrow_data)
            ),
            None,
            self._artifact,
        )
    return ArrowWeaveList(
        pc.match_substring(self._arrow_data, other), types.Boolean(), self._artifact
    )


# TODO: fix
@arrow_op(
    name="ArrowWeaveListString-in",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.Boolean()),
)
def in_(self, other):
    if isinstance(other, ArrowWeaveList):
        return ArrowWeaveList(
            pa.array(
                my_item.as_py() in other_item.as_py()
                for my_item, other_item in zip(self._arrow_data, other._arrow_data)
            ),
            None,
            self._artifact,
        )
    return ArrowWeaveList(
        # this has to be a python loop because the second argument to match_substring has to be a scalar string
        pa.array(item.as_py() in other for item in self._arrow_data),
        types.Boolean(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-len",
    input_type={"self": ARROW_WEAVE_LIST_STRING_TYPE},
    output_type=ArrowWeaveListType(types.Int()),
)
def arrowweavelist_len(self):
    return ArrowWeaveList(
        pc.binary_length(self._arrow_data), types.Int(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-add",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_STRING_TYPE,
)
def __add__(self, other):
    return _concatenate_strings(self, other)


# todo: remove this explicit name, it shouldn't be needed
@arrow_op(
    name="ArrowWeaveListString-append",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_STRING_TYPE,
)
def append(self, other):
    return _concatenate_strings(self, other)


@arrow_op(
    name="ArrowWeaveListString-prepend",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "other": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_STRING_TYPE,
)
def prepend(self, other):
    if isinstance(other, str):
        other = ArrowWeaveList(
            pa.array([other] * len(self._arrow_data)), types.String(), self._artifact
        )
    return _concatenate_strings(other, self)


@arrow_op(
    name="ArrowWeaveListString-split",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "pattern": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.List(types.String())),
)
def split(self, pattern):
    if isinstance(pattern, str):
        return ArrowWeaveList(
            pc.split_pattern(self._arrow_data, pattern),
            types.List(types.String()),
            self._artifact,
        )
    return ArrowWeaveList(
        pa.array(
            self._arrow_data[i].as_py().split(pattern._arrow_data[i].as_py())
            for i in range(len(self._arrow_data))
        ),
        types.List(types.String()),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-partition",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "sep": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.List(types.String())),
)
def partition(self, sep):
    return ArrowWeaveList(
        pa.array(
            self._arrow_data[i]
            .as_py()
            .partition(sep if isinstance(sep, str) else sep._arrow_data[i].as_py())
            for i in range(len(self._arrow_data))
        ),
        types.List(types.String()),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-startsWith",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "prefix": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.Boolean()),
)
def startswith(self, prefix):
    if isinstance(prefix, str):
        return ArrowWeaveList(
            pc.starts_with(self._arrow_data, prefix), types.Boolean(), self._artifact
        )
    return ArrowWeaveList(
        pa.array(
            s.as_py().startswith(p.as_py())
            for s, p in zip(self._arrow_data, prefix._arrow_data)
        ),
        types.Boolean(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-endsWith",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "suffix": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ArrowWeaveListType(types.Boolean()),
)
def endswith(self, suffix):
    if isinstance(suffix, str):
        return ArrowWeaveList(
            pc.ends_with(self._arrow_data, suffix), types.Boolean(), self._artifact
        )
    return ArrowWeaveList(
        pa.array(
            s.as_py().endswith(p.as_py())
            for s, p in zip(self._arrow_data, suffix._arrow_data)
        ),
        types.Boolean(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-isAlpha",
    input_type={"self": ARROW_WEAVE_LIST_STRING_TYPE},
    output_type=ArrowWeaveListType(types.Boolean()),
)
def isalpha(self):
    return ArrowWeaveList(
        pc.ascii_is_alpha(self._arrow_data), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-isNumeric",
    input_type={"self": ARROW_WEAVE_LIST_STRING_TYPE},
    output_type=ArrowWeaveListType(types.Boolean()),
)
def isnumeric(self):
    return ArrowWeaveList(
        pc.ascii_is_decimal(self._arrow_data), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-isAlnum",
    input_type={"self": ARROW_WEAVE_LIST_STRING_TYPE},
    output_type=ArrowWeaveListType(types.Boolean()),
)
def isalnum(self):
    return ArrowWeaveList(
        pc.ascii_is_alnum(self._arrow_data), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-lower",
    input_type={"self": ARROW_WEAVE_LIST_STRING_TYPE},
    output_type=ArrowWeaveListType(types.String()),
)
def lower(self):
    return ArrowWeaveList(
        pc.ascii_lower(self._arrow_data), types.String(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-upper",
    input_type={"self": ARROW_WEAVE_LIST_STRING_TYPE},
    output_type=ArrowWeaveListType(types.String()),
)
def upper(self):
    return ArrowWeaveList(
        pc.ascii_upper(self._arrow_data), types.String(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-slice",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "begin": types.Int(),
        "end": types.Int(),
    },
    output_type=ARROW_WEAVE_LIST_STRING_TYPE,
)
def slice(self, begin, end):
    return ArrowWeaveList(
        pc.utf8_slice_codeunits(self._arrow_data, begin, end),
        types.String(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-replace",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "pattern": types.String(),
        "replacement": types.String(),
    },
    output_type=ARROW_WEAVE_LIST_STRING_TYPE,
)
def replace(self, pattern, replacement):
    return ArrowWeaveList(
        pc.replace_substring(self._arrow_data, pattern, replacement),
        types.String(),
        self._artifact,
    )


@op(name="ArrowWeaveListString-strip")
def strip(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(
        pc.utf8_trim_whitespace(self._arrow_data), types.String(), self._artifact
    )


@op(name="ArrowWeaveListString-lStrip")
def lstrip(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(
        pc.utf8_ltrim_whitespace(self._arrow_data), types.String(), self._artifact
    )


@op(name="ArrowWeaveListString-rStrip")
def rstrip(self: ArrowWeaveList[str]) -> ArrowWeaveList[str]:
    return ArrowWeaveList(
        pc.utf8_rtrim_whitespace(self._arrow_data), types.String(), self._artifact
    )
