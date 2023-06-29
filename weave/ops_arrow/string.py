import typing

import pyarrow as pa
import pyarrow.compute as pc

from .arrow import offsets_starting_at_zero

from ..api import op
from ..decorator_arrow_op import arrow_op
from .. import weave_types as types

from .list_ import ArrowWeaveList, ArrowWeaveListType
from .arrow import ArrowWeaveListType
from . import util


ARROW_WEAVE_LIST_STRING_TYPE = ArrowWeaveListType(types.String())
ARROW_WEAVE_LIST_BOOLEAN_TYPE = ArrowWeaveListType(types.Boolean())
ARROW_WEAVE_LIST_INT_TYPE = ArrowWeaveListType(types.Int())
ARROW_WEAVE_LIST_LIST_OF_STR_TYPE = ArrowWeaveListType(types.List(types.String()))

unary_input_type = {
    "self": ARROW_WEAVE_LIST_STRING_TYPE,
}
binary_input_type = {
    "self": ARROW_WEAVE_LIST_STRING_TYPE,
    "other": types.UnionType(
        types.optional(types.String()), ARROW_WEAVE_LIST_STRING_TYPE
    ),
}

null_consuming_binary_input_type = {
    "self": ArrowWeaveListType(types.optional(types.String())),
    "other": types.UnionType(
        types.optional(types.String()),
        ArrowWeaveListType(types.optional(types.String())),
    ),
}

null_consuming_binary_input_type_right = {
    "self": types.optional(types.String()),
    "other": ArrowWeaveListType(types.optional(types.String())),
}

self_type_output_type_fn = lambda input_types: input_types["self"]


