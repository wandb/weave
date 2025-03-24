import typing

import pyarrow as pa
import pyarrow.compute as pc

from weave_query import weave_types as types
from weave_query.api import op
from weave_query.arrow.arrow import ArrowWeaveListType, offsets_starting_at_zero
from weave_query.arrow.list_ import ArrowWeaveList, ArrowWeaveListType
from weave_query.decorator_arrow_op import arrow_op
from weave_query.ops_arrow import util

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
    return util.handle_dictionary_array(self, pc.binary_length, types.Int())


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
    def _split(arrow_data):
        if isinstance(pattern, str):
            return pc.split_pattern(arrow_data, pattern)
        else:
            return pa.array(
                item.as_py().split(p.as_py())
                if item.as_py() is not None and p.as_py() is not None
                else None
                for item, p in zip(arrow_data, pattern._arrow_data)
            )

    return util.handle_dictionary_array(
        self, _split, types.optional(types.List(types.String()))
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
    if sep is None:
        return ArrowWeaveList(
            pa.array([None] * len(self._arrow_data)),
            types.optional(types.List(types.String())),
            self._artifact,
        )

    if isinstance(sep, str):
        return ArrowWeaveList(
            pa.array(
                [
                    item.as_py().partition(sep) if item.as_py() is not None else None
                    for item in self._arrow_data
                ]
            ),
            types.optional(types.List(types.String())),
            self._artifact,
        )

    return ArrowWeaveList(
        pa.array(
            [
                item.as_py().partition(s.as_py())
                if item.as_py() is not None and s.as_py() is not None
                else None
                for item, s in zip(self._arrow_data, sep._arrow_data)
            ]
        ),
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
    def _startswith(arrow_data):
        if isinstance(prefix, str):
            return pc.starts_with(arrow_data, prefix)
        else:
            return pa.array(
                s.as_py().startswith(p.as_py())
                if s.as_py() is not None and p.as_py() is not None
                else None
                for s, p in zip(arrow_data, prefix._arrow_data)
            )

    return util.handle_dictionary_array(self, _startswith, types.Boolean())


@arrow_op(
    name="ArrowWeaveListString-endsWith",
    input_type={
        "self": ARROW_WEAVE_LIST_STRING_TYPE,
        "suffix": types.UnionType(types.String(), ARROW_WEAVE_LIST_STRING_TYPE),
    },
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def endswith(self, suffix):
    def _ends_with(arrow_data):
        if isinstance(suffix, str):
            return pc.ends_with(arrow_data, suffix)
        else:
            return pa.array(
                s.as_py().endswith(p.as_py())
                if s.as_py() is not None and p.as_py() is not None
                else None
                for s, p in zip(arrow_data, suffix._arrow_data)
            )

    return util.handle_dictionary_array(self, _ends_with, types.Boolean())


@arrow_op(
    name="ArrowWeaveListString-isAlpha",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def isalpha(self):
    return util.handle_dictionary_array(self, pc.ascii_is_alpha, types.Boolean())


@arrow_op(
    name="ArrowWeaveListString-isNumeric",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def isnumeric(self):
    return util.handle_dictionary_array(self, pc.ascii_is_decimal, types.Boolean())


@arrow_op(
    name="ArrowWeaveListString-isAlnum",
    input_type=unary_input_type,
    output_type=ARROW_WEAVE_LIST_BOOLEAN_TYPE,
)
def isalnum(self):
    return util.handle_dictionary_array(self, pc.ascii_is_alnum, types.Boolean())


@arrow_op(
    name="ArrowWeaveListString-lower",
    input_type=unary_input_type,
    output_type=ArrowWeaveListType(types.String()),
)
def lower(self):
    return util.handle_dictionary_array(self, pc.ascii_lower, types.String())


@arrow_op(
    name="ArrowWeaveListString-upper",
    input_type=unary_input_type,
    output_type=ArrowWeaveListType(types.String()),
)
def upper(self):
    return util.handle_dictionary_array(self, pc.ascii_upper, types.String())


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
    return util.handle_dictionary_array(
        self, lambda arr: pc.utf8_slice_codeunits(arr, begin, end), types.String()
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
    return util.handle_dictionary_array(
        self,
        lambda arr: pc.replace_substring(arr, pattern, replacement),
        types.String(),
    )


@arrow_op(
    name="ArrowWeaveListString-strip",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def strip(self):
    return util.handle_dictionary_array(self, pc.utf8_trim_whitespace, types.String())


@arrow_op(
    name="ArrowWeaveListString-lStrip",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def lstrip(self):
    return util.handle_dictionary_array(self, pc.utf8_ltrim_whitespace, types.String())


@arrow_op(
    name="ArrowWeaveListString-rStrip",
    input_type=unary_input_type,
    output_type=self_type_output_type_fn,
)
def rstrip(self):
    return util.handle_dictionary_array(self, pc.utf8_rtrim_whitespace, types.String())


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

    def _join_to_str(arrow_data):
        # match Weave0 - join nulls to empty string
        filled_arr = pa.ListArray.from_arrays(
            offsets_starting_at_zero(arrow_data),
            arrow_data.flatten().fill_null(""),
        )
        return pc.binary_join(filled_arr, sep)

    return util.handle_dictionary_array(arr, _join_to_str, types.String())


@arrow_op(
    name="ArrowWeaveListString-toNumber",
    input_type={"self": ArrowWeaveListType(types.String())},
    output_type=ArrowWeaveListType(types.optional(types.Number())),
)
def to_number(self):
    def _to_number(arrow_data):
        is_not_numeric = pc.invert(pc.utf8_is_numeric(arrow_data))

        # need to use kleene logic here for masking
        mask = pc.and_kleene(is_not_numeric, pa.nulls(len(arrow_data)).cast(pa.bool_()))

        new_data = pc.replace_with_mask(arrow_data, mask, arrow_data).cast(pa.float64())
        return new_data

    return util.handle_dictionary_array(
        self, _to_number, types.optional(types.Number())
    )