def _concatenate_strings(
    left: ArrowWeaveList[str], right: typing.Union[str, ArrowWeaveList[str]]
) -> ArrowWeaveList[str]:
    a = left._arrow_data
    if right == None:
        return ArrowWeaveList(
            pa.nulls(len(a), type=a.type),
            types.NoneType(),
            left._artifact,
        )
    if isinstance(right, ArrowWeaveList):
        right = right._arrow_data
    return ArrowWeaveList(
        pc.binary_join_element_wise(left._arrow_data, right, ""),
        types.String(),
        left._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-equal",
    input_type=null_consuming_binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __eq__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    result = util.equal(self._arrow_data, other)
    return ArrowWeaveList(result, types.Boolean(), self._artifact)


@arrow_op(
    name="ArrowWeaveListString-notEqual",
    input_type=null_consuming_binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def __ne__(self, other):
    if isinstance(other, ArrowWeaveList):
        other = other._arrow_data
    result = util.not_equal(self._arrow_data, other)
    return ArrowWeaveList(result, types.Boolean(), self._artifact)


@arrow_op(
    name="ArrowWeaveListString-contains",
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
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
    input_type=binary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def in_(self, other):
    if isinstance(other, ArrowWeaveList):

        def new_val_iterator():
            for my_item, other_item in zip(self._arrow_data, other._arrow_data):
                if (
                    pa.compute.is_null(my_item).as_py()
                    or pa.compute.is_null(other_item).as_py()
                ):
                    yield None
                else:
                    yield my_item.as_py() in other_item.as_py()

        return ArrowWeaveList(
            pa.array(new_val_iterator()),
            types.Boolean(),
            self._artifact,
        )

    return ArrowWeaveList(
        # this has to be a python loop because the second argument to match_substring has to be a scalar string
        pa.array(
            item.as_py() in other if not pa.compute.is_null(item).as_py() else None
            for item in self._arrow_data
        ),
        types.Boolean(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-len",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_INT_TYPE,
)
def arrowweavelist_len(self):
    return ArrowWeaveList(
        pc.binary_length(self._arrow_data), types.Int(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-add",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def string_add(self, other):
    return _concatenate_strings(self, other)


# Handle plain str on the left. We'll need to figure out how to do
# this generally.
# TODO: Do this generally!
@op(
    name="ArrowWeaveListString_right-add",
    output_type=lambda input_type: input_type["right"],
)
def string_right_add(
    left: typing.Optional[str], right: ArrowWeaveList[typing.Optional[str]]
):
    return ArrowWeaveList(
        pc.binary_join_element_wise(left, right._arrow_data_asarray_no_tags(), ""),
        types.String(),
        right._artifact,
    )


# todo: remove this explicit name, it shouldn't be needed
@arrow_op(
    name="ArrowWeaveListString-append",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
)
def append(self, other):
    return _concatenate_strings(self, other)


@arrow_op(
    name="ArrowWeaveListString-prepend",
    input_type=binary_input_type,
    output_type=self_type_output_type_fn,
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
    output_type=ARROW_WEAVE_LIST_LIST_OF_STR_TYPE,
)
def split(self, pattern):
    if isinstance(pattern, str):
        return ArrowWeaveList(
            pc.split_pattern(self._arrow_data, pattern),
            types.optional(types.List(types.String())),
            self._artifact,
        )
    return ArrowWeaveList(
        pa.array(
            self._arrow_data[i].as_py().split(pattern._arrow_data[i].as_py())
            for i in range(len(self._arrow_data))
        ),
        types.optional(types.List(types.String())),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-partition",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "sep": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_LIST_OF_STR_TYPE,
)
def partition(self, sep):
    def data_iterator():
        for i in range(len(self._arrow_data)):
            item = self._arrow_data[i].as_py()
            separator = sep if isinstance(sep, str) else sep._arrow_data[i].as_py()
            if not (item is None or separator is None):
                yield item.partition(separator)
            else:
                yield None

    return ArrowWeaveList(
        pa.array(data_iterator()),
        types.optional(types.List(types.String())),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-startsWith",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "prefix": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
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
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
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
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def isalpha(self):
    return ArrowWeaveList(
        pc.ascii_is_alpha(self._arrow_data), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-isNumeric",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def isnumeric(self):
    return ArrowWeaveList(
        pc.ascii_is_decimal(self._arrow_data), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-isAlnum",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def isalnum(self):
    return ArrowWeaveList(
        pc.ascii_is_alnum(self._arrow_data), types.Boolean(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-lower",
    input_type=unary_input_type,
    output_type=ArrowWeaveListType(types.String()),
)
def lower(self):
    return ArrowWeaveList(
        pc.ascii_lower(self._arrow_data), types.String(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-upper",
    input_type=unary_input_type,
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
    output_type=self_type_output_type_fn,
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
    output_type=self_type_output_type_fn,
)
def replace(self, pattern, replacement):
    return ArrowWeaveList(
        pc.replace_substring(self._arrow_data, pattern, replacement),
        types.String(),
        self._artifact,
    )


@arrow_op(
    name="ArrowWeaveListString-strip",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def strip(self):
    return ArrowWeaveList(
        pc.utf8_trim_whitespace(self._arrow_data), types.String(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-lStrip",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def lstrip(self):
    return ArrowWeaveList(
        pc.utf8_ltrim_whitespace(self._arrow_data), types.String(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-rStrip",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def rstrip(self):
    return ArrowWeaveList(
        pc.utf8_rtrim_whitespace(self._arrow_data), types.String(), self._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-joinToStr",
    input_type={
        "arr": ArrowWeaveListType(types.List(types.optional(types.String()))),
        "sep": types.UnionType(types.String(), ArrowWeaveListType(types.String())),
    },
    output_type=ArrowWeaveListType(types.String()),
)
def join_to_str(arr, sep):
    if isinstance(sep, ArrowWeaveList):
        sep = sep._arrow_data
    # match Weave0 - join nulls to empty string
    filled_arr = pa.ListArray.from_arrays(
        offsets_starting_at_zero(arr._arrow_data),
        arr._arrow_data.flatten().fill_null(""),
    )
    return ArrowWeaveList(
        pc.binary_join(filled_arr, sep), types.String(), arr._artifact
    )


@arrow_op(
    name="ArrowWeaveListString-toNumber",
    input_type={"self": ArrowWeaveListType(types.String())},
    output_type=ArrowWeaveListType(types.Number()),
)
def to_number(self):
    arrow_data = self._arrow_data
    is_not_numeric = pc.invert(pc.utf8_is_numeric(arrow_data))

    # need to use kleene logic here for masking
    mask = pc.and_kleene(is_not_numeric, pa.nulls(len(self)).cast(pa.bool_()))

    new_data = pc.replace_with_mask(arrow_data, mask, arrow_data).cast(pa.float64())
    return ArrowWeaveList(new_data, types.optional(types.Number()), self._artifact)
